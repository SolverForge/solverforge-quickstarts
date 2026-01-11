//! Solver configuration for Employee Scheduling.
//!
//! Matches the Python pattern:
//! ```python
//! solver_manager = SolverManager.create(SolverFactory.create(solver_config))
//! solution_manager = SolutionManager.create(solver_manager)
//! ```

use crate::domain::EmployeeSchedule;
use solverforge::SolutionManager;

// Re-export for API compatibility
pub use solverforge::SolverStatus;

/// The solution manager singleton for employee scheduling.
///
/// Usage:
/// ```ignore
/// use employee_scheduling::solver::{solver_manager, solution_manager};
///
/// // Start solving
/// solver_manager().solve_and_listen(job_id, schedule, |solution| {
///     // Called when best solution updates
/// });
///
/// // Check status
/// let status = solver_manager().get_solver_status(job_id);
///
/// // Stop early
/// solver_manager().terminate_early(job_id);
///
/// // Analyze a solution
/// let analysis = solution_manager().analyze(schedule);
/// ```
pub fn solver_manager() -> &'static SolutionManager<EmployeeSchedule> {
    static MANAGER: std::sync::OnceLock<SolutionManager<EmployeeSchedule>> =
        std::sync::OnceLock::new();
    MANAGER.get_or_init(SolutionManager::new)
}

/// Alias for solver_manager (Python has both SolverManager and SolutionManager).
pub fn solution_manager() -> &'static SolutionManager<EmployeeSchedule> {
    solver_manager()
}
