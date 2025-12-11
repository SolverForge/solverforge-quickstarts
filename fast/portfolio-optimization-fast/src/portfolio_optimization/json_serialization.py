"""
JSON serialization utilities for the Portfolio Optimization quickstart.

Provides Pydantic configuration for REST API models with camelCase support.
"""
from solverforge_legacy.solver.score import HardSoftScore
from typing import Any
from pydantic import BaseModel, ConfigDict, PlainSerializer, BeforeValidator
from pydantic.alias_generators import to_camel


ScoreSerializer = PlainSerializer(
    lambda score: str(score) if score is not None else None, return_type=str | None
)


def validate_score(v: Any) -> Any:
    """Validate and parse score from string or HardSoftScore."""
    if isinstance(v, HardSoftScore) or v is None:
        return v
    if isinstance(v, str):
        return HardSoftScore.parse(v)
    raise ValueError('"score" should be a string')


ScoreValidator = BeforeValidator(validate_score)


class JsonDomainBase(BaseModel):
    """
    Base class for Pydantic REST models.

    Provides:
    - Automatic camelCase conversion for JSON keys
    - Support for both camelCase and snake_case in input
    - Attribute access from dataclass instances
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
