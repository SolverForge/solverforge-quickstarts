from solverforge_legacy.solver.score import (
    constraint_provider,
    ConstraintFactory,
    HardSoftDecimalScore,
    ConstraintCollectors,
)

from .domain import TrolleyStep, Trolley
from .warehouse import calculate_distance


REQUIRED_NUMBER_OF_BUCKETS = "Required number of buckets"
MINIMIZE_ORDER_SPLIT = "Minimize order split by trolley"
MINIMIZE_DISTANCE_PREVIOUS = "Minimize the distance from the previous trolley step"
MINIMIZE_DISTANCE_TO_ORIGIN = "Minimize the distance from last trolley step to the path origin"
BALANCE_TROLLEY_WORKLOAD = "Balance trolley workload"


def calculate_order_required_buckets(order_volume: int, bucket_capacity: int) -> int:
    """Calculate how many buckets are needed for an order volume."""
    return (order_volume + bucket_capacity - 1) // bucket_capacity


def get_previous_location(step: TrolleyStep):
    """Get the location of the previous element (trolley or previous step)."""
    if step.previous_step is not None:
        return step.previous_step.location
    elif step.trolley is not None:
        return step.trolley.location
    return None


def get_distance_from_previous(step: TrolleyStep) -> int:
    """Calculate distance from previous element to this step."""
    previous_location = get_previous_location(step)
    if previous_location is None:
        return 0
    return calculate_distance(previous_location, step.location)


@constraint_provider
def define_constraints(factory: ConstraintFactory):
    return [
        # Hard constraints
        required_number_of_buckets(factory),
        # Soft constraints
        minimize_order_split_by_trolley(factory),
        minimize_distance_from_previous_step(factory),
        minimize_distance_from_last_step_to_origin(factory),
        balance_trolley_workload(factory),
    ]


def required_number_of_buckets(factory: ConstraintFactory):
    """
    Ensure that a Trolley has sufficient buckets for all picked items.
    Buckets are not shared between orders.
    """
    return (
        factory.for_each(TrolleyStep)
        .filter(lambda step: step.trolley is not None)
        # Group by (trolley, order) and sum volumes
        .group_by(
            lambda step: step.trolley,
            lambda step: step.order_item.order,
            ConstraintCollectors.sum(lambda step: step.order_item.volume)
        )
        # Calculate required buckets per order
        .group_by(
            lambda trolley, order, order_volume: trolley,
            lambda trolley, order, order_volume: order,
            ConstraintCollectors.sum(
                lambda trolley, order, order_volume: calculate_order_required_buckets(
                    order_volume, trolley.bucket_capacity
                )
            )
        )
        # Sum required buckets per trolley
        .group_by(
            lambda trolley, order, order_buckets: trolley,
            ConstraintCollectors.sum(lambda trolley, order, order_buckets: order_buckets)
        )
        # Penalize if trolley doesn't have enough buckets
        .filter(lambda trolley, total_buckets: trolley.bucket_count < total_buckets)
        .penalize(
            HardSoftDecimalScore.ONE_HARD,
            lambda trolley, total_buckets: total_buckets - trolley.bucket_count
        )
        .as_constraint(REQUIRED_NUMBER_OF_BUCKETS)
    )


def minimize_order_split_by_trolley(factory: ConstraintFactory):
    """
    An order should ideally be prepared on the same trolley.
    Penalize splitting an order across multiple trolleys.
    """
    return (
        factory.for_each(TrolleyStep)
        .filter(lambda step: step.trolley is not None)
        .group_by(
            lambda step: step.order_item.order,
            ConstraintCollectors.count_distinct(lambda step: step.trolley)
        )
        .penalize(
            HardSoftDecimalScore.ONE_SOFT,
            lambda order, trolley_count: trolley_count * 1000
        )
        .as_constraint(MINIMIZE_ORDER_SPLIT)
    )


def minimize_distance_from_previous_step(factory: ConstraintFactory):
    """
    Minimize the distance travelled by ensuring consecutive steps are close together.
    """
    return (
        factory.for_each(TrolleyStep)
        .filter(lambda step: step.trolley is not None)
        .penalize(
            HardSoftDecimalScore.ONE_SOFT,
            get_distance_from_previous
        )
        .as_constraint(MINIMIZE_DISTANCE_PREVIOUS)
    )


def minimize_distance_from_last_step_to_origin(factory: ConstraintFactory):
    """
    Minimize the return distance from the last step back to the trolley's starting location.
    """
    return (
        factory.for_each(TrolleyStep)
        .filter(lambda step: step.trolley is not None and step.is_last)
        .penalize(
            HardSoftDecimalScore.ONE_SOFT,
            lambda step: calculate_distance(step.location, step.trolley.location)
        )
        .as_constraint(MINIMIZE_DISTANCE_TO_ORIGIN)
    )


def balance_trolley_workload(factory: ConstraintFactory):
    """
    Penalize having too many items on one trolley vs others.
    Uses quadratic penalty to encourage even distribution.
    """
    return (
        factory.for_each(TrolleyStep)
        .filter(lambda step: step.trolley is not None)
        .group_by(
            lambda step: step.trolley,
            ConstraintCollectors.count()
        )
        .penalize(
            HardSoftDecimalScore.ONE_SOFT,
            lambda trolley, count: count * count * 10
        )
        .as_constraint(BALANCE_TROLLEY_WORKLOAD)
    )
