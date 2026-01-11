//! Solver configuration for Employee Scheduling.
//!
//! Follows Timefold's pattern:
//! - `SolverManager` - async job management (solve, terminate, status)
//! - `SolutionManager` - stateless analysis (analyze constraints)

use crate::domain::EmployeeSchedule;
use solverforge::{SolutionManager, SolverManager};

pub use solverforge::SolverStatus;

/// The solver manager singleton for async job management.
pub fn solver_manager() -> &'static SolverManager<EmployeeSchedule> {
    static MANAGER: std::sync::OnceLock<SolverManager<EmployeeSchedule>> =
        std::sync::OnceLock::new();
    MANAGER.get_or_init(SolverManager::new)
}

/// The solution manager singleton for stateless analysis.
pub fn solution_manager() -> &'static SolutionManager<EmployeeSchedule> {
    static MANAGER: std::sync::OnceLock<SolutionManager<EmployeeSchedule>> =
        std::sync::OnceLock::new();
    MANAGER.get_or_init(SolutionManager::new)
}
