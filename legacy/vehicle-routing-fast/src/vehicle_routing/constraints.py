from solverforge_legacy.solver.score import (
    ConstraintFactory,
    HardSoftScore,
    constraint_provider,
)

from .domain import Vehicle, Visit

VEHICLE_CAPACITY = "vehicleCapacity"
MINIMIZE_TRAVEL_TIME = "minimizeTravelTime"
SERVICE_FINISHED_AFTER_MAX_END_TIME = "serviceFinishedAfterMaxEndTime"
MAX_ROUTE_DURATION = "maxRouteDuration"


@constraint_provider
def define_constraints(factory: ConstraintFactory):
    return [
        # Hard constraints
        vehicle_capacity(factory),
        service_finished_after_max_end_time(factory),
        # max_route_duration(factory),  # Optional extension - disabled by default
        # Soft constraints
        minimize_travel_time(factory),
    ]


##############################################
# Hard constraints
##############################################


def vehicle_capacity(factory: ConstraintFactory):
    return (
        factory.for_each(Vehicle)
        .filter(lambda vehicle: vehicle.calculate_total_demand() > vehicle.capacity)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda vehicle: vehicle.calculate_total_demand() - vehicle.capacity,
        )
        .as_constraint(VEHICLE_CAPACITY)
    )


def service_finished_after_max_end_time(factory: ConstraintFactory):
    return (
        factory.for_each(Visit)
        .filter(lambda visit: visit.is_service_finished_after_max_end_time())
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda visit: visit.service_finished_delay_in_minutes(),
        )
        .as_constraint(SERVICE_FINISHED_AFTER_MAX_END_TIME)
    )


##############################################
# Soft constraints
##############################################


def minimize_travel_time(factory: ConstraintFactory):
    return (
        factory.for_each(Vehicle)
        .penalize(
            HardSoftScore.ONE_SOFT,
            lambda vehicle: vehicle.calculate_total_driving_time_seconds(),
        )
        .as_constraint(MINIMIZE_TRAVEL_TIME)
    )


##############################################
# Optional constraints (disabled by default)
##############################################


def max_route_duration(factory: ConstraintFactory):
    """
    Hard constraint: Vehicle routes cannot exceed 8 hours total duration.

    The limit of 8 hours is chosen based on typical driver shift limits:
    - PHILADELPHIA: 55 visits across 6 vehicles, routes typically 4-6 hours
    - FIRENZE: 77 visits across 6 vehicles, routes can approach 8 hours

    Note: A limit that's too low may make the problem infeasible.
    Always ensure your constraints are compatible with your data dimensions.
    """
    MAX_DURATION_SECONDS = 8 * 60 * 60  # 8 hours

    return (
        factory.for_each(Vehicle)
        .filter(lambda vehicle: len(vehicle.visits) > 0)
        .filter(lambda vehicle:
            (vehicle.arrival_time - vehicle.departure_time).total_seconds()
            > MAX_DURATION_SECONDS
        )
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda vehicle: int(
                ((vehicle.arrival_time - vehicle.departure_time).total_seconds()
                 - MAX_DURATION_SECONDS) / 60
            ),
        )
        .as_constraint(MAX_ROUTE_DURATION)
    )
