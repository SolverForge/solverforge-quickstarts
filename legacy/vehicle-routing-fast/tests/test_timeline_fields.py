"""
Tests for timeline visualization fields in API serialization.

These tests verify that all fields required by the frontend timeline
visualizations (By vehicle, By visit tabs) are correctly serialized.
"""
from datetime import datetime, timedelta
from vehicle_routing.domain import (
    Location,
    Visit,
    Vehicle,
    VehicleRoutePlan,
)
from vehicle_routing.converters import (
    visit_to_model,
    vehicle_to_model,
    plan_to_model,
)


def create_test_location(lat: float = 43.77, lng: float = 11.25) -> Location:
    """Create a test location."""
    return Location(latitude=lat, longitude=lng)


def create_test_vehicle(
    departure_time: datetime = None,
    visits: list = None,
) -> Vehicle:
    """Create a test vehicle with optional visits."""
    if departure_time is None:
        departure_time = datetime(2024, 1, 1, 6, 0, 0)
    return Vehicle(
        id="1",
        name="Alpha",
        capacity=25,
        home_location=create_test_location(),
        departure_time=departure_time,
        visits=visits or [],
    )


def create_test_visit(
    vehicle: Vehicle = None,
    previous_visit: "Visit" = None,
    arrival_time: datetime = None,
) -> Visit:
    """Create a test visit."""
    visit = Visit(
        id="101",
        name="Test Customer",
        location=create_test_location(43.78, 11.26),
        demand=5,
        min_start_time=datetime(2024, 1, 1, 9, 0, 0),
        max_end_time=datetime(2024, 1, 1, 17, 0, 0),
        service_duration=timedelta(minutes=15),
        vehicle=vehicle,
        previous_visit=previous_visit,
        arrival_time=arrival_time,
    )
    return visit


def create_test_plan(vehicles: list = None, visits: list = None) -> VehicleRoutePlan:
    """Create a test route plan."""
    if vehicles is None:
        vehicles = [create_test_vehicle()]
    if visits is None:
        visits = []
    return VehicleRoutePlan(
        name="Test Plan",
        south_west_corner=create_test_location(43.75, 11.20),
        north_east_corner=create_test_location(43.80, 11.30),
        vehicles=vehicles,
        visits=visits,
    )


class TestVisitTimelineFields:
    """Tests for visit timeline serialization fields."""

    def test_unassigned_visit_has_null_timeline_fields(self):
        """Unassigned visits should have null timeline fields."""
        visit = create_test_visit(vehicle=None, arrival_time=None)
        model = visit_to_model(visit)

        assert model.arrival_time is None
        assert model.start_service_time is None
        assert model.departure_time is None
        assert model.driving_time_seconds_from_previous_standstill is None

    def test_assigned_visit_has_timeline_fields(self):
        """Assigned visits with arrival_time should have all timeline fields."""
        vehicle = create_test_vehicle()
        arrival = datetime(2024, 1, 1, 9, 30, 0)
        visit = create_test_visit(vehicle=vehicle, arrival_time=arrival)
        vehicle.visits = [visit]

        model = visit_to_model(visit)

        # arrival_time should be serialized
        assert model.arrival_time is not None
        assert model.arrival_time == "2024-01-01T09:30:00"

        # start_service_time = max(arrival_time, min_start_time)
        # Since arrival (09:30) > min_start (09:00), start_service = 09:30
        assert model.start_service_time is not None
        assert model.start_service_time == "2024-01-01T09:30:00"

        # departure_time = start_service_time + service_duration
        # = 09:30 + 15min = 09:45
        assert model.departure_time is not None
        assert model.departure_time == "2024-01-01T09:45:00"

        # driving_time_seconds should be calculated from vehicle home
        assert model.driving_time_seconds_from_previous_standstill is not None

    def test_early_arrival_uses_min_start_time(self):
        """When arrival is before min_start_time, start_service uses min_start_time."""
        vehicle = create_test_vehicle()
        # Arrive at 08:30, but min_start is 09:00
        early_arrival = datetime(2024, 1, 1, 8, 30, 0)
        visit = create_test_visit(vehicle=vehicle, arrival_time=early_arrival)
        vehicle.visits = [visit]

        model = visit_to_model(visit)

        # start_service_time should be min_start_time (09:00), not arrival (08:30)
        assert model.start_service_time == "2024-01-01T09:00:00"

        # departure should be min_start_time + service_duration = 09:15
        assert model.departure_time == "2024-01-01T09:15:00"


class TestVehicleTimelineFields:
    """Tests for vehicle timeline serialization fields."""

    def test_empty_vehicle_arrival_equals_departure(self):
        """Vehicle with no visits should have arrival_time = departure_time."""
        departure = datetime(2024, 1, 1, 6, 0, 0)
        vehicle = create_test_vehicle(departure_time=departure, visits=[])

        model = vehicle_to_model(vehicle)

        assert model.departure_time == "2024-01-01T06:00:00"
        assert model.arrival_time == "2024-01-01T06:00:00"

    def test_vehicle_with_visits_has_later_arrival(self):
        """Vehicle with visits should have arrival_time after last visit departure."""
        departure = datetime(2024, 1, 1, 6, 0, 0)
        vehicle = create_test_vehicle(departure_time=departure)

        # Create a visit assigned to this vehicle
        arrival = datetime(2024, 1, 1, 9, 30, 0)
        visit = create_test_visit(vehicle=vehicle, arrival_time=arrival)
        vehicle.visits = [visit]

        model = vehicle_to_model(vehicle)

        assert model.departure_time == "2024-01-01T06:00:00"
        # arrival_time should be > departure_time
        assert model.arrival_time is not None
        # arrival_time should be after visit departure + travel back to depot


class TestPlanTimelineFields:
    """Tests for route plan timeline window fields."""

    def test_plan_has_start_and_end_datetime(self):
        """Route plan should have startDateTime and endDateTime for timeline window."""
        departure = datetime(2024, 1, 1, 6, 0, 0)
        vehicle = create_test_vehicle(departure_time=departure)
        plan = create_test_plan(vehicles=[vehicle])

        model = plan_to_model(plan)

        # startDateTime should be earliest vehicle departure
        assert model.start_date_time is not None
        assert model.start_date_time == "2024-01-01T06:00:00"

        # endDateTime should be latest vehicle arrival
        # For empty vehicle, arrival = departure
        assert model.end_date_time is not None
        assert model.end_date_time == "2024-01-01T06:00:00"

    def test_plan_with_multiple_vehicles(self):
        """Plan timeline window should span all vehicles."""
        early_vehicle = create_test_vehicle(
            departure_time=datetime(2024, 1, 1, 5, 0, 0)
        )
        early_vehicle.id = "1"
        late_vehicle = create_test_vehicle(
            departure_time=datetime(2024, 1, 1, 8, 0, 0)
        )
        late_vehicle.id = "2"

        plan = create_test_plan(vehicles=[early_vehicle, late_vehicle])
        model = plan_to_model(plan)

        # startDateTime should be earliest departure (05:00)
        assert model.start_date_time == "2024-01-01T05:00:00"

        # endDateTime should be latest arrival
        # Both vehicles empty, so arrival = departure for each
        # Latest is late_vehicle at 08:00
        assert model.end_date_time == "2024-01-01T08:00:00"

    def test_empty_plan_has_null_datetimes(self):
        """Plan with no vehicles should have null datetime fields."""
        plan = create_test_plan(vehicles=[])

        model = plan_to_model(plan)

        assert model.start_date_time is None
        assert model.end_date_time is None
