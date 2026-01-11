"""
Score Analysis DTOs for Portfolio Optimization.

These data transfer objects are used for the /analyze endpoint
to provide detailed constraint-by-constraint score breakdown.
"""
from pydantic import BaseModel
from typing import List


class MatchAnalysisDTO(BaseModel):
    """A single constraint match (violation or reward)."""
    name: str
    score: str
    justification: str


class ConstraintAnalysisDTO(BaseModel):
    """Analysis of a single constraint across all matches."""
    name: str
    weight: str
    score: str
    matches: List[MatchAnalysisDTO]
