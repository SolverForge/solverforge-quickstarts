from solverforge_legacy.solver import SolverManager, SolutionManager
from solverforge_legacy.solver.config import (
    SolverConfig,
    ScoreDirectorFactoryConfig,
    TerminationConfig,
    Duration,
)

from .domain import VM, VMPlacementPlan
from .constraints import define_constraints


solver_config = SolverConfig(
    solution_class=VMPlacementPlan,
    entity_class_list=[VM],
    score_director_factory_config=ScoreDirectorFactoryConfig(
        constraint_provider_function=define_constraints
    ),
    termination_config=TerminationConfig(spent_limit=Duration(seconds=30)),
)

solver_manager = SolverManager.create(solver_config)
solution_manager = SolutionManager.create(solver_manager)
