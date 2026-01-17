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
use solverforge_maps::{BoundingBox, RoadNetwork, RoutingProgress};
use std::collections::HashMap;
use std::convert::Infallible;
use std::sync::Arc;
use tokio::sync::mpsc;
use uuid::Uuid;

use crate::demo_data::{self, DemoData};
use crate::domain::VehicleRoutePlan;
use crate::dto::*;

struct SolveJob {
    solution: VehicleRoutePlan,
    solver_status: String,
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

                // Use unified API with a progress channel that drains buffered messages
                let (tx, mut rx) = mpsc::channel::<RoutingProgress>(100);

                // Spawn a task to consume progress messages (non-streaming, so we just drain)
                tokio::spawn(async move {
                    while rx.recv().await.is_some() {
                        // Discard progress messages in non-streaming mode
                    }
                });

                if let Ok(result) =
                    RoadNetwork::load_and_compute(&bbox, &plan.coordinates, tx).await
                {
                    plan.travel_times = result.travel_times;
                    plan.geometries = result.geometries;
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
            let complete = SseComplete { event: "complete", solution: dto };
            yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
        } else {
            // Real roads path - use unified API with progress streaming
            let bbox = BoundingBox::new(
                plan.south_west_corner.0,
                plan.south_west_corner.1,
                plan.north_east_corner.0,
                plan.north_east_corner.1,
            );

            // Create progress channel
            let (tx, mut rx) = mpsc::channel::<RoutingProgress>(100);

            // Spawn the computation task
            let coordinates = plan.coordinates.clone();
            let compute_handle = tokio::spawn(async move {
                RoadNetwork::load_and_compute(&bbox, &coordinates, tx).await
            });

            // Stream progress events as they arrive
            while let Some(progress) = rx.recv().await {
                let (phase, message) = progress_to_phase_message(&progress);
                let sse_progress = SseProgress {
                    event: "progress",
                    phase,
                    message,
                    percent: progress.percent(),
                    detail: progress_detail(&progress),
                };
                yield Ok(Event::default().data(serde_json::to_string(&sse_progress).unwrap()));
            }

            // Get final result
            match compute_handle.await {
                Ok(Ok(result)) => {
                    plan.travel_times = result.travel_times;
                    plan.geometries = result.geometries;

                    let progress = SseProgress { event: "progress", phase: "complete", message: "Ready!", percent: 100, detail: None };
                    yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

                    let dto = VehicleRoutePlanDto::from_plan(&plan, None);
                    let complete = SseComplete { event: "complete", solution: dto };
                    yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
                }
                Ok(Err(e)) => {
                    let err = SseError { event: "error", message: format!("Failed to load road network: {}", e) };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                }
                Err(e) => {
                    let err = SseError { event: "error", message: format!("Task panicked: {}", e) };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                }
            }
        }
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

/// Converts RoutingProgress to (phase, message) for SSE.
fn progress_to_phase_message(progress: &RoutingProgress) -> (&'static str, &'static str) {
    match progress {
        RoutingProgress::CheckingCache { .. } => ("cache", "Checking cache..."),
        RoutingProgress::DownloadingNetwork { .. } => ("network", "Downloading road network..."),
        RoutingProgress::ParsingOsm { .. } => ("parsing", "Parsing OSM data..."),
        RoutingProgress::BuildingGraph { .. } => ("building", "Building routing graph..."),
        RoutingProgress::ComputingMatrix { .. } => ("matrix", "Computing travel times..."),
        RoutingProgress::ComputingGeometries { .. } => ("geometry", "Computing route geometries..."),
        RoutingProgress::EncodingGeometries { .. } => ("encoding", "Encoding geometries..."),
        RoutingProgress::Complete => ("complete", "Ready!"),
    }
}

/// Extracts detail string from RoutingProgress for SSE.
fn progress_detail(progress: &RoutingProgress) -> Option<String> {
    match progress {
        RoutingProgress::DownloadingNetwork { bytes, .. } if *bytes > 0 => {
            Some(format!("{} KB downloaded", bytes / 1024))
        }
        RoutingProgress::ParsingOsm { nodes, edges, .. } => {
            Some(format!("{} nodes, {} edges", nodes, edges))
        }
        RoutingProgress::ComputingMatrix { row, total, .. } => {
            Some(format!("Row {}/{}", row, total))
        }
        RoutingProgress::ComputingGeometries { pair, total, .. } => {
            Some(format!("Pair {}/{}", pair, total))
        }
        _ => None,
    }
}

async fn create_route_plan(
    State(state): State<Arc<AppState>>,
    Query(query): Query<RoutingQuery>,
    Json(dto): Json<VehicleRoutePlanDto>,
) -> String {
    let id = Uuid::new_v4().to_string();
    let mut plan = dto.to_domain();

    // Load road network and compute matrix if real_roads routing requested
    if query.routing.as_deref() == Some("real_roads") {
        let bbox = BoundingBox::new(
            plan.south_west_corner.0,
            plan.south_west_corner.1,
            plan.north_east_corner.0,
            plan.north_east_corner.1,
        );

        // Use unified API with a progress channel that drains buffered messages
        let (tx, mut rx) = mpsc::channel::<RoutingProgress>(100);

        // Spawn a task to consume progress messages (non-streaming, so we just drain)
        tokio::spawn(async move {
            while rx.recv().await.is_some() {
                // Discard progress messages in non-streaming mode
            }
        });

        if let Ok(result) = RoadNetwork::load_and_compute(&bbox, &plan.coordinates, tx).await {
            plan.travel_times = result.travel_times;
            plan.geometries = result.geometries;
        }
    }

    {
        let mut jobs = state.jobs.write();
        jobs.insert(
            id.clone(),
            SolveJob {
                solution: plan.clone(),
                solver_status: "SOLVING".to_string(),
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

async fn get_route_geometry(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<GeometryResponse>, StatusCode> {
    let jobs = state.jobs.read();
    let job = jobs.get(&id).ok_or(StatusCode::NOT_FOUND)?;
    let plan = &job.solution;

    let mut segments = Vec::new();
    for (v_idx, vehicle) in plan.vehicles.iter().enumerate() {
        let mut prev_loc = vehicle.home_location_idx;
        for &visit_idx in &vehicle.visits {
            let visit_loc = plan.visits[visit_idx].location_idx;
            if let Some(polyline) = plan.geometries.get(&(prev_loc, visit_loc)) {
                segments.push(GeometrySegment {
                    vehicle_idx: v_idx,
                    polyline: polyline.clone(),
                });
            }
            prev_loc = visit_loc;
        }
        // Return to home
        if !vehicle.visits.is_empty() {
            if let Some(polyline) = plan.geometries.get(&(prev_loc, vehicle.home_location_idx)) {
                segments.push(GeometrySegment {
                    vehicle_idx: v_idx,
                    polyline: polyline.clone(),
                });
            }
        }
    }

    Ok(Json(GeometryResponse { segments }))
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
