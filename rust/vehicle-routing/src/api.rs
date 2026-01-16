//! REST API handlers for Vehicle Routing.

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::sse::{Event, KeepAlive, Sse},
    routing::{delete, get, post, put},
    Json, Router,
};
use futures::stream::Stream;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use solverforge_maps::{encode_polyline, BoundingBox, RoadNetwork};
use std::collections::HashMap;
use std::convert::Infallible;
use std::sync::Arc;
use uuid::Uuid;

use crate::demo_data::{self, DemoData};
use crate::domain::VehicleRoutePlan;
use crate::dto::*;

struct SolveJob {
    solution: VehicleRoutePlan,
    solver_status: String,
    geometries: HashMap<(usize, usize), String>,
}

pub struct AppState {
    jobs: RwLock<HashMap<String, SolveJob>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            jobs: RwLock::new(HashMap::new()),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Deserialize)]
pub struct RoutingQuery {
    #[serde(default)]
    pub routing: Option<String>,
}

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/info", get(info))
        .route("/demo-data", get(list_demo_data))
        .route("/demo-data/{id}", get(get_demo_data))
        .route("/demo-data/{id}/stream", get(get_demo_data_stream))
        .route("/route-plans", post(create_route_plan))
        .route("/route-plans", get(list_route_plans))
        .route("/route-plans/analyze", put(analyze_route_plan))
        .route("/route-plans/{id}", get(get_route_plan))
        .route("/route-plans/{id}/status", get(get_route_plan_status))
        .route("/route-plans/{id}/geometry", get(get_route_geometry))
        .route("/route-plans/{id}", delete(stop_solving))
        .with_state(state)
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse { status: "UP" })
}

async fn info() -> Json<InfoResponse> {
    Json(InfoResponse {
        name: "Vehicle Routing",
        version: env!("CARGO_PKG_VERSION"),
        solver_engine: "SolverForge",
    })
}

async fn list_demo_data() -> Json<Vec<&'static str>> {
    Json(demo_data::list_demo_data())
}

async fn get_demo_data(
    Path(id): Path<String>,
    Query(query): Query<RoutingQuery>,
) -> Result<Json<VehicleRoutePlanDto>, StatusCode> {
    match id.parse::<DemoData>() {
        Ok(demo) => {
            let mut plan = demo_data::generate(demo);

            // Load road network and compute matrix if real_roads routing requested
            if query.routing.as_deref() == Some("real_roads") {
                let bbox = BoundingBox::new(
                    plan.south_west_corner.0,
                    plan.south_west_corner.1,
                    plan.north_east_corner.0,
                    plan.north_east_corner.1,
                );

                if let Ok(network) = RoadNetwork::load_or_fetch(&bbox).await {
                    plan.travel_times = network.compute_matrix(&plan.coordinates);
                }
            }

            Ok(Json(VehicleRoutePlanDto::from_plan(&plan, None)))
        }
        Err(_) => Err(StatusCode::NOT_FOUND),
    }
}

#[derive(Serialize)]
struct SseProgress {
    event: &'static str,
    phase: &'static str,
    message: &'static str,
    percent: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    detail: Option<String>,
}

#[derive(Serialize)]
struct SseComplete {
    event: &'static str,
    solution: VehicleRoutePlanDto,
    geometries: HashMap<String, Vec<String>>,
}

#[derive(Serialize)]
struct SseError {
    event: &'static str,
    message: String,
}

