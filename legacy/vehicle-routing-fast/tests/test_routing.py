"""
Unit tests for the routing module.

Tests cover:
- RouteResult dataclass
- DistanceMatrix operations
- Haversine fallback calculations
- Polyline encoding/decoding roundtrip
- Location class integration with distance matrix
"""
import pytest
import polyline

from vehicle_routing.domain import Location
from vehicle_routing.routing import (
    RouteResult,
    DistanceMatrix,
    _haversine_driving_time,
    _haversine_distance_meters,
    _straight_line_geometry,
    compute_distance_matrix_with_progress,
)


class TestRouteResult:
    """Tests for the RouteResult dataclass."""

    def test_create_route_result(self):
        """Test creating a basic RouteResult."""
        result = RouteResult(
            duration_seconds=3600,
            distance_meters=50000,
            geometry="encodedPolyline"
        )
        assert result.duration_seconds == 3600
        assert result.distance_meters == 50000
        assert result.geometry == "encodedPolyline"

    def test_route_result_optional_geometry(self):
        """Test RouteResult with no geometry."""
        result = RouteResult(duration_seconds=100, distance_meters=1000)
        assert result.geometry is None


class TestDistanceMatrix:
    """Tests for the DistanceMatrix class."""

    def test_empty_matrix(self):
        """Test empty distance matrix returns None."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)
        assert matrix.get_route(loc1, loc2) is None

    def test_set_and_get_route(self):
        """Test setting and retrieving a route."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        result = RouteResult(
            duration_seconds=3600,
            distance_meters=100000,
            geometry="test_geometry"
        )
        matrix.set_route(loc1, loc2, result)

        retrieved = matrix.get_route(loc1, loc2)
        assert retrieved is not None
        assert retrieved.duration_seconds == 3600
        assert retrieved.distance_meters == 100000
        assert retrieved.geometry == "test_geometry"

    def test_get_route_different_direction(self):
        """Test that routes are directional (A->B != B->A by default)."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        result = RouteResult(duration_seconds=3600, distance_meters=100000)
        matrix.set_route(loc1, loc2, result)

        # Should find loc1 -> loc2
        assert matrix.get_route(loc1, loc2) is not None
        # Should NOT find loc2 -> loc1 (wasn't set)
        assert matrix.get_route(loc2, loc1) is None

    def test_get_driving_time_from_matrix(self):
        """Test getting driving time from matrix."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        result = RouteResult(duration_seconds=3600, distance_meters=100000)
        matrix.set_route(loc1, loc2, result)

        assert matrix.get_driving_time(loc1, loc2) == 3600

    def test_get_driving_time_falls_back_to_haversine(self):
        """Test that missing routes fall back to haversine."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        # Don't set any route - should use haversine fallback
        time = matrix.get_driving_time(loc1, loc2)
        assert time > 0  # Should return some positive value from haversine

    def test_get_geometry(self):
        """Test getting geometry from matrix."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        result = RouteResult(
            duration_seconds=3600,
            distance_meters=100000,
            geometry="test_encoded_polyline"
        )
        matrix.set_route(loc1, loc2, result)

        assert matrix.get_geometry(loc1, loc2) == "test_encoded_polyline"

    def test_get_geometry_missing_returns_none(self):
        """Test that missing routes return None for geometry."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        assert matrix.get_geometry(loc1, loc2) is None


class TestHaversineFunctions:
    """Tests for standalone haversine functions."""

    def test_haversine_driving_time_same_location(self):
        """Same location should return 0 driving time."""
        loc = Location(latitude=40.0, longitude=-75.0)
        assert _haversine_driving_time(loc, loc) == 0

    def test_haversine_driving_time_realistic(self):
        """Test haversine driving time with realistic coordinates."""
        philadelphia = Location(latitude=39.95, longitude=-75.17)
        new_york = Location(latitude=40.71, longitude=-74.01)
        time = _haversine_driving_time(philadelphia, new_york)
        # ~130 km at 50 km/h = ~9400 seconds
        assert 8500 < time < 10500

    def test_haversine_distance_meters_same_location(self):
        """Same location should return 0 distance."""
        loc = Location(latitude=40.0, longitude=-75.0)
        assert _haversine_distance_meters(loc, loc) == 0

    def test_haversine_distance_meters_one_degree(self):
        """Test one degree of latitude is approximately 111 km."""
        loc1 = Location(latitude=0, longitude=0)
        loc2 = Location(latitude=1, longitude=0)
        distance = _haversine_distance_meters(loc1, loc2)
        # 1 degree latitude = ~111.32 km
        assert 110000 < distance < 113000

    def test_straight_line_geometry(self):
        """Test straight line geometry encoding."""
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)
        encoded = _straight_line_geometry(loc1, loc2)

        # Decode and verify
        points = polyline.decode(encoded)
        assert len(points) == 2
        assert abs(points[0][0] - 40.0) < 0.0001
        assert abs(points[0][1] - (-75.0)) < 0.0001
        assert abs(points[1][0] - 41.0) < 0.0001
        assert abs(points[1][1] - (-74.0)) < 0.0001


class TestPolylineRoundtrip:
    """Tests for polyline encoding/decoding."""

    def test_encode_decode_roundtrip(self):
        """Test that encoding and decoding preserves coordinates."""
        coordinates = [(39.9526, -75.1652), (39.9535, -75.1589)]
        encoded = polyline.encode(coordinates, precision=5)
        decoded = polyline.decode(encoded, precision=5)

        assert len(decoded) == 2
        for orig, dec in zip(coordinates, decoded):
            assert abs(orig[0] - dec[0]) < 0.00001
            assert abs(orig[1] - dec[1]) < 0.00001

    def test_encode_single_point(self):
        """Test encoding a single point."""
        coordinates = [(40.0, -75.0)]
        encoded = polyline.encode(coordinates, precision=5)
        decoded = polyline.decode(encoded, precision=5)

        assert len(decoded) == 1
        assert abs(decoded[0][0] - 40.0) < 0.00001
        assert abs(decoded[0][1] - (-75.0)) < 0.00001

    def test_encode_many_points(self):
        """Test encoding many points (like a real route)."""
        coordinates = [
            (39.9526, -75.1652),
            (39.9535, -75.1589),
            (39.9543, -75.1690),
            (39.9520, -75.1685),
            (39.9505, -75.1660),
        ]
        encoded = polyline.encode(coordinates, precision=5)
        decoded = polyline.decode(encoded, precision=5)

        assert len(decoded) == len(coordinates)
        for orig, dec in zip(coordinates, decoded):
            assert abs(orig[0] - dec[0]) < 0.00001
            assert abs(orig[1] - dec[1]) < 0.00001


class TestLocationDistanceMatrixIntegration:
    """Tests for Location class integration with DistanceMatrix."""

    def setup_method(self):
        """Clear any existing distance matrix before each test."""
        Location.clear_distance_matrix()

    def teardown_method(self):
        """Clear distance matrix after each test."""
        Location.clear_distance_matrix()

    def test_location_uses_haversine_without_matrix(self):
        """Without matrix, Location should use haversine."""
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        # Should use haversine (no matrix set)
        time = loc1.driving_time_to(loc2)
        assert time > 0

    def test_location_uses_matrix_when_set(self):
        """With matrix set, Location should use matrix values."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        # Set a specific value in matrix
        result = RouteResult(duration_seconds=12345, distance_meters=100000)
        matrix.set_route(loc1, loc2, result)

        # Set the matrix on Location class
        Location.set_distance_matrix(matrix)

        # Should return the matrix value, not haversine
        time = loc1.driving_time_to(loc2)
        assert time == 12345

    def test_location_falls_back_when_route_not_in_matrix(self):
        """If route not in matrix, Location should fall back to haversine."""
        matrix = DistanceMatrix()
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)
        loc3 = Location(latitude=42.0, longitude=-73.0)

        # Only set loc1 -> loc2
        result = RouteResult(duration_seconds=12345, distance_meters=100000)
        matrix.set_route(loc1, loc2, result)

        Location.set_distance_matrix(matrix)

        # loc1 -> loc2 should use matrix
        assert loc1.driving_time_to(loc2) == 12345

        # loc1 -> loc3 should fall back to haversine (not in matrix)
        time = loc1.driving_time_to(loc3)
        assert time != 12345  # Should be haversine calculated value
        assert time > 0

    def test_get_distance_matrix(self):
        """Test getting the current distance matrix."""
        assert Location.get_distance_matrix() is None

        matrix = DistanceMatrix()
        Location.set_distance_matrix(matrix)
        assert Location.get_distance_matrix() is matrix

    def test_clear_distance_matrix(self):
        """Test clearing the distance matrix."""
        matrix = DistanceMatrix()
        Location.set_distance_matrix(matrix)
        assert Location.get_distance_matrix() is not None

        Location.clear_distance_matrix()
        assert Location.get_distance_matrix() is None


