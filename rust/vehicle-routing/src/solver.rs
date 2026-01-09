//! Solver service for Vehicle Routing Problem.
//!
//! Zero-wiring API: `solution.solve()` with constraints embedded via macro.

use parking_lot::RwLock;
use solverforge::Score;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::oneshot;
use tracing::info;

use crate::console;
use crate::domain::VehicleRoutePlan;

/// Default solving time: 30 seconds.
const DEFAULT_TIME_LIMIT_SECS: u64 = 30;

/// Solver configuration with termination criteria.
#[derive(Debug, Clone, Default)]
pub struct SolverConfig {
    /// Stop after this duration.
    pub time_limit: Option<Duration>,
    /// Stop after this many steps.
    pub step_limit: Option<u64>,
}

impl SolverConfig {
    /// Creates a config with default 30-second time limit.
    pub fn default_config() -> Self {
        Self {
            time_limit: Some(Duration::from_secs(DEFAULT_TIME_LIMIT_SECS)),
            ..Default::default()
        }
    }
}

/// Status of a solving job.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SolverStatus {
    /// Not currently solving.
    NotSolving,
    /// Actively solving.
    Solving,
}

impl SolverStatus {
    /// Returns the status as a SCREAMING_SNAKE_CASE string for API responses.
    ///
    /// ```
    /// use vehicle_routing::solver::SolverStatus;
    ///
    /// assert_eq!(SolverStatus::NotSolving.as_str(), "NOT_SOLVING");
    /// assert_eq!(SolverStatus::Solving.as_str(), "SOLVING");
    /// ```
    pub fn as_str(self) -> &'static str {
        match self {
            SolverStatus::NotSolving => "NOT_SOLVING",
            SolverStatus::Solving => "SOLVING",
        }
    }
}

/// A solving job with current state.
pub struct SolveJob {
    /// Unique job identifier.
    pub id: String,
    /// Current status.
    pub status: SolverStatus,
    /// Current best solution.
    pub plan: VehicleRoutePlan,
    /// Solver configuration.
    pub config: SolverConfig,
    /// Stop signal sender.
    stop_signal: Option<oneshot::Sender<()>>,
}

impl SolveJob {
    /// Creates a new solve job with default config.
    pub fn new(id: String, plan: VehicleRoutePlan) -> Self {
        Self {
            id,
            status: SolverStatus::NotSolving,
            plan,
            config: SolverConfig::default_config(),
            stop_signal: None,
        }
    }

    /// Creates a new solve job with custom config.
    pub fn with_config(id: String, plan: VehicleRoutePlan, config: SolverConfig) -> Self {
        Self {
            id,
            status: SolverStatus::NotSolving,
            plan,
            config,
            stop_signal: None,
        }
    }
}

/// Manages VRP solving jobs.
///
/// # Examples
///
/// ```
/// use vehicle_routing::solver::SolverService;
/// use vehicle_routing::demo_data::generate_philadelphia;
///
/// let service = SolverService::new();
/// let plan = generate_philadelphia();
///
/// // Create a job (doesn't start solving yet)
/// let job = service.create_job("test-1".to_string(), plan);
/// assert_eq!(job.read().status, vehicle_routing::solver::SolverStatus::NotSolving);
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

    /// Creates a new job for the given plan with default config.
    pub fn create_job(&self, id: String, plan: VehicleRoutePlan) -> Arc<RwLock<SolveJob>> {
        let job = Arc::new(RwLock::new(SolveJob::new(id.clone(), plan)));
        self.jobs.write().insert(id, job.clone());
        job
    }

    /// Creates a new job with custom config.
    pub fn create_job_with_config(
        &self,
        id: String,
        plan: VehicleRoutePlan,
        config: SolverConfig,
    ) -> Arc<RwLock<SolveJob>> {
        let job = Arc::new(RwLock::new(SolveJob::with_config(id.clone(), plan, config)));
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
        let (tx, rx) = oneshot::channel();
        let config = job.read().config.clone();

        {
            let mut job_guard = job.write();
            job_guard.status = SolverStatus::Solving;
            job_guard.stop_signal = Some(tx);
        }

        let job_clone = job.clone();

        tokio::task::spawn_blocking(move || {
            solve_blocking(job_clone, rx, config);
        });
    }

    /// Stops a solving job.
    pub fn stop_solving(&self, id: &str) -> bool {
        if let Some(job) = self.get_job(id) {
            let mut job_guard = job.write();
            if let Some(stop_signal) = job_guard.stop_signal.take() {
                let _ = stop_signal.send(());
                job_guard.status = SolverStatus::NotSolving;
                return true;
            }
        }
        false
    }
}

