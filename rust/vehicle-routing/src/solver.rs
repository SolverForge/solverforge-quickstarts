//! Solver service for Vehicle Routing Problem.
//!
//! Uses Late Acceptance local search with 3-opt moves for efficient route optimization.
//! Direct score calculation with full solution access (no global state).

use parking_lot::RwLock;
use rand::Rng;
use solverforge::prelude::*;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::oneshot;
use tracing::{debug, info};

use crate::console::{self, PhaseTimer};
use crate::constraints::calculate_score;
use crate::domain::VehicleRoutePlan;

/// Default solving time: 30 seconds.
const DEFAULT_TIME_LIMIT_SECS: u64 = 30;

/// Late acceptance history size.
const LATE_ACCEPTANCE_SIZE: usize = 400;

/// Solver configuration with termination criteria.
///
/// Multiple termination conditions combine with OR logic (any triggers termination).
#[derive(Debug, Clone, Default)]
pub struct SolverConfig {
    /// Stop after this duration.
    pub time_limit: Option<Duration>,
    /// Stop after this duration without improvement.
    pub unimproved_time_limit: Option<Duration>,
    /// Stop after this many steps.
    pub step_limit: Option<u64>,
    /// Stop after this many steps without improvement.
    pub unimproved_step_limit: Option<u64>,
}

impl SolverConfig {
    /// Creates a config with default 30-second time limit.
    pub fn default_config() -> Self {
        Self {
            time_limit: Some(Duration::from_secs(DEFAULT_TIME_LIMIT_SECS)),
            ..Default::default()
        }
    }

