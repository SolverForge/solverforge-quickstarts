//! Solver service for Vehicle Routing Problem.
//!
//! Uses Late Acceptance local search with list-change moves for route optimization.
//! Imports only from the `solverforge` umbrella crate.

use parking_lot::RwLock;
use solverforge::{
    // Core types
    prelude::*,
    // Phase infrastructure
    FirstAcceptedForager, LateAcceptanceAcceptor, ListChangeMove, ListChangeMoveSelector,
    LocalSearchPhase, Phase, SolverScope,
    // Selectors
    FromSolutionEntitySelector,
    // Shadow variable support
    ShadowAwareScoreDirector,
};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::oneshot;
use tracing::info;

use crate::console::{self, PhaseTimer};
use crate::constraints::{calculate_score, define_constraints};
use crate::domain::{visits_insert, visits_len, visits_remove, VehicleRoutePlan};

/// Default solving time: 30 seconds.
const DEFAULT_TIME_LIMIT_SECS: u64 = 30;

/// Late acceptance history size.
const LATE_ACCEPTANCE_SIZE: usize = 400;

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
fn solve_blocking(
    job: Arc<RwLock<SolveJob>>,
    mut stop_rx: oneshot::Receiver<()>,
    config: SolverConfig,
) {
    let mut solution = job.read().plan.clone();
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

    // Phase 1: Construction heuristic (round-robin)
    let mut ch_timer = PhaseTimer::start("ConstructionHeuristic", 0);
    let current_score = construction_heuristic(&mut solution, &mut ch_timer);
    ch_timer.finish();

    // Print solving started after construction
    console::print_solving_started(
        solve_start.elapsed().as_millis() as u64,
        &current_score.to_string(),
        solution.visits.len(),
        solution.visits.len(),
        solution.vehicles.len(),
    );

    // Update job with constructed solution
    update_job(&job, &solution, current_score);

    // Phase 2: Late Acceptance local search with list-change moves
    let n_vehicles = solution.vehicles.len();
    if n_vehicles == 0 {
        info!("No vehicles to optimize");
        console::print_solving_ended(
            solve_start.elapsed(),
            0,
            1,
            &current_score.to_string(),
            current_score.is_feasible(),
        );
        finish_job(&job, &solution, current_score);
        return;
    }

    let ls_timer = PhaseTimer::start("LateAcceptance", 1);

    // Create entity selector for all vehicles
    let entity_selector = FromSolutionEntitySelector::new(0);

    // Create list-change move selector
    let move_selector: ListChangeMoveSelector<VehicleRoutePlan, usize> = ListChangeMoveSelector::new(
        Box::new(entity_selector),
        visits_len,
        visits_remove,
        visits_insert,
        "visits",
        0,
    );

    // Create acceptor and forager
    let acceptor = LateAcceptanceAcceptor::<VehicleRoutePlan>::new(LATE_ACCEPTANCE_SIZE);
    let forager = FirstAcceptedForager::<VehicleRoutePlan, ListChangeMove<VehicleRoutePlan, usize>>::new();

    // Create local search phase
    let mut phase = LocalSearchPhase::new(
        Box::new(move_selector),
        Box::new(acceptor),
        Box::new(forager),
        config.step_limit,
    );

    // Create score director with shadow variable support
    let descriptor = crate::domain::create_solution_descriptor();
    let constraints = define_constraints();
    let score_calculator = move |plan: &VehicleRoutePlan| constraints.evaluate_all(plan);
    let inner_director =
        SimpleScoreDirector::with_calculator(solution, descriptor, score_calculator);
    let director = ShadowAwareScoreDirector::new(inner_director);

    // Create solver scope
    let mut solver_scope = SolverScope::new(Box::new(director));

    // Set up termination flag for stop signal
    let terminate_flag = Arc::new(AtomicBool::new(false));
    solver_scope.set_terminate_early_flag(terminate_flag.clone());

    // Spawn task to handle stop signal
    let terminate_flag_clone = terminate_flag.clone();
    let time_limit = config.time_limit;
    std::thread::spawn(move || {
        // Wait for either stop signal or timeout
        let deadline = time_limit.map(|d| Instant::now() + d);
        loop {
            // Check stop signal (non-blocking)
            if stop_rx.try_recv().is_ok() {
                terminate_flag_clone.store(true, Ordering::SeqCst);
                break;
            }
            // Check timeout
            if let Some(deadline) = deadline {
                if Instant::now() >= deadline {
                    terminate_flag_clone.store(true, Ordering::SeqCst);
                    break;
                }
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    });

    // Run local search phase
    phase.solve(&mut solver_scope);

    // Get stats before consuming timer
    let total_moves = ls_timer.moves_evaluated();
    ls_timer.finish();

    // Extract final solution
    let final_solution = solver_scope.working_solution().clone();
    let final_score = final_solution.score.unwrap_or(current_score);

    let total_duration = solve_start.elapsed();

    info!(
        job_id = %job_id,
        duration_secs = total_duration.as_secs_f64(),
        steps = total_moves,
        score = %final_score,
        feasible = final_score.is_feasible(),
        "Solving complete"
    );

    console::print_solving_ended(
        total_duration,
        total_moves,
        2,
        &final_score.to_string(),
        final_score.is_feasible(),
    );

    finish_job(&job, &final_solution, final_score);
}

/// Construction heuristic: round-robin visit assignment.
///
/// Skips construction if all visits are already assigned (continue mode).
fn construction_heuristic(solution: &mut VehicleRoutePlan, timer: &mut PhaseTimer) -> HardSoftScore {
    let n_visits = solution.visits.len();
    let n_vehicles = solution.vehicles.len();

    if n_vehicles == 0 || n_visits == 0 {
        return calculate_score(solution);
    }

    // Count already-assigned visits
    let assigned_count: usize = solution.vehicles.iter().map(|v| v.visits.len()).sum();

    // If all visits already assigned, skip construction (continue mode)
    if assigned_count == n_visits {
        info!("All visits already assigned, skipping construction heuristic");
        return calculate_score(solution);
    }

    // Build set of already-assigned visits
    let assigned: std::collections::HashSet<usize> = solution
        .vehicles
        .iter()
        .flat_map(|v| v.visits.iter().copied())
        .collect();

    // Round-robin assignment for unassigned visits only
    let mut vehicle_idx = 0;
    for visit_idx in 0..n_visits {
        if assigned.contains(&visit_idx) {
            continue;
        }

        timer.record_move();
        solution.vehicles[vehicle_idx].visits.push(visit_idx);

        let score = calculate_score(solution);
        timer.record_accepted(&score.to_string());

        vehicle_idx = (vehicle_idx + 1) % n_vehicles;
    }

    calculate_score(solution)
}

/// Updates job with current solution.
fn update_job(job: &Arc<RwLock<SolveJob>>, solution: &VehicleRoutePlan, score: HardSoftScore) {
    let mut job_guard = job.write();
    job_guard.plan = solution.clone();
    job_guard.plan.score = Some(score);
}

/// Finishes job and sets status.
fn finish_job(job: &Arc<RwLock<SolveJob>>, solution: &VehicleRoutePlan, score: HardSoftScore) {
    let mut job_guard = job.write();
    job_guard.plan = solution.clone();
    job_guard.plan.score = Some(score);
    job_guard.status = SolverStatus::NotSolving;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::demo_data::generate_philadelphia;

    #[test]
    fn test_construction_heuristic() {
        let mut plan = generate_philadelphia();

        // Create a timer but don't print (we're in a test)
        let mut timer = PhaseTimer::start("ConstructionHeuristic", 0);
        let score = construction_heuristic(&mut plan, &mut timer);

        // All visits should be assigned
        let total_visits: usize = plan.vehicles.iter().map(|v| v.visits.len()).sum();
        assert_eq!(total_visits, 49); // Philadelphia has 49 visits
        assert!(score.hard() <= 0); // May have some violations
    }
}
