//! Solver service for Employee Scheduling.
//!
//! Uses the public SolverForge API with fluent constraint definitions.

use parking_lot::Mutex;
use std::collections::HashMap;
use std::sync::Arc;

use crate::console;
use crate::domain::EmployeeSchedule;
use solverforge::{Score, SolverEvent};

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
/// assert_eq!(job.lock().status, employee_scheduling::solver::SolverStatus::NotSolving);
/// ```
pub struct SolverService {
    jobs: Mutex<HashMap<String, Arc<Mutex<SolveJob>>>>,
}

impl SolverService {
    /// Creates a new solver service.
    pub fn new() -> Self {
        Self {
            jobs: Mutex::new(HashMap::new()),
        }
    }

    /// Creates a new job for the given schedule.
    pub fn create_job(&self, id: String, schedule: EmployeeSchedule) -> Arc<Mutex<SolveJob>> {
        let job = Arc::new(Mutex::new(SolveJob::new(id.clone(), schedule)));
        self.jobs.lock().insert(id, job.clone());
        job
    }

    /// Gets a job by ID.
    pub fn get_job(&self, id: &str) -> Option<Arc<Mutex<SolveJob>>> {
        self.jobs.lock().get(id).cloned()
    }

    /// Lists all job IDs.
    pub fn list_jobs(&self) -> Vec<String> {
        self.jobs.lock().keys().cloned().collect()
    }

    /// Removes a job by ID.
    pub fn remove_job(&self, id: &str) -> Option<Arc<Mutex<SolveJob>>> {
        self.jobs.lock().remove(id)
    }

    /// Starts solving a job in the background.
    pub fn start_solving(&self, job: Arc<Mutex<SolveJob>>) {
        job.lock().status = SolverStatus::Solving;

        let job_clone = job.clone();
        tokio::task::spawn_blocking(move || {
            solve_blocking(job_clone);
        });
    }

    /// Stops a solving job.
    pub fn stop_solving(&self, id: &str) -> bool {
        if let Some(job) = self.get_job(id) {
            job.lock().status = SolverStatus::NotSolving;
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
fn solve_blocking(job: Arc<Mutex<SolveJob>>) {
    let initial_schedule = job.lock().schedule.clone();

    // Use solve_with_events for full console output
    let job_for_callback = job.clone();
    let result = initial_schedule.solve_with_events(
        // Event handler for console output
        |event| match event {
            SolverEvent::Started { entity_count, variable_count, value_count } => {
                console::print_solving_started(0, "?", entity_count, variable_count, value_count);
            }
            SolverEvent::PhaseStarted { phase_index, phase_name } => {
                console::print_phase_start(phase_name, phase_index);
            }
            SolverEvent::PhaseEnded { phase_index, phase_name, duration, steps, moves_evaluated, best_score } => {
                console::print_phase_end(phase_name, phase_index, duration, steps, moves_evaluated, &format!("{}", best_score));
            }
            SolverEvent::BestSolutionChanged { step, elapsed, moves_evaluated, score } => {
                console::print_step_progress(step, elapsed, moves_evaluated, &format!("{}", score));
            }
            SolverEvent::Ended { duration, total_moves, phase_count, final_score } => {
                let is_feasible = final_score.is_feasible();
                console::print_solving_ended(duration, total_moves, phase_count, &format!("{}", final_score), is_feasible);
            }
        },
        // Best solution handler for job updates
        move |best_solution, score| {
            let mut job_guard = job_for_callback.lock();
            job_guard.schedule = best_solution.clone();
            job_guard.schedule.score = Some(score);
        },
    );

    // Update job with final result
    let mut job_guard = job.lock();
    job_guard.schedule = result;
    job_guard.status = SolverStatus::NotSolving;
}
