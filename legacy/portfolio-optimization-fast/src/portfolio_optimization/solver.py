"""
Solver Configuration for Portfolio Optimization

This module sets up the SolverForge solver with:
- Solution class (PortfolioOptimizationPlan)
- Entity class (StockSelection)
- Constraint provider (define_constraints)
- Termination config (configurable, default 30 seconds)

The solver explores different stock selections and finds the best
portfolio that satisfies all constraints while maximizing return.
"""
from solverforge_legacy.solver import SolverManager, SolverFactory, SolutionManager
from solverforge_legacy.solver.config import (
    SolverConfig,
    ScoreDirectorFactoryConfig,
    TerminationConfig,
    Duration,
)

from .domain import PortfolioOptimizationPlan, StockSelection
from .constraints import define_constraints


def create_solver_config(termination_seconds: int = 30) -> SolverConfig:
    """
    Create a solver configuration with specified termination time.

    Args:
        termination_seconds: How long to run the solver (default 30 seconds)

    Returns:
        SolverConfig configured for portfolio optimization
    """
    return SolverConfig(
        # The solution class that contains all entities
        solution_class=PortfolioOptimizationPlan,

        # The entity classes that the solver modifies
        entity_class_list=[StockSelection],

        # The constraint provider that defines business rules
        score_director_factory_config=ScoreDirectorFactoryConfig(
            constraint_provider_function=define_constraints
        ),

        # How long to run the solver
        termination_config=TerminationConfig(spent_limit=Duration(seconds=termination_seconds)),
    )


# Default solver config (30 seconds)
solver_config: SolverConfig = create_solver_config()

# Create default solver manager for handling solve requests
solver_manager: SolverManager = SolverManager.create(SolverFactory.create(solver_config))

# Create solution manager for analyzing solutions
solution_manager: SolutionManager = SolutionManager.create(solver_manager)
