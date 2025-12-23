from solverforge_legacy.solver.score import (
    constraint_provider,
    ConstraintFactory,
    HardSoftDecimalScore,
)

from .domain import Trolley


REQUIRED_NUMBER_OF_BUCKETS = "Required number of buckets"
MINIMIZE_ORDER_SPLIT = "Minimize order split by trolley"
MINIMIZE_DISTANCE = "Minimize total distance"


@constraint_provider
def define_constraints(factory: ConstraintFactory):
    return [
        # Hard constraints
        required_number_of_buckets(factory),
        # Soft constraints
        minimize_order_split_by_trolley(factory),
        minimize_total_distance(factory),
    ]


def required_number_of_buckets(factory: ConstraintFactory):
    """
    Hard: Ensure trolley has enough buckets for all orders.
    """
    return (
        factory.for_each(Trolley)
        .filter(lambda trolley: trolley.calculate_excess_buckets() > 0)
        .penalize(
            HardSoftDecimalScore.ONE_HARD,
            lambda trolley: trolley.calculate_excess_buckets()
        )
        .as_constraint(REQUIRED_NUMBER_OF_BUCKETS)
    )


def minimize_order_split_by_trolley(factory: ConstraintFactory):
    """
    Soft: Orders should ideally be on the same trolley.
    """
    return (
        factory.for_each(Trolley)
        .filter(lambda trolley: len(trolley.steps) > 0)
        .penalize(
            HardSoftDecimalScore.ONE_SOFT,
            lambda trolley: trolley.calculate_order_split_penalty()
        )
        .as_constraint(MINIMIZE_ORDER_SPLIT)
    )


def minimize_total_distance(factory: ConstraintFactory):
    """
    Soft: Minimize total distance traveled by all trolleys.
    Aggregated at Trolley level (like vehicle-routing) for performance.
    """
    return (
        factory.for_each(Trolley)
        .penalize(
            HardSoftDecimalScore.ONE_SOFT,
            lambda trolley: trolley.calculate_total_distance()
        )
        .as_constraint(MINIMIZE_DISTANCE)
    )
