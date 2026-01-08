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
    // SERIO incremental scoring
    TypedScoreDirector,
};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::oneshot;
use tracing::info;

use crate::console::{self, PhaseTimer};
use crate::constraints::{calculate_score, define_constraints};
use crate::domain::VehicleRoutePlan;

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

    // Create entity selector for vehicles (index 1, not 0 which is visits)
    let entity_selector = FromSolutionEntitySelector::new(1);

    // Create list-change move selector using macro-generated methods
    let move_selector: ListChangeMoveSelector<VehicleRoutePlan, usize> = ListChangeMoveSelector::new(
        Box::new(entity_selector),
        VehicleRoutePlan::list_len,
        VehicleRoutePlan::list_remove,
        VehicleRoutePlan::list_insert,
        "visits",
        1, // entity_descriptor_index for vehicles
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

    // Create score director with SERIO incremental scoring and shadow variable support
    let descriptor = crate::domain::create_solution_descriptor();
    let constraints = define_constraints();
    let inner_director = TypedScoreDirector::with_descriptor(
        solution,
        constraints,
        descriptor,
        VehicleRoutePlan::entity_count,
    );
    let director = ShadowAwareScoreDirector::new(inner_director);

    // Create solver scope
    let mut solver_scope = SolverScope::new(Box::new(director));

    // Initialize the score director for SERIO incremental scoring.
    // TypedScoreDirector requires calculate_score() before incremental updates work.
    solver_scope.calculate_score();

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
    use solverforge::ScoreDirector;

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

    /// Debug test: verify SERIO works with RecordingScoreDirector (like LocalSearchPhase uses).
    #[test]
    fn test_serio_with_recording_director() {
        use solverforge::{Move, RecordingScoreDirector};

        let mut solution = generate_philadelphia();
        solution.finalize();

        // Simple round-robin assignment
        for (i, _visit) in solution.visits.iter().enumerate() {
            let vehicle_idx = i % solution.vehicles.len();
            solution.vehicles[vehicle_idx].visits.push(i);
        }
        solution.update_shadows();

        // Create typed score director
        let descriptor = crate::domain::create_solution_descriptor();
        let constraints = define_constraints();
        let inner_director = TypedScoreDirector::with_descriptor(
            solution,
            constraints,
            descriptor,
            VehicleRoutePlan::entity_count,
        );
        let mut director = ShadowAwareScoreDirector::new(inner_director);

        // Initialize
        let initial_score = director.calculate_score();
        eprintln!("\nInitial score: {:?}", initial_score);

        // Create a move
        let move_instance = ListChangeMove::<VehicleRoutePlan, usize>::new(
            0,    // source_entity_index
            0,    // source_position
            1,    // dest_entity_index
            0,    // dest_position
            VehicleRoutePlan::list_len,
            VehicleRoutePlan::list_remove,
            VehicleRoutePlan::list_insert,
            "visits",
            1, // descriptor_index
        );

        // === Phase 1: Evaluate move with RecordingScoreDirector (like LocalSearchPhase) ===
        eprintln!("\n=== Phase 1: Evaluate move with RecordingScoreDirector ===");
        let move_score;
        {
            let mut recording = RecordingScoreDirector::new(&mut director);
            move_instance.do_move(&mut recording);
            move_score = recording.calculate_score();
            eprintln!("Move score (during evaluation): {:?}", move_score);

            // Undo the move
            recording.undo_changes();
        }
        // RecordingScoreDirector is now dropped

        // Check the score after undo
        let score_after_undo = director.calculate_score();
        eprintln!("Score after undo: {:?}", score_after_undo);

        // Score should be back to initial
        assert_eq!(
            initial_score, score_after_undo,
            "Score not restored after undo!"
        );

        // === Phase 2: Apply move for real (like LocalSearchPhase does after picking) ===
        eprintln!("\n=== Phase 2: Apply move for real ===");
        move_instance.do_move(&mut director);

        let final_score = director.calculate_score();
        eprintln!("Final score (after real application): {:?}", final_score);

        // This should match the move_score from evaluation
        assert_eq!(
            move_score, final_score,
            "Final score doesn't match evaluation score!"
        );

        // And it should be different from initial
        assert_ne!(
            initial_score, final_score,
            "Score didn't change after applying move!"
        );
    }

    /// Debug test: verify SERIO works through TypedScoreDirector (not just raw constraints).
    #[test]
    fn test_serio_via_score_director() {
        let mut solution = generate_philadelphia();
        solution.finalize();

        // Simple round-robin assignment
        for (i, _visit) in solution.visits.iter().enumerate() {
            let vehicle_idx = i % solution.vehicles.len();
            solution.vehicles[vehicle_idx].visits.push(i);
        }
        solution.update_shadows();

        // Create typed score director (same as in local search)
        let descriptor = crate::domain::create_solution_descriptor();
        let constraints = define_constraints();
        let inner_director = TypedScoreDirector::with_descriptor(
            solution,
            constraints,
            descriptor,
            VehicleRoutePlan::entity_count,
        );
        let mut director = ShadowAwareScoreDirector::new(inner_director);

        // Initialize
        let initial_score = director.calculate_score();
        eprintln!("\nInitial score (via director): {:?}", initial_score);

        // Now manually apply a move via the score director
        let source_vehicle = 0;
        let dest_vehicle = 1;
        let source_pos = 0;

        eprintln!("\n=== Applying move via score director ===");

        // before_variable_changed for both vehicles
        director.before_variable_changed(1, source_vehicle, "visits");
        director.before_variable_changed(1, dest_vehicle, "visits");

        // Make the change
        let visit_idx = director.working_solution_mut().vehicles[source_vehicle]
            .visits
            .remove(source_pos);
        director.working_solution_mut().vehicles[dest_vehicle]
            .visits
            .push(visit_idx);
        eprintln!("Moved visit {} from vehicle {} to vehicle {}", visit_idx, source_vehicle, dest_vehicle);

        // after_variable_changed for both vehicles
        director.after_variable_changed(1, source_vehicle, "visits");
        director.after_variable_changed(1, dest_vehicle, "visits");

        // Get the new score from cached_score (via calculate_score)
        let new_score = director.calculate_score();
        eprintln!("New score (after move): {:?}", new_score);

        // Also do a full re-evaluation to verify
        // (need to create new constraints since old ones may have state)
        director.working_solution_mut().update_shadows();
        let full_rescore = calculate_score(director.working_solution_mut());
        eprintln!("Full re-evaluation: {:?}", full_rescore);

        // The incremental score should match full re-evaluation
        assert_eq!(
            new_score, full_rescore,
            "Incremental score doesn't match full re-evaluation!"
        );

        // The score should have changed
        assert_ne!(
            initial_score, new_score,
            "Score didn't change after move!"
        );
    }

    /// Debug test: trace SERIO deltas to understand why score doesn't change.
    #[test]
    fn test_serio_delta_trace() {
        use solverforge::ConstraintSet;

        let mut solution = generate_philadelphia();
        solution.finalize();

        // Simple round-robin assignment (not using construction heuristic to keep it simple)
        for (i, _visit) in solution.visits.iter().enumerate() {
            let vehicle_idx = i % solution.vehicles.len();
            solution.vehicles[vehicle_idx].visits.push(i);
        }

        // Update shadows after assignment
        solution.update_shadows();

        // Print initial state
        eprintln!("\n=== Initial State ===");
        for (i, v) in solution.vehicles.iter().enumerate() {
            eprintln!(
                "Vehicle {}: visits={:?}, cached_driving_time={}, driving_time_minutes={}",
                i,
                v.visits,
                v.cached_driving_time,
                v.driving_time_minutes()
            );
        }

        // Create typed constraints
        let mut constraints = define_constraints();

        // Initialize constraints (full evaluation)
        let initial_score = constraints.initialize_all(&solution);
        eprintln!("\nInitial score from initialize_all: {:?}", initial_score);

        // Also evaluate each constraint separately
        let per_constraint = constraints.evaluate_each(&solution);
        for cr in &per_constraint {
            eprintln!(
                "  Constraint '{}': score={:?}, matches={}",
                cr.name, cr.score, cr.match_count
            );
        }

        // Now simulate a move: move visit 0 from vehicle 0 to vehicle 1
        let source_vehicle = 0;
        let dest_vehicle = 1;
        let source_pos = 0;

        eprintln!("\n=== Simulating move: visit from vehicle {} pos {} to vehicle {} ===",
            source_vehicle, source_pos, dest_vehicle);

        // Step 1: on_retract for source vehicle (BEFORE any changes)
        let retract_source = constraints.on_retract_all(&solution, source_vehicle);
        eprintln!("on_retract(source={}): delta={:?}", source_vehicle, retract_source);
        eprintln!(
            "  Vehicle {} cached_driving_time={} driving_time_minutes={}",
            source_vehicle,
            solution.vehicles[source_vehicle].cached_driving_time,
            solution.vehicles[source_vehicle].driving_time_minutes()
        );

        // Step 2: on_retract for dest vehicle (BEFORE any changes)
        let retract_dest = constraints.on_retract_all(&solution, dest_vehicle);
        eprintln!("on_retract(dest={}): delta={:?}", dest_vehicle, retract_dest);

        // Step 3: Make the change
        let visit_idx = solution.vehicles[source_vehicle].visits.remove(source_pos);
        solution.vehicles[dest_vehicle].visits.push(visit_idx);
        eprintln!("Moved visit {} from vehicle {} to vehicle {}", visit_idx, source_vehicle, dest_vehicle);

        // Step 4: Update shadows for ALL vehicles (use public method)
        solution.update_shadows();
        eprintln!(
            "After shadow update - Vehicle {} cached_driving_time={} driving_time_minutes={}",
            source_vehicle,
            solution.vehicles[source_vehicle].cached_driving_time,
            solution.vehicles[source_vehicle].driving_time_minutes()
        );
        eprintln!(
            "After shadow update - Vehicle {} cached_driving_time={} driving_time_minutes={}",
            dest_vehicle,
            solution.vehicles[dest_vehicle].cached_driving_time,
            solution.vehicles[dest_vehicle].driving_time_minutes()
        );

        // Step 5: on_insert for source vehicle (AFTER shadow update)
        let insert_source = constraints.on_insert_all(&solution, source_vehicle);
        eprintln!("on_insert(source={}): delta={:?}", source_vehicle, insert_source);

        // Step 6: on_insert for dest vehicle (AFTER shadow update)
        let insert_dest = constraints.on_insert_all(&solution, dest_vehicle);
        eprintln!("on_insert(dest={}): delta={:?}", dest_vehicle, insert_dest);

        // Calculate net delta
        let total_delta = retract_source + retract_dest + insert_source + insert_dest;
        eprintln!("\n=== Summary ===");
        eprintln!("Total SERIO delta: {:?}", total_delta);
        eprintln!("Expected new score: {:?}", initial_score + total_delta);

        // Full re-evaluation for comparison
        let full_rescore = constraints.evaluate_all(&solution);
        eprintln!("Full re-evaluation score: {:?}", full_rescore);

        // The SERIO delta should result in the same score as full re-evaluation
        let serio_score = initial_score + total_delta;
        assert_eq!(
            serio_score, full_rescore,
            "SERIO incremental score doesn't match full re-evaluation!"
        );

        // Also assert that the delta is non-zero (the move should change something)
        assert_ne!(
            total_delta,
            HardSoftScore::zero(),
            "SERIO delta is zero - moves aren't being tracked!"
        );
    }

    /// Debug test: run a single step of local search and check scoring.
    #[test]
    fn test_single_local_search_step() {
        use solverforge::{Move, MoveSelector, RecordingScoreDirector};

        let mut solution = generate_philadelphia();
        solution.finalize();

        // Simple round-robin assignment
        for (i, _visit) in solution.visits.iter().enumerate() {
            let vehicle_idx = i % solution.vehicles.len();
            solution.vehicles[vehicle_idx].visits.push(i);
        }
        solution.update_shadows();

        // Create typed score director
        let descriptor = crate::domain::create_solution_descriptor();
        let constraints = define_constraints();
        let inner_director = TypedScoreDirector::with_descriptor(
            solution,
            constraints,
            descriptor,
            VehicleRoutePlan::entity_count,
        );
        let mut director: Box<dyn solverforge::ScoreDirector<VehicleRoutePlan>> =
            Box::new(ShadowAwareScoreDirector::new(inner_director));

        // Initialize score
        let initial_score = director.calculate_score();
        eprintln!("\nInitial score: {:?}", initial_score);

        // Create a move selector
        let entity_selector = FromSolutionEntitySelector::new(1);
        let move_selector = ListChangeMoveSelector::<VehicleRoutePlan, usize>::new(
            Box::new(entity_selector),
            VehicleRoutePlan::list_len,
            VehicleRoutePlan::list_remove,
            VehicleRoutePlan::list_insert,
            "visits",
            1,
        );

        // Get doable moves
        let moves: Vec<_> = move_selector
            .iter_moves(&*director)
            .filter(|m| m.is_doable(&*director))
            .collect();
        eprintln!("Generated {} doable moves", moves.len());

        // Evaluate first doable move
        let first_move = &moves[0];
        eprintln!(
            "First doable move: source_entity={}, source_pos={}, dest_entity={}, dest_pos={}",
            first_move.source_entity_index(),
            first_move.source_position(),
            first_move.dest_entity_index(),
            first_move.dest_position()
        );

        // Print vehicle state before move
        eprintln!("Before move - Vehicle 0:");
        eprintln!(
            "  visits={:?}",
            director.working_solution().vehicles[0].visits
        );
        eprintln!(
            "  cached_driving_time={}",
            director.working_solution().vehicles[0].cached_driving_time
        );

        // Phase 1: Evaluate with RecordingScoreDirector
        let move_score;
        {
            let mut recording = RecordingScoreDirector::new(&mut *director);
            first_move.do_move(&mut recording);

            // Print vehicle state after move execution
            eprintln!("After do_move - Vehicle 0:");
            eprintln!(
                "  visits={:?}",
                recording.working_solution().vehicles[0].visits
            );
            eprintln!(
                "  cached_driving_time={}",
                recording.working_solution().vehicles[0].cached_driving_time
            );

            move_score = recording.calculate_score();
            eprintln!("Move score (evaluation): {:?}", move_score);
            recording.undo_changes();

            // Print state after undo
            eprintln!("After undo - Vehicle 0:");
            eprintln!(
                "  visits={:?}",
                recording.working_solution().vehicles[0].visits
            );
            eprintln!(
                "  cached_driving_time={}",
                recording.working_solution().vehicles[0].cached_driving_time
            );
        }

        // Check score after undo
        let score_after_undo = director.calculate_score();
        eprintln!("Score after undo: {:?}", score_after_undo);
        assert_eq!(initial_score, score_after_undo, "Score not restored after undo");

        // Phase 2: Apply move for real (as LocalSearchPhase does)
        eprintln!("\n=== Applying move for real ===");
        first_move.do_move(&mut *director);

        // Check score after real application
        let final_score = director.calculate_score();
        eprintln!("Final score: {:?}", final_score);

        // This is the critical assertion
        assert_eq!(
            move_score, final_score,
            "Final score doesn't match evaluation score - this is the bug!"
        );

        assert_ne!(
            initial_score, final_score,
            "Score didn't change after move!"
        );
    }

    #[test]
    fn test_local_search_makes_progress() {
        let mut solution = generate_philadelphia();
        solution.finalize();

        // Run construction heuristic
        let mut timer = PhaseTimer::start("ConstructionHeuristic", 0);
        let ch_score = construction_heuristic(&mut solution, &mut timer);
        eprintln!("After construction: score={:?}", ch_score);

        // Set up local search - entity index 1 for vehicles (0 is visits)
        let entity_selector = FromSolutionEntitySelector::new(1);
        let move_selector: ListChangeMoveSelector<VehicleRoutePlan, usize> =
            ListChangeMoveSelector::new(
                Box::new(entity_selector),
                VehicleRoutePlan::list_len,
                VehicleRoutePlan::list_remove,
                VehicleRoutePlan::list_insert,
                "visits",
                1,
            );

        let acceptor = LateAcceptanceAcceptor::<VehicleRoutePlan>::new(LATE_ACCEPTANCE_SIZE);
        let forager =
            FirstAcceptedForager::<VehicleRoutePlan, ListChangeMove<VehicleRoutePlan, usize>>::new();

        let mut phase = LocalSearchPhase::new(
            Box::new(move_selector),
            Box::new(acceptor),
            Box::new(forager),
            Some(100), // Only 100 steps for test
        );

        // Create score director with SERIO incremental scoring
        let descriptor = crate::domain::create_solution_descriptor();
        let constraints = define_constraints();
        let inner_director = TypedScoreDirector::with_descriptor(
            solution,
            constraints,
            descriptor,
            VehicleRoutePlan::entity_count,
        );
        let director = ShadowAwareScoreDirector::new(inner_director);

        let mut solver_scope = SolverScope::new(Box::new(director));

        // Calculate and log initial score
        let initial_score = solver_scope.calculate_score();
        eprintln!("Before local search: initial_score={:?}", initial_score);

        // Run local search
        phase.solve(&mut solver_scope);

        // Get final solution and score
        // IMPORTANT: call calculate_score() to get the actual cached score from SERIO
        // (not the stale score stored on the solution object)
        let step_count = solver_scope.total_step_count();
        let final_score = solver_scope.calculate_score();
        let final_solution = solver_scope.working_solution().clone();
        eprintln!(
            "After local search: steps={}, final_score={:?}",
            step_count, final_score
        );

        // Verify local search did some work
        assert!(
            step_count > 0,
            "Local search made 0 steps - no moves were accepted"
        );

        // Verify visits are still assigned (didn't break)
        let total_visits: usize = final_solution
            .vehicles
            .iter()
            .map(|v| v.visits.len())
            .sum();
        assert_eq!(total_visits, 49);

        // Score should be at least as good as construction (not worse)
        assert!(
            final_score >= ch_score,
            "Local search made score worse: {:?} < {:?}",
            final_score,
            ch_score
        );
    }
}
