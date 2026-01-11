//! REST API handlers for Employee Scheduling.

use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{delete, get, post, put},
    Json, Router,
};
use chrono::{NaiveDate, NaiveDateTime};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, RwLock};

use crate::demo_data::{self, DemoData};
use crate::domain::{Employee, EmployeeSchedule, Shift};
use crate::solver::{solver_manager, SolverStatus};

/// Application state shared across handlers.
///
/// Stores active jobs and their latest solutions.
pub struct AppState {
    /// Maps job_id string -> (slot_index, latest_solution)
    jobs: RwLock<HashMap<String, (usize, Option<EmployeeSchedule>)>>,
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

// ============================================================================
// DTOs
// ============================================================================

/// Employee DTO for API requests/responses.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EmployeeDto {
    pub name: String,
    pub skills: Vec<String>,
    #[serde(default)]
    pub unavailable_dates: Vec<NaiveDate>,
    #[serde(default)]
    pub undesired_dates: Vec<NaiveDate>,
    #[serde(default)]
    pub desired_dates: Vec<NaiveDate>,
}

impl From<&Employee> for EmployeeDto {
    fn from(e: &Employee) -> Self {
        Self {
            name: e.name.clone(),
            skills: e.skills.iter().cloned().collect(),
            unavailable_dates: e.unavailable_dates.iter().cloned().collect(),
            undesired_dates: e.undesired_dates.iter().cloned().collect(),
            desired_dates: e.desired_dates.iter().cloned().collect(),
        }
    }
}

impl EmployeeDto {
    fn to_employee(&self, index: usize) -> Employee {
        let unavailable_dates: HashSet<NaiveDate> =
            self.unavailable_dates.iter().cloned().collect();
        let undesired_dates: HashSet<NaiveDate> = self.undesired_dates.iter().cloned().collect();
        let desired_dates: HashSet<NaiveDate> = self.desired_dates.iter().cloned().collect();

        let mut unavailable_days: Vec<NaiveDate> = unavailable_dates.iter().copied().collect();
        unavailable_days.sort();
        let mut undesired_days: Vec<NaiveDate> = undesired_dates.iter().copied().collect();
        undesired_days.sort();
        let mut desired_days: Vec<NaiveDate> = desired_dates.iter().copied().collect();
        desired_days.sort();

        Employee {
            index,
            name: self.name.clone(),
            skills: self.skills.iter().cloned().collect(),
            unavailable_dates,
            undesired_dates,
            desired_dates,
            unavailable_days,
            undesired_days,
            desired_days,
        }
    }
}

/// Shift DTO with embedded Employee object.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ShiftDto {
    pub id: String,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
    pub location: String,
    pub required_skill: String,
    pub employee: Option<EmployeeDto>,
}

/// Full schedule DTO for request/response.
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduleDto {
    pub employees: Vec<EmployeeDto>,
    pub shifts: Vec<ShiftDto>,
    #[serde(default)]
    pub score: Option<String>,
    #[serde(default)]
    pub solver_status: Option<SolverStatus>,
}

impl ScheduleDto {
    pub fn from_schedule(schedule: &EmployeeSchedule, status: Option<SolverStatus>) -> Self {
        let employees: Vec<EmployeeDto> = schedule.employees.iter().map(EmployeeDto::from).collect();

        let shifts: Vec<ShiftDto> = schedule
            .shifts
            .iter()
            .map(|s| ShiftDto {
                id: s.id.clone(),
                start: s.start,
                end: s.end,
                location: s.location.clone(),
                required_skill: s.required_skill.clone(),
                employee: s
                    .employee_idx
                    .and_then(|idx| schedule.employees.get(idx))
                    .map(EmployeeDto::from),
            })
            .collect();

        Self {
            employees,
            shifts,
            score: schedule.score.map(|s| format!("{}", s)),
            solver_status: status,
        }
    }

    pub fn to_domain(&self) -> EmployeeSchedule {
        // Build employees with their indices set correctly
        let employees: Vec<Employee> = self
            .employees
            .iter()
            .enumerate()
            .map(|(i, dto)| dto.to_employee(i))
            .collect();
        let name_to_idx: std::collections::HashMap<&str, usize> = employees
            .iter()
            .map(|e| (e.name.as_str(), e.index))
            .collect();

        let shifts: Vec<Shift> = self
            .shifts
            .iter()
            .map(|s| Shift {
                id: s.id.clone(),
                start: s.start,
                end: s.end,
                location: s.location.clone(),
                required_skill: s.required_skill.clone(),
                employee_idx: s
                    .employee
                    .as_ref()
                    .and_then(|e| name_to_idx.get(e.name.as_str()).copied()),
            })
            .collect();

        EmployeeSchedule::new(employees, shifts)
    }
}

// ============================================================================
// Router and Handlers
// ============================================================================

/// Creates the API router.
pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        // Health & Info
        .route("/health", get(health))
        .route("/info", get(info))
        // Demo data
        .route("/demo-data", get(list_demo_data))
        .route("/demo-data/{id}", get(get_demo_data))
        // Schedules
        .route("/schedules", post(create_schedule))
        .route("/schedules", get(list_schedules))
        .route("/schedules/analyze", put(analyze_schedule))
        .route("/schedules/{id}", get(get_schedule))
        .route("/schedules/{id}/status", get(get_schedule_status))
        .route("/schedules/{id}", delete(stop_solving))
        .with_state(state)
}

// ============================================================================
// Health & Info
// ============================================================================

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
}

