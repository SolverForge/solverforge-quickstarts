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


def make_id_item_validator(key: str):
    def validator(v: Any, info: ValidationInfo) -> Any:
        if v is None:
            return None

        if not isinstance(v, str) or not info.context:
            return v

        return info.context.get(key)[v]

    return BeforeValidator(validator)


def make_id_list_item_validator(key: str):
    def validator(v: Any, info: ValidationInfo) -> Any:
        if v is None:
            return None

        if isinstance(v, (list, tuple)):
            out = []
            for item in v:
                if not isinstance(item, str) or not info.context:
                    return v
                out.append(info.context.get(key)[item])
            return out

        return v

    return BeforeValidator(validator)


ScoreSerializer = PlainSerializer(
    lambda score: str(score) if score is not None else None, return_type=str | None
)
IdSerializer = PlainSerializer(
    lambda item: item if isinstance(item, str) else (item.id if item is not None else None),
    return_type=str | None
)
IdListSerializer = PlainSerializer(
    lambda items: [item if isinstance(item, str) else item.id for item in items],
    return_type=list
)

VMListValidator = make_id_list_item_validator("vms")
VMValidator = make_id_item_validator("vms")
ServerValidator = make_id_item_validator("servers")


def validate_score(v: Any, info: ValidationInfo) -> Any:
    if isinstance(v, HardSoftScore) or v is None:
        return v
    if isinstance(v, str):
        # Handle "None" string or empty string as null
        if v in ("None", "null", ""):
            return None
        return HardSoftScore.parse(v)
    raise ValueError('"score" should be a string')


ScoreValidator = BeforeValidator(validate_score)
