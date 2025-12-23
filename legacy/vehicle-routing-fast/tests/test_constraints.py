from solverforge_legacy.solver.test import ConstraintVerifier

from vehicle_routing.domain import Location, Vehicle, VehicleRoutePlan, Visit
from vehicle_routing.constraints import (
    define_constraints,
    vehicle_capacity,
    service_finished_after_max_end_time,
    minimize_travel_time,
)

from datetime import datetime, timedelta

# Driving times calculated using Haversine formula for realistic geographic distances.
# These test coordinates at 50 km/h average speed yield:
# LOCATION_1 to LOCATION_2: 40018 seconds (~11.1 hours, ~556 km)
# LOCATION_2 to LOCATION_3: 40025 seconds (~11.1 hours, ~556 km)
# LOCATION_1 to LOCATION_3: 11322 seconds (~3.1 hours, ~157 km)

LOCATION_1 = Location(latitude=0, longitude=0)
LOCATION_2 = Location(latitude=3, longitude=4)
LOCATION_3 = Location(latitude=-1, longitude=1)

DEPARTURE_TIME = datetime(2020, 1, 1)
MIN_START_TIME = DEPARTURE_TIME + timedelta(hours=2)
MAX_END_TIME = DEPARTURE_TIME + timedelta(hours=5)
SERVICE_DURATION = timedelta(hours=1)

constraint_verifier = ConstraintVerifier.build(
    define_constraints, VehicleRoutePlan, Vehicle, Visit
)


def test_vehicle_capacity_unpenalized():
    vehicleA = Vehicle(
        id="1", name="Alpha", capacity=100, home_location=LOCATION_1, departure_time=DEPARTURE_TIME
    )
    visit1 = Visit(
        id="2",
        name="John",
        location=LOCATION_2,
        demand=80,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )
    connect(vehicleA, visit1)

    (
        constraint_verifier.verify_that(vehicle_capacity)
        .given(vehicleA, visit1)
        .penalizes_by(0)
    )


def test_vehicle_capacity_penalized():
    vehicleA = Vehicle(
        id="1", name="Alpha", capacity=100, home_location=LOCATION_1, departure_time=DEPARTURE_TIME
    )
    visit1 = Visit(
        id="2",
        name="John",
        location=LOCATION_2,
        demand=80,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )
    visit2 = Visit(
        id="3",
        name="Paul",
        location=LOCATION_3,
        demand=40,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )

    connect(vehicleA, visit1, visit2)

    (
        constraint_verifier.verify_that(vehicle_capacity)
        .given(vehicleA, visit1, visit2)
        .penalizes_by(20)
    )


def test_service_finished_after_max_end_time_unpenalized():
    vehicleA = Vehicle(
        id="1", name="Alpha", capacity=100, home_location=LOCATION_1, departure_time=DEPARTURE_TIME
    )
    visit1 = Visit(
        id="2",
        name="John",
        location=LOCATION_3,
        demand=80,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )

    connect(vehicleA, visit1)

    (
        constraint_verifier.verify_that(service_finished_after_max_end_time)
        .given(vehicleA, visit1)
        .penalizes_by(0)
    )


def test_service_finished_after_max_end_time_penalized():
    vehicleA = Vehicle(
        id="1", name="Alpha", capacity=100, home_location=LOCATION_1, departure_time=DEPARTURE_TIME
    )
    visit1 = Visit(
        id="2",
        name="John",
        location=LOCATION_2,
        demand=80,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )

    connect(vehicleA, visit1)

    # With Haversine formula:
    # Travel time to LOCATION_2: 40018 seconds = 11.12 hours
    # Arrival time: 2020-01-01 11:06:58
    # Service duration: 1 hour
    # End service: 2020-01-01 12:06:58
    # Max end time: 2020-01-01 05:00:00
    # Delay: 7 hours 6 minutes 58 seconds = 426.97 minutes, rounded up = 427 minutes
    (
        constraint_verifier.verify_that(service_finished_after_max_end_time)
        .given(vehicleA, visit1)
        .penalizes_by(427)
    )


def test_total_driving_time():
    vehicleA = Vehicle(
        id="1", name="Alpha", capacity=100, home_location=LOCATION_1, departure_time=DEPARTURE_TIME
    )
    visit1 = Visit(
        id="2",
        name="John",
        location=LOCATION_2,
        demand=80,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )
    visit2 = Visit(
        id="3",
        name="Paul",
        location=LOCATION_3,
        demand=40,
        min_start_time=MIN_START_TIME,
        max_end_time=MAX_END_TIME,
        service_duration=SERVICE_DURATION,
    )

    connect(vehicleA, visit1, visit2)

    # With Haversine formula:
    # LOCATION_1 -> LOCATION_2: 40018 seconds
    # LOCATION_2 -> LOCATION_3: 40025 seconds
    # LOCATION_3 -> LOCATION_1: 11322 seconds
    # Total: 91365 seconds
    (
        constraint_verifier.verify_that(minimize_travel_time)
        .given(vehicleA, visit1, visit2)
        .penalizes_by(91365)
    )


def connect(vehicle: Vehicle, *visits: Visit):
    vehicle.visits = list(visits)
    for i in range(len(visits)):
        visit = visits[i]
        visit.vehicle = vehicle
        if i > 0:
            visit.previous_visit = visits[i - 1]

        if i < len(visits) - 1:
            visit.next_visit = visits[i + 1]
        visit.update_arrival_time()
