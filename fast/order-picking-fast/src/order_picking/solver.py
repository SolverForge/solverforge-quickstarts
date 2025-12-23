from solverforge_legacy.solver import SolverManager, SolutionManager
from solverforge_legacy.solver.config import (
    SolverConfig,
    ScoreDirectorFactoryConfig,
    TerminationConfig,
    Duration,
)

from .domain import Trolley, TrolleyStep, OrderPickingSolution
from .constraints import define_constraints


solver_config = SolverConfig(
    solution_class=OrderPickingSolution,
    entity_class_list=[Trolley, TrolleyStep],
    score_director_factory_config=ScoreDirectorFactoryConfig(
        constraint_provider_function=define_constraints
    ),
    termination_config=TerminationConfig(spent_limit=Duration(minutes=10)),
)

solver_manager = SolverManager.create(solver_config)
solution_manager = SolutionManager.create(solver_manager)