    /// Checks if any termination condition is met.
    fn should_terminate(
        &self,
        elapsed: Duration,
        steps: u64,
        time_since_improvement: Duration,
        steps_since_improvement: u64,
    ) -> bool {
        if let Some(limit) = self.time_limit {
            if elapsed >= limit {
                return true;
            }
        }
        if let Some(limit) = self.unimproved_time_limit {
            if time_since_improvement >= limit {
                return true;
            }
        }
        if let Some(limit) = self.step_limit {
            if steps >= limit {
                return true;
            }
        }
        if let Some(limit) = self.unimproved_step_limit {
            if steps_since_improvement >= limit {
                return true;
            }
        }
        false
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
    let mut current_score = construction_heuristic(&mut solution, &mut ch_timer);
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

    // Phase 2: Late Acceptance local search with 3-opt
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

    let mut ls_timer = PhaseTimer::start("LateAcceptance", 1);
    let mut late_scores = vec![current_score; LATE_ACCEPTANCE_SIZE];
    let mut step: u64 = 0;
    let mut rng = rand::thread_rng();

    // Track best score and improvement times
    let mut best_score = current_score;
    let mut last_improvement_time = solve_start;
    let mut last_improvement_step: u64 = 0;

    loop {
        // Check termination conditions
        let elapsed = solve_start.elapsed();
        let time_since_improvement = last_improvement_time.elapsed();
        let steps_since_improvement = step - last_improvement_step;

        if config.should_terminate(elapsed, step, time_since_improvement, steps_since_improvement) {
            debug!("Termination condition met");
            break;
        }

        // Check for stop signal
        if stop_rx.try_recv().is_ok() {
            info!("Solving terminated early by user");
            break;
        }

        // Alternate between list-change and 2-opt moves
        let accepted = if step % 3 == 0 {
            // 2-opt move (intra-route segment reversal)
            try_two_opt_move(&mut solution, &mut current_score, &late_scores, step, &mut rng, &mut ls_timer)
        } else {
            // List-change move (visit relocation)
            try_list_change_move(&mut solution, &mut current_score, &late_scores, step, &mut rng, &mut ls_timer)
        };

        if accepted {
            // Update late acceptance history
            let late_idx = (step as usize) % LATE_ACCEPTANCE_SIZE;
            late_scores[late_idx] = current_score;

            // Track improvements
            if current_score > best_score {
                best_score = current_score;
                last_improvement_time = Instant::now();
                last_improvement_step = step;
            }

            // Periodic update
            if ls_timer.steps_accepted().is_multiple_of(1000) {
                update_job(&job, &solution, current_score);
                debug!(
                    step,
                    moves_accepted = ls_timer.steps_accepted(),
                    score = %current_score,
                    elapsed_secs = solve_start.elapsed().as_secs(),
                    "Progress update"
                );
            }

            // Periodic console progress (every 10000 moves)
            if ls_timer.moves_evaluated().is_multiple_of(10000) {
                console::print_step_progress(
                    ls_timer.steps_accepted(),
                    ls_timer.elapsed(),
                    ls_timer.moves_evaluated(),
                    &current_score.to_string(),
                );
            }
        }

        step += 1;
    }

    ls_timer.finish();

    let total_duration = solve_start.elapsed();
    let total_moves = step;

    info!(
        job_id = %job_id,
        duration_secs = total_duration.as_secs_f64(),
        steps = step,
        score = %current_score,
        feasible = current_score.is_feasible(),
        "Solving complete"
    );

    console::print_solving_ended(
        total_duration,
        total_moves,
        2,
        &current_score.to_string(),
        current_score.is_feasible(),
    );

    finish_job(&job, &solution, current_score);
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

/// Tries a list-change (visit relocation) move.
/// Returns true if the move was accepted.
fn try_list_change_move<R: Rng>(
    solution: &mut VehicleRoutePlan,
    current_score: &mut HardSoftScore,
    late_scores: &[HardSoftScore],
    step: u64,
    rng: &mut R,
    timer: &mut PhaseTimer,
) -> bool {
    let n_vehicles = solution.vehicles.len();

    // Find a non-empty source vehicle
    let non_empty: Vec<usize> = solution
        .vehicles
        .iter()
        .enumerate()
        .filter(|(_, v)| !v.visits.is_empty())
        .map(|(i, _)| i)
        .collect();

    if non_empty.is_empty() {
        return false;
    }

    let src_vehicle = non_empty[rng.gen_range(0..non_empty.len())];
    let src_len = solution.vehicles[src_vehicle].visits.len();
    let src_pos = rng.gen_range(0..src_len);

    // Pick destination vehicle and position
    let dst_vehicle = rng.gen_range(0..n_vehicles);
    let dst_len = solution.vehicles[dst_vehicle].visits.len();

    // Valid insertion position
    let max_pos = if src_vehicle == dst_vehicle {
        src_len
    } else {
        dst_len + 1
    };

    if max_pos == 0 {
        return false;
    }

    let dst_pos = rng.gen_range(0..max_pos);

    // Skip no-op moves
    if src_vehicle == dst_vehicle {
        let effective_dst = if dst_pos > src_pos { dst_pos - 1 } else { dst_pos };
        if src_pos == effective_dst {
            return false;
        }
    }

    timer.record_move();

    // Apply move
    let visit_idx = solution.vehicles[src_vehicle].visits.remove(src_pos);
    let adjusted_dst = if src_vehicle == dst_vehicle && dst_pos > src_pos {
        dst_pos - 1
    } else {
        dst_pos
    };
    solution.vehicles[dst_vehicle].visits.insert(adjusted_dst, visit_idx);

    // Evaluate
    let new_score = calculate_score(solution);
    let late_idx = (step as usize) % late_scores.len();
    let late_score = late_scores[late_idx];

    if new_score >= *current_score || new_score >= late_score {
        // Accept
        timer.record_accepted(&new_score.to_string());
        *current_score = new_score;
        true
    } else {
        // Reject - undo
        solution.vehicles[dst_vehicle].visits.remove(adjusted_dst);
        solution.vehicles[src_vehicle].visits.insert(src_pos, visit_idx);
        false
    }
}

/// Tries a 2-opt move (reverse a segment within a route).
/// Returns true if the move was accepted.
fn try_two_opt_move<R: Rng>(
    solution: &mut VehicleRoutePlan,
    current_score: &mut HardSoftScore,
    late_scores: &[HardSoftScore],
    step: u64,
    rng: &mut R,
    timer: &mut PhaseTimer,
) -> bool {
    // Find a vehicle with at least 2 visits
    let eligible: Vec<usize> = solution
        .vehicles
        .iter()
        .enumerate()
        .filter(|(_, v)| v.visits.len() >= 2)
        .map(|(i, _)| i)
        .collect();

    if eligible.is_empty() {
        return false;
    }

    let vehicle_idx = eligible[rng.gen_range(0..eligible.len())];
    let route_len = solution.vehicles[vehicle_idx].visits.len();

    // Pick two cut points for 2-opt
    let i = rng.gen_range(0..route_len);
    let j = rng.gen_range(0..route_len);

    if i == j {
        return false;
    }

    let (start, end) = if i < j { (i, j) } else { (j, i) };

    // Need at least 2 elements to reverse
    if end - start < 1 {
        return false;
    }

    timer.record_move();

    // Apply 2-opt: reverse segment [start, end]
    solution.vehicles[vehicle_idx].visits[start..=end].reverse();

    // Evaluate
    let new_score = calculate_score(solution);
    let late_idx = (step as usize) % late_scores.len();
    let late_score = late_scores[late_idx];

    if new_score >= *current_score || new_score >= late_score {
        // Accept
        timer.record_accepted(&new_score.to_string());
        *current_score = new_score;
        true
    } else {
        // Reject - undo (reverse again)
        solution.vehicles[vehicle_idx].visits[start..=end].reverse();
        false
    }
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
