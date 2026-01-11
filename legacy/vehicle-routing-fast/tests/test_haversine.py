"""
Unit tests for the Haversine driving time calculator in Location class.

These tests verify that the driving time calculations correctly implement
the Haversine formula for great-circle distance on Earth.
"""
from vehicle_routing.domain import Location


class TestHaversineDrivingTime:
    """Tests for Location.driving_time_to() using Haversine formula."""

    def test_same_location_returns_zero(self):
        """Same location should return 0 driving time."""
        loc = Location(latitude=40.0, longitude=-75.0)
        assert loc.driving_time_to(loc) == 0

    def test_same_coordinates_returns_zero(self):
        """Two locations with same coordinates should return 0."""
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=40.0, longitude=-75.0)
        assert loc1.driving_time_to(loc2) == 0

    def test_symmetric_distance(self):
        """Distance from A to B should equal distance from B to A."""
        loc1 = Location(latitude=0, longitude=0)
        loc2 = Location(latitude=3, longitude=4)
        assert loc1.driving_time_to(loc2) == loc2.driving_time_to(loc1)

    def test_equator_one_degree_longitude(self):
        """
        One degree of longitude at the equator is approximately 111.32 km.
        At 50 km/h, this should take about 2.2 hours = 7920 seconds.
        """
        loc1 = Location(latitude=0, longitude=0)
        loc2 = Location(latitude=0, longitude=1)
        driving_time = loc1.driving_time_to(loc2)
        # Allow 5% tolerance for rounding
        assert 7500 < driving_time < 8500, f"Expected ~8000, got {driving_time}"

    def test_equator_one_degree_latitude(self):
        """
        One degree of latitude is approximately 111.32 km everywhere.
        At 50 km/h, this should take about 2.2 hours = 7920 seconds.
        """
        loc1 = Location(latitude=0, longitude=0)
        loc2 = Location(latitude=1, longitude=0)
        driving_time = loc1.driving_time_to(loc2)
        # Allow 5% tolerance for rounding
        assert 7500 < driving_time < 8500, f"Expected ~8000, got {driving_time}"

    def test_realistic_us_cities(self):
        """
        Test driving time between realistic US city coordinates.
        Philadelphia (39.95, -75.17) to New York (40.71, -74.01)
        Distance is approximately 130 km, should take ~2.6 hours at 50 km/h.
        """
        philadelphia = Location(latitude=39.95, longitude=-75.17)
        new_york = Location(latitude=40.71, longitude=-74.01)
        driving_time = philadelphia.driving_time_to(new_york)
        # Expected: ~130 km / 50 km/h * 3600 = ~9360 seconds
        # Allow reasonable tolerance
        assert 8500 < driving_time < 10500, f"Expected ~9400, got {driving_time}"

    def test_longer_distance(self):
        """
        Test longer distance: Philadelphia to Hartford.
        Distance is approximately 290 km.
        """
        philadelphia = Location(latitude=39.95, longitude=-75.17)
        hartford = Location(latitude=41.76, longitude=-72.68)
        driving_time = philadelphia.driving_time_to(hartford)
        # Expected: ~290 km / 50 km/h * 3600 = ~20880 seconds
        # Allow reasonable tolerance
        assert 19000 < driving_time < 23000, f"Expected ~21000, got {driving_time}"

    def test_known_values_from_test_data(self):
        """
        Verify the exact values used in constraint tests.
        These values are calculated using the Haversine formula.
        """
        LOCATION_1 = Location(latitude=0, longitude=0)
        LOCATION_2 = Location(latitude=3, longitude=4)
        LOCATION_3 = Location(latitude=-1, longitude=1)

        # These exact values are used in test_constraints.py
        assert LOCATION_1.driving_time_to(LOCATION_2) == 40018
        assert LOCATION_2.driving_time_to(LOCATION_3) == 40025
        assert LOCATION_1.driving_time_to(LOCATION_3) == 11322

    def test_negative_coordinates(self):
        """Test with negative latitude and longitude (Southern/Western hemisphere)."""
        loc1 = Location(latitude=-33.87, longitude=151.21)  # Sydney
        loc2 = Location(latitude=-37.81, longitude=144.96)  # Melbourne
        driving_time = loc1.driving_time_to(loc2)
        # Distance is approximately 714 km
        # Expected: ~714 km / 50 km/h * 3600 = ~51408 seconds
        assert 48000 < driving_time < 55000, f"Expected ~51400, got {driving_time}"

    def test_cross_hemisphere(self):
        """Test crossing equator."""
        loc1 = Location(latitude=10, longitude=0)
        loc2 = Location(latitude=-10, longitude=0)
        driving_time = loc1.driving_time_to(loc2)
        # 20 degrees of latitude = ~2226 km
        # Expected: ~2226 km / 50 km/h * 3600 = ~160272 seconds
        assert 155000 < driving_time < 165000, f"Expected ~160000, got {driving_time}"

    def test_cross_antimeridian(self):
        """Test crossing the antimeridian (date line)."""
        loc1 = Location(latitude=0, longitude=179)
        loc2 = Location(latitude=0, longitude=-179)
        driving_time = loc1.driving_time_to(loc2)
        # 2 degrees at equator = ~222 km
        # Expected: ~222 km / 50 km/h * 3600 = ~15984 seconds
        assert 15000 < driving_time < 17000, f"Expected ~16000, got {driving_time}"


class TestHaversineInternalMethods:
    """Tests for internal Haversine calculation methods."""

    def test_to_cartesian_equator_prime_meridian(self):
        """Test Cartesian conversion at equator/prime meridian intersection."""
        loc = Location(latitude=0, longitude=0)
        x, y, z = loc._to_cartesian()
        # At (0, 0): x=0, y=0.5, z=0
        assert abs(x - 0) < 0.001
        assert abs(y - 0.5) < 0.001
        assert abs(z - 0) < 0.001

    def test_to_cartesian_north_pole(self):
        """Test Cartesian conversion at North Pole."""
        loc = Location(latitude=90, longitude=0)
        x, y, z = loc._to_cartesian()
        # At North Pole: x=0, y=0, z=0.5
        assert abs(x - 0) < 0.001
        assert abs(y - 0) < 0.001
        assert abs(z - 0.5) < 0.001

    def test_meters_to_driving_seconds(self):
        """Test conversion from meters to driving seconds."""
        # 50 km = 50000 m should take 1 hour = 3600 seconds at 50 km/h
        seconds = Location._meters_to_driving_seconds(50000)
        assert seconds == 3600

    def test_meters_to_driving_seconds_zero(self):
        """Zero meters should return zero seconds."""
        assert Location._meters_to_driving_seconds(0) == 0

    def test_meters_to_driving_seconds_small(self):
        """Test small distances."""
        # 1 km = 1000 m should take 72 seconds at 50 km/h
        seconds = Location._meters_to_driving_seconds(1000)
        assert seconds == 72


