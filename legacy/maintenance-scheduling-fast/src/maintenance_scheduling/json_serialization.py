from solverforge_legacy.solver.score import HardSoftScore

from typing import Any
from pydantic import (
    BaseModel,
    ConfigDict,
    PlainSerializer,
    BeforeValidator,
    ValidationInfo,
)
from pydantic.alias_generators import to_camel


class JsonDomainBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


ScoreSerializer = PlainSerializer(lambda score: str(score), return_type=str)
IdSerializer = PlainSerializer(
    lambda item: item.id if item is not None else None, return_type=str | None
)


def validate_score(v: Any, info: ValidationInfo) -> Any:
    if isinstance(v, HardSoftScore) or v is None:
        return v
    if isinstance(v, str):
        return HardSoftScore.parse(v)
    raise ValueError('"score" should be a string')


ScoreValidator = BeforeValidator(validate_score)
