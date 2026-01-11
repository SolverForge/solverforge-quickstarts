//! Solver service for Vehicle Routing Problem.
//!
//! Uses the public SolverForge API.

use parking_lot::Mutex;
use std::collections::HashMap;
use std::sync::Arc;

use crate::domain::VehicleRoutePlan;
use solverforge::{run_solver_with_events, Score, SolverEvent};

use crate::constraints::define_constraints;

/// Status of a solving job.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SolverStatus {
    NotSolving,
    Solving,
}

impl SolverStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            SolverStatus::NotSolving => "NOT_SOLVING",
            SolverStatus::Solving => "SOLVING",
        }
    }
}

/// A solving job with current state.
pub struct SolveJob {
    pub id: String,
    pub status: SolverStatus,
    pub plan: VehicleRoutePlan,
}

impl SolveJob {
    pub fn new(id: String, plan: VehicleRoutePlan) -> Self {
        Self {
            id,
            status: SolverStatus::NotSolving,
            plan,
        }
    }
}

/// Manages VRP solving jobs.
pub struct SolverService {
    jobs: Mutex<HashMap<String, Arc<Mutex<SolveJob>>>>,
}

impl SolverService {
    pub fn new() -> Self {
        Self {
            jobs: Mutex::new(HashMap::new()),
        }
    }

    pub fn create_job(&self, id: String, plan: VehicleRoutePlan) -> Arc<Mutex<SolveJob>> {
        let job = Arc::new(Mutex::new(SolveJob::new(id.clone(), plan)));
        self.jobs.lock().insert(id, job.clone());
        job
    }

    pub fn get_job(&self, id: &str) -> Option<Arc<Mutex<SolveJob>>> {
        self.jobs.lock().get(id).cloned()
    }

    pub fn list_jobs(&self) -> Vec<String> {
        self.jobs.lock().keys().cloned().collect()
    }

    pub fn remove_job(&self, id: &str) -> Option<Arc<Mutex<SolveJob>>> {
        self.jobs.lock().remove(id)
    }

    pub fn start_solving(&self, job: Arc<Mutex<SolveJob>>) {
        job.lock().status = SolverStatus::Solving;

        let job_clone = job.clone();
        tokio::task::spawn_blocking(move || {
            solve_blocking(job_clone);
        });
    }

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

/// Runs the solver using the public SolverForge API.
fn solve_blocking(job: Arc<Mutex<SolveJob>>) {
    let initial_plan = job.lock().plan.clone();

    let job_for_callback = job.clone();
    let result = run_solver_with_events(
        initial_plan,
        VehicleRoutePlan::finalize_all,
        define_constraints,
        VehicleRoutePlan::list_get_element,
        VehicleRoutePlan::list_set_element,
        VehicleRoutePlan::element_count,
        VehicleRoutePlan::n_entities,
        VehicleRoutePlan::descriptor,
        VehicleRoutePlan::entity_count,
        |event| match event {
            SolverEvent::BestSolutionChanged { score, .. } => {
                println!("New best: {}", score);
            }
            SolverEvent::Ended { final_score, .. } => {
                println!("Finished: {} (feasible: {})", final_score, final_score.is_feasible());
            }
            _ => {}
        },
        move |best_solution, score| {
            let mut job_guard = job_for_callback.lock();
            job_guard.plan = best_solution.clone();
            job_guard.plan.score = Some(score);
        },
    );

    let mut job_guard = job.lock();
    job_guard.plan = result;
    job_guard.status = SolverStatus::NotSolving;
}