async fn get_demo_data_stream(
    Path(id): Path<String>,
    Query(query): Query<RoutingQuery>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let stream = async_stream::stream! {
        let demo = match id.parse::<DemoData>() {
            Ok(d) => d,
            Err(_) => {
                let err = SseError { event: "error", message: format!("Demo data not found: {}", id) };
                yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                return;
            }
        };

        let mut plan = demo_data::generate(demo);
        let use_real_roads = query.routing.as_deref() == Some("real_roads");

        if !use_real_roads {
            // Fast path - haversine
            let progress = SseProgress { event: "progress", phase: "computing", message: "Computing distances...", percent: 50, detail: None };
            yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

            let progress = SseProgress { event: "progress", phase: "complete", message: "Ready!", percent: 100, detail: None };
            yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

            let dto = VehicleRoutePlanDto::from_plan(&plan, None);
            let complete = SseComplete { event: "complete", solution: dto, geometries: HashMap::new() };
            yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
        } else {
            // Real roads path
            let progress = SseProgress { event: "progress", phase: "network", message: "Loading road network...", percent: 10, detail: None };
            yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

            let bbox = BoundingBox::new(
                plan.south_west_corner.0,
                plan.south_west_corner.1,
                plan.north_east_corner.0,
                plan.north_east_corner.1,
            );

            match RoadNetwork::load_or_fetch(&bbox).await {
                Ok(network) => {
                    let progress = SseProgress { event: "progress", phase: "routes", message: "Computing travel times...", percent: 50, detail: None };
                    yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

                    plan.travel_times = network.compute_matrix(&plan.coordinates);

                    let progress = SseProgress { event: "progress", phase: "routes", message: "Computing route geometries...", percent: 75, detail: None };
                    yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

                    let raw_geometries = network.compute_all_geometries(&plan.coordinates);
                    let encoded: HashMap<(usize, usize), String> = raw_geometries
                        .into_iter()
                        .map(|(k, coords)| (k, encode_polyline(&coords)))
                        .collect();

                    // Convert geometries to frontend format (vehicle_id -> [polylines])
                    let geometries = build_vehicle_geometries(&plan, &encoded);

                    let progress = SseProgress { event: "progress", phase: "complete", message: "Ready!", percent: 100, detail: None };
                    yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

                    let dto = VehicleRoutePlanDto::from_plan(&plan, None);
                    let complete = SseComplete { event: "complete", solution: dto, geometries };
                    yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
                }
                Err(e) => {
                    let err = SseError { event: "error", message: format!("Failed to load road network: {}", e) };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                }
            }
        }
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

fn build_vehicle_geometries(
    plan: &VehicleRoutePlan,
    encoded: &HashMap<(usize, usize), String>,
) -> HashMap<String, Vec<String>> {
    let mut result: HashMap<String, Vec<String>> = HashMap::new();

    for vehicle in &plan.vehicles {
        let vehicle_visits: Vec<_> = plan
            .visits
            .iter()
            .filter(|v| v.vehicle_idx == Some(vehicle.index))
            .collect();

        let mut polylines = Vec::new();
        let mut prev_idx = vehicle.home_location_idx;

        for visit in &vehicle_visits {
            if let Some(polyline) = encoded.get(&(prev_idx, visit.location_idx)) {
                polylines.push(polyline.clone());
            }
            prev_idx = visit.location_idx;
        }

        // Return to depot
        if !vehicle_visits.is_empty() {
            if let Some(polyline) = encoded.get(&(prev_idx, vehicle.home_location_idx)) {
                polylines.push(polyline.clone());
            }
        }

        result.insert(vehicle.id.clone(), polylines);
    }

    result
}

async fn create_route_plan(
    State(state): State<Arc<AppState>>,
    Query(query): Query<RoutingQuery>,
    Json(dto): Json<VehicleRoutePlanDto>,
) -> String {
    let id = Uuid::new_v4().to_string();
    let mut plan = dto.to_domain();

    // Load road network and compute matrix/geometries if real_roads routing requested
    let geometries = if query.routing.as_deref() == Some("real_roads") {
        let bbox = BoundingBox::new(
            plan.south_west_corner.0,
            plan.south_west_corner.1,
            plan.north_east_corner.0,
            plan.north_east_corner.1,
        );

        if let Ok(network) = RoadNetwork::load_or_fetch(&bbox).await {
            plan.travel_times = network.compute_matrix(&plan.coordinates);

            // Compute and encode geometries
            let raw_geometries = network.compute_all_geometries(&plan.coordinates);
            raw_geometries
                .into_iter()
                .map(|(k, coords)| (k, encode_polyline(&coords)))
                .collect()
        } else {
            HashMap::new()
        }
    } else {
        HashMap::new()
    };

    {
        let mut jobs = state.jobs.write();
        jobs.insert(
            id.clone(),
            SolveJob {
                solution: plan.clone(),
                solver_status: "SOLVING".to_string(),
                geometries,
            },
        );
    }

    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
    let job_id = id.clone();
    let state_clone = state.clone();

    tokio::spawn(async move {
        while let Some((solution, _score)) = rx.recv().await {
            let mut jobs = state_clone.jobs.write();
            if let Some(job) = jobs.get_mut(&job_id) {
                job.solution = solution;
            }
        }
        let mut jobs = state_clone.jobs.write();
        if let Some(job) = jobs.get_mut(&job_id) {
            job.solver_status = "NOT_SOLVING".to_string();
        }
    });

    use solverforge::Solvable;
    rayon::spawn(move || {
        plan.solve(None, tx);
    });

    id
}

async fn list_route_plans(State(state): State<Arc<AppState>>) -> Json<Vec<String>> {
    Json(state.jobs.read().keys().cloned().collect())
}

async fn get_route_plan(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<VehicleRoutePlanDto>, StatusCode> {
    match state.jobs.read().get(&id) {
        Some(job) => Ok(Json(VehicleRoutePlanDto::from_plan(
            &job.solution,
            Some(job.solver_status.clone()),
        ))),
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn get_route_plan_status(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<StatusResponse>, StatusCode> {
    match state.jobs.read().get(&id) {
        Some(job) => Ok(Json(StatusResponse {
            score: job.solution.score.map(|s| format!("{}", s)),
        })),
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn get_route_geometry(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<GeometryResponse>, StatusCode> {
    match state.jobs.read().get(&id) {
        Some(job) => {
            let solution = &job.solution;

            // Build route segments for each vehicle
            let segments: Vec<RouteSegmentDto> = solution
                .vehicles
                .iter()
                .map(|vehicle| {
                    // Get visits assigned to this vehicle
                    let vehicle_visits: Vec<_> = solution
                        .visits
                        .iter()
                        .filter(|v| v.vehicle_idx == Some(vehicle.index))
                        .collect();

                    // Build route coordinates
                    let mut route_coords: Vec<(f64, f64)> = Vec::new();

                    // Start from depot
                    if let Some(home_coords) =
                        solution.get_coordinates(vehicle.home_location_idx)
                    {
                        route_coords.push(home_coords);
                    }

                    // Add visit locations
                    let mut prev_loc_idx = vehicle.home_location_idx;
                    for visit in &vehicle_visits {
                        // If we have precomputed geometry, use it
                        if let Some(polyline) =
                            job.geometries.get(&(prev_loc_idx, visit.location_idx))
                        {
                            let decoded = solverforge_maps::decode_polyline(polyline);
                            // Skip first point (duplicate of previous end)
                            route_coords.extend(decoded.into_iter().skip(1));
                        } else if let Some(coords) = solution.get_coordinates(visit.location_idx) {
                            route_coords.push(coords);
                        }
                        prev_loc_idx = visit.location_idx;
                    }

                    // Return to depot
                    if !vehicle_visits.is_empty() {
                        if let Some(polyline) =
                            job.geometries.get(&(prev_loc_idx, vehicle.home_location_idx))
                        {
                            let decoded = solverforge_maps::decode_polyline(polyline);
                            route_coords.extend(decoded.into_iter().skip(1));
                        } else if let Some(home_coords) =
                            solution.get_coordinates(vehicle.home_location_idx)
                        {
                            route_coords.push(home_coords);
                        }
                    }

                    RouteSegmentDto {
                        vehicle_id: vehicle.id.clone(),
                        vehicle_name: vehicle.name.clone(),
                        polyline: encode_polyline(&route_coords),
                        point_count: route_coords.len(),
                    }
                })
                .collect();

            Ok(Json(GeometryResponse { segments }))
        }
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn stop_solving(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> StatusCode {
    if state.jobs.write().remove(&id).is_some() {
        StatusCode::NO_CONTENT
    } else {
        StatusCode::NOT_FOUND
    }
}

async fn analyze_route_plan(Json(dto): Json<VehicleRoutePlanDto>) -> Json<AnalyzeResponse> {
    use crate::constraints::define_constraints;
    use solverforge::{ConstraintSet, TypedScoreDirector};

    let plan = dto.to_domain();
    let constraints = define_constraints();
    let mut director = TypedScoreDirector::new(plan, constraints);
    let score = director.calculate_score();
    let analyses = director
        .constraints()
        .evaluate_detailed(director.working_solution());

    let constraints_dto: Vec<ConstraintAnalysisDto> = analyses
        .into_iter()
        .map(|analysis| ConstraintAnalysisDto {
            name: analysis.constraint_ref.name.clone(),
            constraint_type: if analysis.is_hard { "hard" } else { "soft" }.to_string(),
            weight: format!("{}", analysis.weight),
            score: format!("{}", analysis.score),
            matches: analysis
                .matches
                .iter()
                .map(|m| ConstraintMatchDto {
                    score: format!("{}", m.score),
                    justification: m.justification.description.clone(),
                })
                .collect(),
        })
        .collect();

    Json(AnalyzeResponse {
        score: format!("{}", score),
        constraints: constraints_dto,
    })
}
