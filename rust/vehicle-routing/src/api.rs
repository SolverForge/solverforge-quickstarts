//! REST API handlers for Vehicle Routing.

use axum::{
    extract::Path,
    http::StatusCode,
    response::sse::{Event, KeepAlive, Sse},
    routing::{get, post, put},
    Json, Router,
};
use futures::stream::Stream;
use serde::Serialize;
use solverforge::Solvable;
use solverforge_maps::{BoundingBox, NetworkConfig, RoadNetwork, RoutingProgress};
use std::convert::Infallible;
use tokio::sync::mpsc;
use tokio_util::sync::CancellationToken;

use crate::demo_data::{self, DemoData};
use crate::dto::*;

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
) -> Result<Json<VehicleRoutePlanDto>, (StatusCode, String)> {
    match id.parse::<DemoData>() {
        Ok(demo) => {
            let mut plan = demo_data::generate(demo);
            let bbox =
                BoundingBox::from_coords(&plan.coordinates).expand_for_routing(&plan.coordinates);
            let config = NetworkConfig::default();

            let network = RoadNetwork::load_or_fetch(&bbox, &config, None)
                .await
                .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

            plan.travel_times = network.compute_matrix(&plan.coordinates, None).await;

            let unreachable = plan.travel_times.unreachable_pairs();
            if !unreachable.is_empty() {
                return Err((
                    StatusCode::BAD_REQUEST,
                    format!("{} location pairs are unreachable", unreachable.len()),
                ));
            }

            plan.geometries = network.compute_geometries(&plan.coordinates, None).await;
            Ok(Json(VehicleRoutePlanDto::from_plan(&plan, None)))
        }
        Err(_) => Err((StatusCode::NOT_FOUND, "Demo not found".to_string())),
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

struct CancelOnDrop(CancellationToken);

impl Drop for CancelOnDrop {
    fn drop(&mut self) {
        self.0.cancel();
    }
}

async fn get_demo_data_stream(
    Path(id): Path<String>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let cancel = CancellationToken::new();
    let cancel_guard = CancelOnDrop(cancel.clone());

    let stream = async_stream::stream! {
        let _guard = cancel_guard;

        let demo = match id.parse::<DemoData>() {
            Ok(d) => d,
            Err(_) => {
                let err = SseError { event: "error", message: format!("Demo data not found: {}", id) };
                yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                return;
            }
        };

        let mut plan = demo_data::generate(demo);
        let bbox = BoundingBox::from_coords(&plan.coordinates)
            .expand_for_routing(&plan.coordinates);
        let config = NetworkConfig::default();

        let (tx, mut rx) = mpsc::channel::<RoutingProgress>(1);
        let coordinates = plan.coordinates.clone();
        let task_cancel = cancel.clone();

        let compute_handle = tokio::spawn(async move {
            tokio::select! {
                biased;
                _ = task_cancel.cancelled() => {
                    Err(solverforge_maps::RoutingError::Cancelled)
                }
                result = async {
                    let network = RoadNetwork::load_or_fetch(&bbox, &config, Some(&tx)).await?;
                    let matrix = network.compute_matrix(&coordinates, Some(&tx)).await;
                    let geometries = network.compute_geometries(&coordinates, Some(&tx)).await;
                    Ok::<_, solverforge_maps::RoutingError>((matrix, geometries))
                } => result
            }
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
            Ok(Ok((matrix, geometries))) => {
                plan.travel_times = matrix;

                let unreachable = plan.travel_times.unreachable_pairs();
                if !unreachable.is_empty() {
                    let err = SseError {
                        event: "error",
                        message: format!("{} location pairs are unreachable", unreachable.len())
                    };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                    return;
                }

                plan.geometries = geometries;

                let progress = SseProgress { event: "progress", phase: "complete", message: "Ready!", percent: 100, detail: None };
                yield Ok(Event::default().data(serde_json::to_string(&progress).unwrap()));

                let dto = VehicleRoutePlanDto::from_plan(&plan, None);
                let complete = SseComplete { event: "complete", solution: dto };
                yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
            }
            Ok(Err(solverforge_maps::RoutingError::Cancelled)) => {
                return;
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
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

async fn solve_route_plan(
    Json(dto): Json<VehicleRoutePlanDto>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let cancel = CancellationToken::new();
    let cancel_guard = CancelOnDrop(cancel.clone());

    let stream = async_stream::stream! {
        let _guard = cancel_guard;
        let mut plan = dto.to_domain();

        let bbox = BoundingBox::from_coords(&plan.coordinates)
            .expand_for_routing(&plan.coordinates);
        let config = NetworkConfig::default();

        let (tx, mut rx) = mpsc::channel::<RoutingProgress>(1);
        let coordinates = plan.coordinates.clone();
        let task_cancel = cancel.clone();

        let compute_handle = tokio::spawn(async move {
            tokio::select! {
                biased;
                _ = task_cancel.cancelled() => {
                    Err(solverforge_maps::RoutingError::Cancelled)
                }
                result = async {
                    let network = RoadNetwork::load_or_fetch(&bbox, &config, Some(&tx)).await?;
                    let matrix = network.compute_matrix(&coordinates, Some(&tx)).await;
                    let geometries = network.compute_geometries(&coordinates, Some(&tx)).await;
                    Ok::<_, solverforge_maps::RoutingError>((matrix, geometries))
                } => result
            }
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
            Ok(Ok((matrix, geometries))) => {
                plan.travel_times = matrix;

                let unreachable = plan.travel_times.unreachable_pairs();
                if !unreachable.is_empty() {
                    let err = SseError {
                        event: "error",
                        message: format!("{} location pairs are unreachable", unreachable.len())
                    };
                    yield Ok(Event::default().data(serde_json::to_string(&err).unwrap()));
                    return;
                }

                plan.geometries = geometries;
            }
            Ok(Err(solverforge_maps::RoutingError::Cancelled)) => {
                return;
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
        };

        let (solver_tx, mut solver_rx) = tokio::sync::mpsc::unbounded_channel();

        rayon::spawn(move || {
            plan.solve(None, solver_tx);
        });

        while let Some((solution, score)) = solver_rx.recv().await {
            let dto = VehicleRoutePlanDto::from_plan(&solution, Some("SOLVING".to_string()));
            let event = SseSolution {
                event: "solution",
                solution: dto,
                score: format!("{}", score),
            };
            yield Ok(Event::default().data(serde_json::to_string(&event).unwrap()));
        }

        let complete = SseSolveComplete { event: "complete" };
        yield Ok(Event::default().data(serde_json::to_string(&complete).unwrap()));
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

async fn analyze_route_plan(Json(dto): Json<VehicleRoutePlanDto>) -> Json<AnalyzeResponse> {
    use crate::constraints::define_constraints;
    use solverforge::{ConstraintSet, ScoreDirector};

    let plan = dto.to_domain();
    let constraints = define_constraints();
    let mut director = ScoreDirector::new(plan, constraints);
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
