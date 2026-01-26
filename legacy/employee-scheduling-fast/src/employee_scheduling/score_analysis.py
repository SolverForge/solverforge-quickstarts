from pydantic import BaseModel
from typing import List


class MatchAnalysisDTO(BaseModel):
    name: str
    score: str
    justification: str


class ConstraintAnalysisDTO(BaseModel):
    name: str
    weight: str
    score: str
    matches: List[MatchAnalysisDTO]
