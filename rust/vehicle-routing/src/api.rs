//! REST API handlers for Vehicle Routing.
//!
//! Uses SSE (Server-Sent Events) for all streaming operations:
//! - Demo data loading with real roads
//! - Solving with real-time solution updates

use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::sse::{Event, KeepAlive, Sse},
    routing::{get, post, put},
    Json, Router,
};
use futures::stream::Stream;
use serde::{Deserialize, Serialize};
use solverforge::Solvable;
use solverforge_maps::{BoundingBox, RoadNetwork, RoutingProgress};
use std::collections::HashMap;
use std::convert::Infallible;
use tokio::sync::mpsc;

use crate::demo_data::{self, DemoData};
use crate::dto::*;

#[derive(Debug, Deserialize)]
pub struct RoutingQuery {
    #[serde(default)]
    pub routing: Option<String>,
}

pub fn router() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/info", get(info))
        .route("/demo-data", get(list_demo_data))
        .route("/demo-data/{id}", get(get_demo_data))
        .route("/demo-data/{id}/stream", get(get_demo_data_stream))
        .route("/route-plans", post(solve_route_plan))
        .route("/route-plans/analyze", put(analyze_route_plan))
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

                let (tx, mut rx) = mpsc::channel::<RoutingProgress>(100);
                tokio::spawn(async move { while rx.recv().await.is_some() {} });

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

// SSE Event types
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
struct SseSolution {
    event: &'static str,
    solution: VehicleRoutePlanDto,
    score: String,
}

#[derive(Serialize)]
struct SseSolveComplete {
    event: &'static str,
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
            let progress = SseProgress { event: "progress", phase: "computing", message: "Computing distances...", percent: 50, detail: None };
            yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

            let progress = SseProgress { event: "progress", phase: "complete", message: "Ready!", percent: 100, detail: None };
            yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

            let dto = VehicleRoutePlanDto::from_plan(&plan, None);
            let complete = SseComplete { event: "complete", solution: dto };
            yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
        } else {
            let bbox = BoundingBox::new(
                plan.south_west_corner.0,
                plan.south_west_corner.1,
                plan.north_east_corner.0,
                plan.north_east_corner.1,
            );

            let (tx, mut rx) = mpsc::channel::<RoutingProgress>(100);
            let coordinates = plan.coordinates.clone();
            let compute_handle = tokio::spawn(async move {
                RoadNetwork::load_and_compute(&bbox, &coordinates, tx).await
            });

            while let Some(progress) = rx.recv().await {
                let (phase, message) = progress.phase_message();
                let sse_progress = SseProgress {
                    event: "progress",
                    phase,
                    message,
                    percent: progress.percent(),
                    detail: progress.detail(),
                };
                yield Ok(Event::default().data(serde_json::to_string(&sse_progress).unwrap()));
            }

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

/// SSE endpoint for solving. Streams:
/// 1. Progress events during road network loading (if real_roads)
/// 2. Solution events as solver finds better solutions
/// 3. Complete event when solver finishes
async fn solve_route_plan(
    Query(query): Query<RoutingQuery>,
    Json(dto): Json<VehicleRoutePlanDto>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let stream = async_stream::stream! {
        let mut plan = dto.to_domain();

        // 1. Load road network if requested (with progress streaming)
        let geometries = if query.routing.as_deref() == Some("real_roads") {
            let bbox = BoundingBox::new(
                plan.south_west_corner.0,
                plan.south_west_corner.1,
                plan.north_east_corner.0,
                plan.north_east_corner.1,
            );

            let (tx, mut rx) = mpsc::channel::<RoutingProgress>(100);
            let coordinates = plan.coordinates.clone();
            let compute_handle = tokio::spawn(async move {
                RoadNetwork::load_and_compute(&bbox, &coordinates, tx).await
            });

            // Stream progress events
            while let Some(progress) = rx.recv().await {
                let (phase, message) = progress.phase_message();
                let sse_progress = SseProgress {
                    event: "progress",
                    phase,
                    message,
                    percent: progress.percent(),
                    detail: progress.detail(),
                };
                yield Ok(Event::default().data(serde_json::to_string(&sse_progress).unwrap()));
            }

            match compute_handle.await {
                Ok(Ok(result)) => {
                    plan.travel_times = result.travel_times;
                    result.geometries
                }
                Ok(Err(e)) => {
                    let err = SseError { event: "error", message: format!("Failed to load road network: {}", e) };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                    return;
                }
                Err(e) => {
                    let err = SseError { event: "error", message: format!("Task panicked: {}", e) };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                    return;
                }
            }
        } else {
            HashMap::new()
        };

        // 2. Start solver with channel for solution updates
        // When the SSE stream closes, solver_rx is dropped, which closes the channel.
        // The solver detects sender.is_closed() and terminates automatically.
        let (solver_tx, mut solver_rx) = tokio::sync::mpsc::unbounded_channel();

        rayon::spawn(move || {
            plan.solve(None, solver_tx);
        });

        // 3. Stream solutions as they arrive
        while let Some((solution, score)) = solver_rx.recv().await {
            let dto = VehicleRoutePlanDto::from_plan_with_geometries(
                &solution,
                &geometries,
                Some("SOLVING".to_string()),
            );
            let event = SseSolution {
                event: "solution",
                solution: dto,
                score: format!("{}", score),
            };
            yield Ok(Event::default().data(serde_json::to_string(&event).unwrap()));
        }

        // 4. Solver finished (either naturally or because channel was closed)
        let complete = SseSolveComplete { event: "complete" };
        yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
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
