from dataclasses import dataclass
from typing import Annotated

from solverforge_legacy.solver.score import HardSoftScore
from .json_serialization import ScoreSerializer


@dataclass
class MatchAnalysisDTO:
    name: str
    score: Annotated[HardSoftScore, ScoreSerializer]
    justification: object


@dataclass
class ConstraintAnalysisDTO:
    name: str
    weight: Annotated[HardSoftScore, ScoreSerializer]
    matches: list[MatchAnalysisDTO]
    score: Annotated[HardSoftScore, ScoreSerializer]
