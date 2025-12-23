"""
Tests for demo data generation with customer-type based time windows.

These tests verify that the demo data correctly generates realistic
delivery scenarios with customer types driving time windows and demand.
"""
import pytest
from datetime import time

from vehicle_routing.demo_data import (
    DemoData,
    generate_demo_data,
    CustomerType,
    random_customer_type,
    CUSTOMER_TYPE_WEIGHTS,
)
from random import Random


class TestCustomerTypes:
    """Tests for customer type definitions and selection."""

    def test_customer_types_have_valid_time_windows(self):
        """Each customer type should have a valid time window."""
        for ctype in CustomerType:
            assert ctype.window_start < ctype.window_end, (
                f"{ctype.name} window_start should be before window_end"
            )

    def test_customer_types_have_valid_demand_ranges(self):
        """Each customer type should have valid demand ranges."""
        for ctype in CustomerType:
            assert ctype.min_demand >= 1, f"{ctype.name} min_demand should be >= 1"
            assert ctype.max_demand >= ctype.min_demand, (
                f"{ctype.name} max_demand should be >= min_demand"
            )

    def test_customer_types_have_valid_service_duration_ranges(self):
        """Each customer type should have valid service duration ranges."""
        for ctype in CustomerType:
            assert ctype.min_service_minutes >= 1, (
                f"{ctype.name} min_service_minutes should be >= 1"
            )
            assert ctype.max_service_minutes >= ctype.min_service_minutes, (
                f"{ctype.name} max_service_minutes should be >= min_service_minutes"
            )

    def test_residential_time_window(self):
        """Residential customers have evening windows."""
        res = CustomerType.RESIDENTIAL
        assert res.window_start == time(17, 0)
        assert res.window_end == time(20, 0)

    def test_business_time_window(self):
        """Business customers have standard business hours."""
        biz = CustomerType.BUSINESS
        assert biz.window_start == time(9, 0)
        assert biz.window_end == time(17, 0)

    def test_restaurant_time_window(self):
        """Restaurant customers have early morning windows."""
        rest = CustomerType.RESTAURANT
        assert rest.window_start == time(6, 0)
        assert rest.window_end == time(10, 0)

    def test_weighted_selection_distribution(self):
        """Weighted selection should roughly match configured weights."""
        random = Random(42)
        counts = {ctype: 0 for ctype in CustomerType}

        n_samples = 10000
        for _ in range(n_samples):
            ctype = random_customer_type(random)
            counts[ctype] += 1

        # Expected: 50% residential, 30% business, 20% restaurant
        total_weight = sum(w for _, w in CUSTOMER_TYPE_WEIGHTS)
        for ctype, weight in CUSTOMER_TYPE_WEIGHTS:
            expected_pct = weight / total_weight
            actual_pct = counts[ctype] / n_samples
            # Allow 5% tolerance
            assert abs(actual_pct - expected_pct) < 0.05, (
                f"{ctype.name}: expected {expected_pct:.2%}, got {actual_pct:.2%}"
            )


