//! REST API for Vehicle Routing Problem.

use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{delete, get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use uuid::Uuid;

use crate::demo_data::generate_philadelphia;
use crate::domain::VehicleRoutePlan;
use crate::solver::{SolverService, SolverStatus};

pub struct AppState {
    pub solver: SolverService,
}

pub fn create_router() -> Router {
    let state = Arc::new(AppState {
        solver: SolverService::new(),
    });

    Router::new()
        .route("/health", get(health))
        .route("/demo-data", get(demo_data))
        .route("/route-plans", post(create_job))
        .route("/route-plans/{id}", get(get_job))
        .route("/route-plans/{id}", delete(stop_job))
        .layer(CorsLayer::new().allow_origin(Any).allow_methods(Any).allow_headers(Any))
        .with_state(state)
}

#[derive(Serialize)]
struct Health { status: &'static str }

async fn health() -> Json<Health> {
    Json(Health { status: "UP" })
}

async fn demo_data() -> Json<VehicleRoutePlan> {
    Json(generate_philadelphia())
}

async fn create_job(
    State(state): State<Arc<AppState>>,
    Json(mut plan): Json<VehicleRoutePlan>,
) -> String {
    let id = Uuid::new_v4().to_string();
    plan.finalize();
    let job = state.solver.create_job(id.clone(), plan);
    state.solver.start_solving(job);
    id
}

async fn get_job(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<JobResponse>, StatusCode> {
    match state.solver.get_job(&id) {
        Some(job) => {
            let guard = job.read();
            Ok(Json(JobResponse {
                plan: guard.plan.clone(),
                status: guard.status,
            }))
        }
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn stop_job(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<VehicleRoutePlan>, StatusCode> {
    state.solver.stop_solving(&id);
    match state.solver.remove_job(&id) {
        Some(job) => Ok(Json(job.read().plan.clone())),
        None => Err(StatusCode::NOT_FOUND),
    }
}

#[derive(Serialize, Deserialize)]
struct JobResponse {
    plan: VehicleRoutePlan,
    status: SolverStatus,
}
