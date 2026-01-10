//! Solver service for Employee Scheduling.
//!
//! Uses the public SolverForge API with fluent constraint definitions.

use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::info;

use crate::domain::EmployeeSchedule;

/// Status of a solving job.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SolverStatus {
    /// Not currently solving.
    NotSolving,
    /// Actively solving.
    Solving,
}


/// A solving job with current state.
pub struct SolveJob {
    /// Unique job identifier.
    pub id: String,
    /// Current status.
    pub status: SolverStatus,
    /// Current best schedule.
    pub schedule: EmployeeSchedule,
}

impl SolveJob {
    /// Creates a new solve job.
    pub fn new(id: String, schedule: EmployeeSchedule) -> Self {
        Self {
            id,
            status: SolverStatus::NotSolving,
            schedule,
        }
    }
}

/// Manages Employee Scheduling solving jobs.
///
/// # Examples
///
/// ```
/// use employee_scheduling::solver::SolverService;
/// use employee_scheduling::demo_data::{generate, DemoData};
///
/// let service = SolverService::new();
/// let schedule = generate(DemoData::Small);
///
/// // Create a job (doesn't start solving yet)
/// let job = service.create_job("test-1".to_string(), schedule);
/// assert_eq!(job.read().status, employee_scheduling::solver::SolverStatus::NotSolving);
/// ```
pub struct SolverService {
    jobs: RwLock<HashMap<String, Arc<RwLock<SolveJob>>>>,
}

impl SolverService {
    /// Creates a new solver service.
    pub fn new() -> Self {
        Self {
            jobs: RwLock::new(HashMap::new()),
        }
    }

    /// Creates a new job for the given schedule.
    pub fn create_job(&self, id: String, schedule: EmployeeSchedule) -> Arc<RwLock<SolveJob>> {
        let job = Arc::new(RwLock::new(SolveJob::new(id.clone(), schedule)));
        self.jobs.write().insert(id, job.clone());
        job
    }

    /// Gets a job by ID.
    pub fn get_job(&self, id: &str) -> Option<Arc<RwLock<SolveJob>>> {
        self.jobs.read().get(id).cloned()
    }

    /// Lists all job IDs.
    pub fn list_jobs(&self) -> Vec<String> {
        self.jobs.read().keys().cloned().collect()
    }

    /// Removes a job by ID.
    pub fn remove_job(&self, id: &str) -> Option<Arc<RwLock<SolveJob>>> {
        self.jobs.write().remove(id)
    }

    /// Starts solving a job in the background.
    pub fn start_solving(&self, job: Arc<RwLock<SolveJob>>) {
        {
            let mut job_guard = job.write();
            job_guard.status = SolverStatus::Solving;
        }

        let job_clone = job.clone();

        tokio::task::spawn_blocking(move || {
            solve_blocking(job_clone);
        });
    }

    /// Stops a solving job.
    /// Note: Since solve() is blocking and doesn't support cancellation,
    /// this only marks the job as stopped - it won't interrupt active solving.
    pub fn stop_solving(&self, id: &str) -> bool {
        if let Some(job) = self.get_job(id) {
            let mut job_guard = job.write();
            job_guard.status = SolverStatus::NotSolving;
            true
        } else {
            false
        }
    }
}

impl Default for SolverService {
    fn default() -> Self {
        Self::new()
    }
}

/// Runs the solver in a blocking context using the public SolverForge API.
fn solve_blocking(job: Arc<RwLock<SolveJob>>) {
    let initial_schedule = job.read().schedule.clone();
    let job_id = job.read().id.clone();

    info!(
        job_id = %job_id,
        shifts = initial_schedule.shifts.len(),
        employees = initial_schedule.employees.len(),
        "Starting Employee Scheduling solver"
    );

    // Use public API - solve() loads solver.toml and runs construction + local search
    let result = initial_schedule.solve();

    info!(
        job_id = %job_id,
        score = ?result.score,
        "Solving complete"
    );

    // Update job with final result
    let mut job_guard = job.write();
    job_guard.schedule = result;
    job_guard.status = SolverStatus::NotSolving;
}