impl Default for SolverService {
    fn default() -> Self {
        Self::new()
    }
}

/// Runs the solver in a blocking context.
///
/// Zero-wiring: constraints embedded via macro attribute on domain type.
fn solve_blocking(
    job: Arc<RwLock<SolveJob>>,
    mut stop_rx: oneshot::Receiver<()>,
    config: SolverConfig,
) {
    let solution = job.read().plan.clone();
    let job_id = job.read().id.clone();
    let solve_start = Instant::now();

    // Print problem configuration
    console::print_config(
        solution.vehicles.len(),
        solution.visits.len(),
        solution.locations.len(),
    );

    info!(
        job_id = %job_id,
        visits = solution.visits.len(),
        vehicles = solution.vehicles.len(),
        "Starting VRP solver"
    );

    let n_vehicles = solution.vehicles.len();
    let n_visits = solution.visits.len();

    if n_vehicles == 0 {
        info!("No vehicles to optimize");
        console::print_solving_ended(
            solve_start.elapsed(),
            0,
            0,
            "0hard/0soft",
            true,
        );
        finish_job(&job, &solution);
        return;
    }

    // Set up termination flag for stop signal and time limit
    let terminate_flag = Arc::new(AtomicBool::new(false));
    let terminate_flag_clone = terminate_flag.clone();
    let time_limit = config.time_limit;
    std::thread::spawn(move || {
        let deadline = time_limit.map(|d| Instant::now() + d);
        loop {
            if stop_rx.try_recv().is_ok() {
                terminate_flag_clone.store(true, Ordering::SeqCst);
                break;
            }
            if let Some(deadline) = deadline {
                if Instant::now() >= deadline {
                    terminate_flag_clone.store(true, Ordering::SeqCst);
                    break;
                }
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    });

    // Zero-wiring: constraints embedded via macro attribute
    let final_solution = VehicleRoutePlan::solve_with_terminate(solution, Some(terminate_flag));

    let total_duration = solve_start.elapsed();
    let final_score = final_solution.score.unwrap_or_default();

    info!(
        job_id = %job_id,
        duration_secs = total_duration.as_secs_f64(),
        score = %final_score,
        feasible = final_score.is_feasible(),
        "Solving complete"
    );

    // Print solving started (after construction phase completes internally)
    console::print_solving_started(
        total_duration.as_millis() as u64,
        &final_score.to_string(),
        n_visits,
        n_visits,
        n_vehicles,
    );

    console::print_solving_ended(
        total_duration,
        0, // Step count tracked internally
        2, // Two phases
        &final_score.to_string(),
        final_score.is_feasible(),
    );

    finish_job(&job, &final_solution);
}

/// Finishes job and sets status.
fn finish_job(job: &Arc<RwLock<SolveJob>>, solution: &VehicleRoutePlan) {
    let mut job_guard = job.write();
    job_guard.plan = solution.clone();
    job_guard.status = SolverStatus::NotSolving;
}

#[cfg(test)]
mod tests {
    use crate::demo_data::generate_philadelphia;

    #[test]
    fn test_solver_makes_progress() {
        let mut solution = generate_philadelphia();
        solution.finalize();

        // Zero-wiring: constraints embedded via macro attribute
        let final_solution = solution.solve();

        // Verify visits are assigned
        let total_visits: usize = final_solution
            .vehicles
            .iter()
            .map(|v| v.visits.len())
            .sum();
        assert_eq!(total_visits, 49); // Philadelphia has 49 visits

        // Verify solution has a score
        assert!(final_solution.score.is_some());
        eprintln!("Final score: {:?}", final_solution.score);
    }
}
