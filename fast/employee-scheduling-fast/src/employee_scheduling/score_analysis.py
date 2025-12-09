from pydantic import BaseModel
from typing import List, Any, Annotated
from solverforge_legacy.solver.score import HardSoftDecimalScore
from .json_serialization import ScoreSerializer


class MatchAnalysisDTO(BaseModel):
    name: str
    score: Annotated[HardSoftDecimalScore, ScoreSerializer]
    justification: Any


class ConstraintAnalysisDTO(BaseModel):
    name: str
    weight: Annotated[HardSoftDecimalScore, ScoreSerializer]
    score: Annotated[HardSoftDecimalScore, ScoreSerializer]
    matches: List[MatchAnalysisDTO]
