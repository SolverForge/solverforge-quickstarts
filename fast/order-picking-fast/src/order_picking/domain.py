from dataclasses import dataclass, field
from typing import Annotated, Optional, List, Union

from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.score import HardSoftDecimalScore
from solverforge_legacy.solver.domain import (
    planning_entity,
    planning_solution,
    PlanningId,
    PlanningScore,
    PlanningListVariable,
    PlanningEntityCollectionProperty,
    ValueRangeProvider,
    InverseRelationShadowVariable,
    PreviousElementShadowVariable,
    NextElementShadowVariable,
)

from .warehouse import WarehouseLocation, Side
from .json_serialization import JsonDomainBase
from pydantic import Field


# =============================================================================
# Domain Classes (used internally by solver - @dataclass for performance)
# =============================================================================

@dataclass
class Product:
    """A store product that can be included in an order."""
    id: str
    name: str
    volume: int  # in cm3
    location: WarehouseLocation


@dataclass
class Order:
    """Represents an order submitted by a customer."""
    id: str
    items: list["OrderItem"] = field(default_factory=list)


@dataclass
class OrderItem:
    """An indivisible product added to an order."""
    id: str
    order: Order
    product: Product

    @property
    def volume(self) -> int:
        return self.product.volume

    @property
    def order_id(self) -> str:
        return self.order.id if self.order else None

    @property
    def location(self) -> WarehouseLocation:
        return self.product.location


@planning_entity
@dataclass
class TrolleyStep:
    """
    Represents a 'stop' in a Trolley's path where an order item is to be picked.

    Shadow variables automatically track the trolley assignment and position in the list.
    """
    id: Annotated[str, PlanningId]
    order_item: OrderItem

    # Shadow variables - automatically maintained by solver
    trolley: Annotated[
        Optional["Trolley"],
        InverseRelationShadowVariable(source_variable_name="steps")
    ] = None

    previous_step: Annotated[
        Optional["TrolleyStep"],
        PreviousElementShadowVariable(source_variable_name="steps")
    ] = None

    next_step: Annotated[
        Optional["TrolleyStep"],
        NextElementShadowVariable(source_variable_name="steps")
    ] = None

    @property
    def location(self) -> WarehouseLocation:
        return self.order_item.location

    @property
    def is_last(self) -> bool:
        return self.next_step is None

    @property
    def trolley_id(self) -> Optional[str]:
        return self.trolley.id if self.trolley else None

    def __str__(self) -> str:
        return f"TrolleyStep({self.id})"

    def __repr__(self) -> str:
        return f"TrolleyStep({self.id})"


@planning_entity
@dataclass
class Trolley:
    """
    A trolley that will be filled with order items.

    The steps list is the planning variable that the solver modifies.
    """
    id: Annotated[str, PlanningId]
    bucket_count: int
    bucket_capacity: int  # in cm3
    location: WarehouseLocation

    # Planning variable - solver assigns TrolleySteps to this list
    steps: Annotated[list[TrolleyStep], PlanningListVariable] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Trolley({self.id})"

    def __repr__(self) -> str:
        return f"Trolley({self.id})"


@planning_solution
@dataclass
class OrderPickingSolution:
    """The planning solution containing trolleys and steps to be optimized."""

    trolleys: Annotated[list[Trolley], PlanningEntityCollectionProperty]

    trolley_steps: Annotated[
        list[TrolleyStep],
        PlanningEntityCollectionProperty,
        ValueRangeProvider
    ]

    score: Annotated[Optional[HardSoftDecimalScore], PlanningScore] = None
    solver_status: SolverStatus = SolverStatus.NOT_SOLVING


# =============================================================================
# Pydantic API Models (for REST serialization only)
# =============================================================================

class WarehouseLocationModel(JsonDomainBase):
    shelving_id: str = Field(..., alias="shelvingId")
    side: str
    row: int


class ProductModel(JsonDomainBase):
    id: str
    name: str
    volume: int
    location: WarehouseLocationModel


class OrderItemModel(JsonDomainBase):
    id: str
    order_id: Optional[str] = Field(None, alias="orderId")
    product: ProductModel


class OrderModel(JsonDomainBase):
    id: str
    items: List[OrderItemModel] = Field(default_factory=list)


class TrolleyStepModel(JsonDomainBase):
    id: str
    order_item: OrderItemModel = Field(..., alias="orderItem")
    trolley: Optional[Union[str, "TrolleyModel"]] = None
    trolley_id: Optional[str] = Field(None, alias="trolleyId")


class TrolleyModel(JsonDomainBase):
    id: str
    bucket_count: int = Field(..., alias="bucketCount")
    bucket_capacity: int = Field(..., alias="bucketCapacity")
    location: WarehouseLocationModel
    steps: List[Union[str, TrolleyStepModel]] = Field(default_factory=list)


class OrderPickingSolutionModel(JsonDomainBase):
    trolleys: List[TrolleyModel]
    trolley_steps: List[TrolleyStepModel] = Field(..., alias="trolleySteps")
    score: Optional[str] = None
    solver_status: Optional[str] = Field(None, alias="solverStatus")
