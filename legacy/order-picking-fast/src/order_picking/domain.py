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
    CascadingUpdateShadowVariable,
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
    The distance_from_previous is a cascading shadow variable that precomputes distance.
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

    # Cascading shadow variable - precomputes distance from previous element
    # This is updated automatically when the step is assigned/moved
    distance_from_previous: Annotated[
        Optional[int],
        CascadingUpdateShadowVariable(target_method_name="update_distance_from_previous")
    ] = None

    def update_distance_from_previous(self):
        """Called automatically by solver when step is assigned/moved."""
        from .warehouse import calculate_distance
        if self.trolley is None:
            self.distance_from_previous = None
        elif self.previous_step is None:
            # First step - distance from trolley start
            self.distance_from_previous = calculate_distance(
                self.trolley.location, self.location
            )
        else:
            # Distance from previous step
            self.distance_from_previous = calculate_distance(
                self.previous_step.location, self.location
            )

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

    def total_capacity(self) -> int:
        """Total volume capacity of this trolley."""
        return self.bucket_count * self.bucket_capacity

    def calculate_total_volume(self) -> int:
        """Sum of volumes of all items assigned to this trolley."""
        return sum(step.order_item.volume for step in self.steps)

    def calculate_excess_volume(self) -> int:
        """Volume exceeding capacity (0 if within capacity)."""
        excess = self.calculate_total_volume() - self.total_capacity()
        return max(0, excess)

    def calculate_required_buckets(self) -> int:
        """
        Calculate total buckets needed for all orders on this trolley.
        Buckets are NOT shared between orders - each order needs its own buckets.
        """
        if len(self.steps) == 0:
            return 0
        # Group steps by order and calculate buckets per order
        order_volumes: dict = {}
        for step in self.steps:
            order = step.order_item.order
            order_volumes[order.id] = order_volumes.get(order.id, 0) + step.order_item.volume
        # Sum up required buckets (ceiling division for each order)
        total_buckets = 0
        for volume in order_volumes.values():
            total_buckets += (volume + self.bucket_capacity - 1) // self.bucket_capacity
        return total_buckets

    def calculate_excess_buckets(self) -> int:
        """Buckets needed beyond capacity (0 if within capacity)."""
        excess = self.calculate_required_buckets() - self.bucket_count
        return max(0, excess)

    def calculate_order_split_penalty(self) -> int:
        """
        Penalty for orders split across trolleys.
        Returns 1000 per unique order on this trolley (will be summed across all trolleys).
        """
        if len(self.steps) == 0:
            return 0
        unique_orders = set(step.order_item.order.id for step in self.steps)
        return len(unique_orders) * 1000

    def calculate_total_distance(self) -> int:
        """
        Calculate total distance for this trolley's route.
        Uses precomputed distance_from_previous shadow variable for speed.
        """
        if len(self.steps) == 0:
            return 0
        from .warehouse import calculate_distance
        # Sum precomputed distances (already includes start -> first step)
        total = 0
        for step in self.steps:
            if step.distance_from_previous is not None:
                total += step.distance_from_previous
        # Add return trip from last step to origin
        last_step = self.steps[-1]
        total += calculate_distance(last_step.location, self.location)
        return total

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