class TestDemoDataGeneration:
    """Tests for the demo data generation."""

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_generates_correct_number_of_vehicles(self, demo):
        """Should generate the configured number of vehicles."""
        plan = generate_demo_data(demo)
        assert len(plan.vehicles) == demo.value.vehicle_count

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_generates_correct_number_of_visits(self, demo):
        """Should generate the configured number of visits."""
        plan = generate_demo_data(demo)
        assert len(plan.visits) == demo.value.visit_count

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_visits_have_valid_time_windows(self, demo):
        """All visits should have time windows matching customer types."""
        plan = generate_demo_data(demo)
        valid_windows = {
            (ctype.window_start, ctype.window_end) for ctype in CustomerType
        }

        for visit in plan.visits:
            window = (visit.min_start_time.time(), visit.max_end_time.time())
            assert window in valid_windows, (
                f"Visit {visit.id} has invalid window {window}"
            )

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_visits_have_varied_time_windows(self, demo):
        """Visits should have a mix of different time windows."""
        plan = generate_demo_data(demo)

        windows = {
            (v.min_start_time.time(), v.max_end_time.time())
            for v in plan.visits
        }

        # Should have at least 2 different window types (likely all 3)
        assert len(windows) >= 2, "Should have varied time windows"

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_vehicles_depart_at_6am(self, demo):
        """Vehicles should depart at 06:00 to serve restaurant customers."""
        plan = generate_demo_data(demo)

        for vehicle in plan.vehicles:
            assert vehicle.departure_time.hour == 6
            assert vehicle.departure_time.minute == 0

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_visits_within_geographic_bounds(self, demo):
        """All visits should be within the specified geographic bounds."""
        plan = generate_demo_data(demo)
        sw = plan.south_west_corner
        ne = plan.north_east_corner

        for visit in plan.visits:
            assert sw.latitude <= visit.location.latitude <= ne.latitude, (
                f"Visit {visit.id} latitude {visit.location.latitude} "
                f"outside bounds [{sw.latitude}, {ne.latitude}]"
            )
            assert sw.longitude <= visit.location.longitude <= ne.longitude, (
                f"Visit {visit.id} longitude {visit.location.longitude} "
                f"outside bounds [{sw.longitude}, {ne.longitude}]"
            )

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_vehicles_within_geographic_bounds(self, demo):
        """All vehicle home locations should be within geographic bounds."""
        plan = generate_demo_data(demo)
        sw = plan.south_west_corner
        ne = plan.north_east_corner

        for vehicle in plan.vehicles:
            loc = vehicle.home_location
            assert sw.latitude <= loc.latitude <= ne.latitude
            assert sw.longitude <= loc.longitude <= ne.longitude

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_service_durations_match_customer_types(self, demo):
        """Service durations should match their customer type's service duration range."""
        plan = generate_demo_data(demo)

        # Map time windows back to customer types
        window_to_type = {
            (ctype.window_start, ctype.window_end): ctype
            for ctype in CustomerType
        }

        for visit in plan.visits:
            window = (visit.min_start_time.time(), visit.max_end_time.time())
            ctype = window_to_type[window]
            duration_minutes = int(visit.service_duration.total_seconds() / 60)
            assert ctype.min_service_minutes <= duration_minutes <= ctype.max_service_minutes, (
                f"Visit {visit.id} ({ctype.name}) service duration {duration_minutes}min "
                f"outside [{ctype.min_service_minutes}, {ctype.max_service_minutes}]"
            )

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_demands_match_customer_types(self, demo):
        """Visit demands should match their customer type's demand range."""
        plan = generate_demo_data(demo)

        # Map time windows back to customer types
        window_to_type = {
            (ctype.window_start, ctype.window_end): ctype
            for ctype in CustomerType
        }

        for visit in plan.visits:
            window = (visit.min_start_time.time(), visit.max_end_time.time())
            ctype = window_to_type[window]
            assert ctype.min_demand <= visit.demand <= ctype.max_demand, (
                f"Visit {visit.id} ({ctype.name}) demand {visit.demand} "
                f"outside [{ctype.min_demand}, {ctype.max_demand}]"
            )

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_vehicle_capacities_within_bounds(self, demo):
        """Vehicle capacities should be within configured bounds."""
        plan = generate_demo_data(demo)
        props = demo.value

        for vehicle in plan.vehicles:
            assert props.min_vehicle_capacity <= vehicle.capacity <= props.max_vehicle_capacity, (
                f"Vehicle {vehicle.id} capacity {vehicle.capacity} "
                f"outside [{props.min_vehicle_capacity}, {props.max_vehicle_capacity}]"
            )

    @pytest.mark.parametrize("demo", list(DemoData))
    def test_deterministic_with_same_seed(self, demo):
        """Same demo data should produce identical results (deterministic)."""
        plan1 = generate_demo_data(demo)
        plan2 = generate_demo_data(demo)

        assert len(plan1.visits) == len(plan2.visits)
        assert len(plan1.vehicles) == len(plan2.vehicles)

        for v1, v2 in zip(plan1.visits, plan2.visits):
            assert v1.location.latitude == v2.location.latitude
            assert v1.location.longitude == v2.location.longitude
            assert v1.demand == v2.demand
            assert v1.service_duration == v2.service_duration
            assert v1.min_start_time == v2.min_start_time
            assert v1.max_end_time == v2.max_end_time


class TestHaversineIntegration:
    """Tests verifying Haversine distance is used correctly in demo data."""

    def test_philadelphia_diagonal_realistic(self):
        """Philadelphia area diagonal should be ~15km with Haversine (tightened bbox)."""
        props = DemoData.PHILADELPHIA.value
        diagonal_seconds = props.south_west_corner.driving_time_to(
            props.north_east_corner
        )
        diagonal_km = (diagonal_seconds / 3600) * 50  # 50 km/h average

        # Philadelphia bbox is tightened to Center City area (~8km x 12km)
        # Diagonal should be around 10-20km
        assert 8 < diagonal_km < 25, f"Diagonal {diagonal_km}km seems wrong"

    def test_firenze_diagonal_realistic(self):
        """Firenze area diagonal should be ~10km with Haversine."""
        props = DemoData.FIRENZE.value
        diagonal_seconds = props.south_west_corner.driving_time_to(
            props.north_east_corner
        )
        diagonal_km = (diagonal_seconds / 3600) * 50  # 50 km/h average

        # Firenze area is small, roughly 6km x 12km
        assert 5 < diagonal_km < 20, f"Diagonal {diagonal_km}km seems wrong"

    def test_inter_visit_distances_use_haversine(self):
        """Distances between visits should use Haversine formula."""
        plan = generate_demo_data(DemoData.PHILADELPHIA)

        # Pick two visits
        v1, v2 = plan.visits[0], plan.visits[1]

        # Calculate distance using the Location method
        haversine_time = v1.location.driving_time_to(v2.location)

        # Verify it's not using simple Euclidean (which would be ~4000 * coord_diff)
        simple_euclidean = round(
            ((v1.location.latitude - v2.location.latitude) ** 2 +
             (v1.location.longitude - v2.location.longitude) ** 2) ** 0.5 * 4000
        )

        # Haversine should give different (usually larger) results
        # for geographic coordinates
        assert haversine_time != simple_euclidean or haversine_time == 0
