from solverforge_legacy.solver.score import HardSoftDecimalScore

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
        serialize_by_alias=True,  # Output camelCase in JSON responses
    )


ScoreSerializer = PlainSerializer(
    lambda score: str(score) if score is not None else None,
    return_type=str | None
)

IdSerializer = PlainSerializer(
    lambda item: item.id if item is not None else None,
    return_type=str | None
)

IdListSerializer = PlainSerializer(
    lambda items: [item.id for item in items],
    return_type=list
)


def validate_score(v: Any, info: ValidationInfo) -> Any:
    if isinstance(v, HardSoftDecimalScore) or v is None:
        return v
    if isinstance(v, str):
        return HardSoftDecimalScore.parse(v)
    raise ValueError('"score" should be a string')


ScoreValidator = BeforeValidator(validate_score)