class TestDistanceMatrixSameLocation:
    """Tests for handling same-location routes."""

    def test_same_location_zero_time(self):
        """Same location should have zero driving time."""
        loc = Location(latitude=40.0, longitude=-75.0)

        matrix = DistanceMatrix()
        result = RouteResult(
            duration_seconds=0,
            distance_meters=0,
            geometry=polyline.encode([(40.0, -75.0)], precision=5)
        )
        matrix.set_route(loc, loc, result)

        assert matrix.get_driving_time(loc, loc) == 0


class TestComputeDistanceMatrixWithProgress:
    """Tests for the compute_distance_matrix_with_progress function."""

    def test_empty_locations_returns_empty_matrix(self):
        """Empty location list should return empty matrix."""
        matrix = compute_distance_matrix_with_progress([], use_osm=False)
        assert matrix is not None
        # Empty matrix - no routes to check

    def test_haversine_mode_computes_all_pairs(self):
        """Haversine mode should compute all location pairs."""
        locations = [
            Location(latitude=40.0, longitude=-75.0),
            Location(latitude=41.0, longitude=-74.0),
            Location(latitude=42.0, longitude=-73.0),
        ]
        matrix = compute_distance_matrix_with_progress(
            locations, use_osm=False
        )

        # Should have all 9 pairs (3x3)
        for origin in locations:
            for dest in locations:
                result = matrix.get_route(origin, dest)
                assert result is not None
                if origin is dest:
                    assert result.duration_seconds == 0
                    assert result.distance_meters == 0
                else:
                    assert result.duration_seconds > 0
                    assert result.distance_meters > 0
                    assert result.geometry is not None

    def test_progress_callback_is_called(self):
        """Progress callback should be called during computation."""
        locations = [
            Location(latitude=40.0, longitude=-75.0),
            Location(latitude=41.0, longitude=-74.0),
        ]

        progress_calls = []

        def callback(phase, message, percent, detail=""):
            progress_calls.append({
                "phase": phase,
                "message": message,
                "percent": percent,
                "detail": detail
            })

        compute_distance_matrix_with_progress(
            locations, use_osm=False, progress_callback=callback
        )

        # Should have received progress callbacks
        assert len(progress_calls) > 0

        # Should have a "complete" phase at the end
        assert any(p["phase"] == "complete" for p in progress_calls)

        # All percentages should be between 0 and 100
        for call in progress_calls:
            assert 0 <= call["percent"] <= 100

    def test_haversine_mode_skips_network_phase(self):
        """In haversine mode, should not have network download messages."""
        locations = [
            Location(latitude=40.0, longitude=-75.0),
            Location(latitude=41.0, longitude=-74.0),
        ]

        progress_calls = []

        def callback(phase, message, percent, detail=""):
            progress_calls.append({
                "phase": phase,
                "message": message
            })

        compute_distance_matrix_with_progress(
            locations, use_osm=False, progress_callback=callback
        )

        # Should have a "network" phase but with haversine message
        network_messages = [p for p in progress_calls if p["phase"] == "network"]
        assert len(network_messages) > 0
        assert "haversine" in network_messages[0]["message"].lower()

    def test_bbox_is_used_when_provided(self):
        """Provided bounding box should be used."""
        locations = [
            Location(latitude=40.0, longitude=-75.0),
            Location(latitude=41.0, longitude=-74.0),
        ]

        bbox = (42.0, 39.0, -73.0, -76.0)  # north, south, east, west

        # Should complete without error with provided bbox
        matrix = compute_distance_matrix_with_progress(
            locations, bbox=bbox, use_osm=False
        )
        assert matrix is not None

    def test_geometries_are_straight_lines_in_haversine_mode(self):
        """In haversine mode, geometries should be straight lines."""
        loc1 = Location(latitude=40.0, longitude=-75.0)
        loc2 = Location(latitude=41.0, longitude=-74.0)

        matrix = compute_distance_matrix_with_progress(
            [loc1, loc2], use_osm=False
        )

        result = matrix.get_route(loc1, loc2)
        assert result is not None
        assert result.geometry is not None

        # Decode and verify it's a straight line (2 points)
        points = polyline.decode(result.geometry)
        assert len(points) == 2