/// GET /health - Health check endpoint.
async fn health() -> Json<HealthResponse> {
    Json(HealthResponse { status: "UP" })
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InfoResponse {
    pub name: &'static str,
    pub version: &'static str,
    pub solver_engine: &'static str,
}

/// GET /info - Application info endpoint.
async fn info() -> Json<InfoResponse> {
    Json(InfoResponse {
        name: "Employee Scheduling",
        version: env!("CARGO_PKG_VERSION"),
        solver_engine: "SolverForge-RS",
    })
}

/// GET /demo-data - List available demo data sets.
async fn list_demo_data() -> Json<Vec<&'static str>> {
    Json(demo_data::list_demo_data())
}

/// GET /demo-data/{id} - Get a specific demo data set.
async fn get_demo_data(Path(id): Path<String>) -> Result<Json<ScheduleDto>, StatusCode> {
    match id.parse::<DemoData>() {
        Ok(demo) => {
            let schedule = demo_data::generate(demo);
            Ok(Json(ScheduleDto::from_schedule(&schedule, None)))
        }
        Err(_) => Err(StatusCode::NOT_FOUND),
    }
}

/// POST /schedules - Create and start solving a schedule.
/// Returns the job ID as plain text.
async fn create_schedule(
    State(state): State<Arc<AppState>>,
    Json(dto): Json<ScheduleDto>,
) -> String {
    let id = uuid::Uuid::new_v4().to_string();
    let schedule = dto.to_domain();

    // Start solving and get receiver
    let (slot_idx, mut receiver) = solver_manager().solve(schedule);

    // Store job mapping
    {
        let mut jobs = state.jobs.write().unwrap();
        jobs.insert(id.clone(), (slot_idx, None));
    }

    // Spawn task to receive solutions and update state
    let state_clone = state.clone();
    let id_clone = id.clone();
    tokio::spawn(async move {
        while let Some((solution, _score)) = receiver.recv().await {
            let mut jobs = state_clone.jobs.write().unwrap();
            if let Some((_, stored_solution)) = jobs.get_mut(&id_clone) {
                *stored_solution = Some(solution);
            }
        }
    });

    id
}

/// GET /schedules - List all schedule IDs.
async fn list_schedules(State(state): State<Arc<AppState>>) -> Json<Vec<String>> {
    let jobs = state.jobs.read().unwrap();
    Json(jobs.keys().cloned().collect())
}

/// GET /schedules/{id} - Get a schedule's current state.
async fn get_schedule(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<ScheduleDto>, StatusCode> {
    let jobs = state.jobs.read().unwrap();
    match jobs.get(&id) {
        Some((slot_idx, Some(schedule))) => {
            let status = solver_manager().get_status(*slot_idx);
            Ok(Json(ScheduleDto::from_schedule(schedule, Some(status))))
        }
        Some((_, None)) => Err(StatusCode::NO_CONTENT), // Solving started but no solution yet
        None => Err(StatusCode::NOT_FOUND),
    }
}

/// Response for schedule status only.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StatusResponse {
    pub score: Option<String>,
    pub solver_status: SolverStatus,
}

/// GET /schedules/{id}/status - Get a schedule's status.
async fn get_schedule_status(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<StatusResponse>, StatusCode> {
    let jobs = state.jobs.read().unwrap();
    match jobs.get(&id) {
        Some((slot_idx, schedule)) => Ok(Json(StatusResponse {
            score: schedule.as_ref().and_then(|s| s.score.map(|sc| format!("{}", sc))),
            solver_status: solver_manager().get_status(*slot_idx),
        })),
        None => Err(StatusCode::NOT_FOUND),
    }
}

/// DELETE /schedules/{id} - Stop solving and remove a schedule.
async fn stop_solving(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> StatusCode {
    let slot_idx = {
        let jobs = state.jobs.read().unwrap();
        jobs.get(&id).map(|(idx, _)| *idx)
    };

    match slot_idx {
        Some(idx) => {
            solver_manager().terminate_early(idx);
            solver_manager().free_slot(idx);

            let mut jobs = state.jobs.write().unwrap();
            jobs.remove(&id);
            StatusCode::NO_CONTENT
        }
        None => StatusCode::NOT_FOUND,
    }
}

/// Constraint analysis result.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConstraintAnalysisDto {
    pub name: String,
    #[serde(rename = "type")]
    pub constraint_type: String,
    pub weight: String,
    pub score: String,
    pub matches: Vec<ConstraintMatchDto>,
}

/// A single constraint match.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConstraintMatchDto {
    pub score: String,
    pub justification: String,
}

/// Response for constraint analysis.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AnalyzeResponse {
    pub score: String,
    pub constraints: Vec<ConstraintAnalysisDto>,
}

/// PUT /schedules/analyze - Analyze constraints for a schedule.
///
/// Uses the SolutionManager.analyze() API.
async fn analyze_schedule(Json(dto): Json<ScheduleDto>) -> Json<AnalyzeResponse> {
    use crate::solver::solution_manager;

    let schedule = dto.to_domain();

    // Use public API for constraint analysis
    let analysis = solution_manager().analyze(&schedule);

    let constraints_dto: Vec<ConstraintAnalysisDto> = analysis
        .constraints
        .into_iter()
        .map(|c| ConstraintAnalysisDto {
            name: c.name,
            constraint_type: "soft".to_string(), // HardSoftScore doesn't track this per-constraint
            weight: format!("{}", c.weight),
            score: format!("{}", c.score),
            matches: Vec::new(), // Simplified - detailed matches not exposed yet
        })
        .collect();

    Json(AnalyzeResponse {
        score: format!("{}", analysis.score),
        constraints: constraints_dto,
    })
}
