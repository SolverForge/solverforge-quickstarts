from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.score import HardSoftScore
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

from datetime import datetime, timedelta
from typing import Annotated, Optional, List, Union
from dataclasses import dataclass, field
from .json_serialization import JsonDomainBase
from pydantic import Field


# Global driving time matrix for pre-computed mode
# Key: (from_lat, from_lng, to_lat, to_lng) -> driving_time_seconds
# This is kept outside the Location class to avoid transpiler issues with mutable fields
_DRIVING_TIME_MATRIX: dict[tuple[float, float, float, float], int] = {}


def _get_matrix_key(from_loc: "Location", to_loc: "Location") -> tuple[float, float, float, float]:
    """Create a hashable key for the driving time matrix lookup."""
    return (from_loc.latitude, from_loc.longitude, to_loc.latitude, to_loc.longitude)


@dataclass
class Location:
    """
    Represents a geographic location with latitude and longitude.

    Driving times can be calculated in two modes:
    1. On-demand (default): Uses Haversine formula for each calculation
    2. Pre-computed matrix: O(1) lookup from global pre-calculated distance matrix

    The pre-computed mode is faster during solving (millions of lookups)
    but requires O(n²) memory and one-time initialization cost.

    To enable pre-computed mode, call init_driving_time_matrix() with all locations
    before solving.
    """
    latitude: float
    longitude: float

    # Earth radius in meters
    _EARTH_RADIUS_M = 6371000
    _TWICE_EARTH_RADIUS_M = 2 * _EARTH_RADIUS_M
    # Average driving speed assumption: 50 km/h
    _AVERAGE_SPEED_KMPH = 50

    def driving_time_to(self, other: "Location") -> int:
        """
        Get driving time in seconds to another location.

        If a pre-computed matrix is available (via init_driving_time_matrix),
        uses O(1) lookup. Otherwise, calculates on-demand using Haversine formula.
        """
        # Use pre-computed matrix if available
        key = _get_matrix_key(self, other)
        if key in _DRIVING_TIME_MATRIX:
            return _DRIVING_TIME_MATRIX[key]

        # Fall back to on-demand calculation
        return self._calculate_driving_time_haversine(other)

    def _calculate_driving_time_haversine(self, other: "Location") -> int:
        """
        Calculate driving time in seconds using Haversine distance.

        Algorithm:
        1. Convert lat/long to 3D Cartesian coordinates on a unit sphere
        2. Calculate Euclidean distance between the two points
        3. Use the arc sine formula to get the great-circle distance
        4. Convert meters to driving seconds assuming average speed
        """
        if self.latitude == other.latitude and self.longitude == other.longitude:
            return 0

        from_cartesian = self._to_cartesian()
        to_cartesian = other._to_cartesian()
        distance_meters = self._calculate_distance(from_cartesian, to_cartesian)
        return self._meters_to_driving_seconds(distance_meters)

    def _to_cartesian(self) -> tuple[float, float, float, float]:
        """Convert latitude/longitude to 3D Cartesian coordinates on a unit sphere."""
        import math
        lat_rad = math.radians(self.latitude)
        lon_rad = math.radians(self.longitude)
        # Cartesian coordinates, normalized for a sphere of diameter 1.0
        x = 0.5 * math.cos(lat_rad) * math.sin(lon_rad)
        y = 0.5 * math.cos(lat_rad) * math.cos(lon_rad)
        z = 0.5 * math.sin(lat_rad)
        return (x, y, z)

    def _calculate_distance(self, from_c: tuple[float, float, float, float], to_c: tuple[float, float, float, float]) -> int:
        """Calculate great-circle distance in meters between two Cartesian points."""
        import math
        dx = from_c[0] - to_c[0]
        dy = from_c[1] - to_c[1]
        dz = from_c[2] - to_c[2]
        r = math.sqrt(dx * dx + dy * dy + dz * dz)
        return round(self._TWICE_EARTH_RADIUS_M * math.asin(r))

    @classmethod
    def _meters_to_driving_seconds(cls, meters: int) -> int:
        """Convert distance in meters to driving time in seconds."""
        # Formula: seconds = meters / (km/h) * 3.6
        # This is equivalent to: seconds = meters / (speed_m_per_s)
        # where speed_m_per_s = km/h / 3.6
        return round(meters / cls._AVERAGE_SPEED_KMPH * 3.6)

    def __str__(self):
        return f"[{self.latitude}, {self.longitude}]"

    def __repr__(self):
        return f"Location({self.latitude}, {self.longitude})"


def init_driving_time_matrix(locations: list[Location]) -> None:
    """
    Pre-compute driving times between all location pairs.

    This trades O(n²) memory for O(1) lookup during solving.
    For n=77 locations (FIRENZE), this is only 5,929 entries.

    Call this once after creating all locations but before solving.
    The matrix is stored globally and persists across solver runs.
    """
    global _DRIVING_TIME_MATRIX
    _DRIVING_TIME_MATRIX = {}
    for from_loc in locations:
        for to_loc in locations:
            key = _get_matrix_key(from_loc, to_loc)
            _DRIVING_TIME_MATRIX[key] = from_loc._calculate_driving_time_haversine(to_loc)


def clear_driving_time_matrix() -> None:
    """Clear the pre-computed driving time matrix."""
    global _DRIVING_TIME_MATRIX
    _DRIVING_TIME_MATRIX = {}


def is_driving_time_matrix_initialized() -> bool:
    """Check if the driving time matrix has been pre-computed."""
    return len(_DRIVING_TIME_MATRIX) > 0


@planning_entity
@dataclass
class Visit:
    id: Annotated[str, PlanningId]
    name: str
    location: Location
    demand: int
    min_start_time: datetime
    max_end_time: datetime
    service_duration: timedelta
    vehicle: Annotated[
        Optional["Vehicle"],
        InverseRelationShadowVariable(source_variable_name="visits"),
    ] = None
    previous_visit: Annotated[
        Optional["Visit"], PreviousElementShadowVariable(source_variable_name="visits")
    ] = None
    next_visit: Annotated[
        Optional["Visit"], NextElementShadowVariable(source_variable_name="visits")
    ] = None
    arrival_time: Annotated[
        Optional[datetime],
        CascadingUpdateShadowVariable(target_method_name="update_arrival_time"),
    ] = None

    def update_arrival_time(self):
        if self.vehicle is None or (
            self.previous_visit is not None and self.previous_visit.arrival_time is None
        ):
            self.arrival_time = None
        elif self.previous_visit is None:
            self.arrival_time = self.vehicle.departure_time + timedelta(
                seconds=self.vehicle.home_location.driving_time_to(self.location)
            )
        else:
            self.arrival_time = (
                self.previous_visit.calculate_departure_time()
                + timedelta(
                    seconds=self.previous_visit.location.driving_time_to(self.location)
                )
            )

    def calculate_departure_time(self):
        if self.arrival_time is None:
            return None

        return max(self.arrival_time, self.min_start_time) + self.service_duration

    @property
    def departure_time(self) -> Optional[datetime]:
        return self.calculate_departure_time()

    @property
    def start_service_time(self) -> Optional[datetime]:
        if self.arrival_time is None:
            return None
        return max(self.arrival_time, self.min_start_time)

    def is_service_finished_after_max_end_time(self) -> bool:
        return (
            self.arrival_time is not None
            and self.calculate_departure_time() > self.max_end_time
        )

    def service_finished_delay_in_minutes(self) -> int:
        if self.arrival_time is None:
            return 0
        # Round up to next minute using the negative division trick:
        # ex: 30 seconds / -1 minute = -0.5,
        # so 30 seconds // -1 minute = -1,
        # and negating that gives 1
        return -(
            (self.calculate_departure_time() - self.max_end_time)
            // timedelta(minutes=-1)
        )

    @property
    def driving_time_seconds_from_previous_standstill(self) -> Optional[int]:
        if self.vehicle is None:
            return None

        if self.previous_visit is None:
            return self.vehicle.home_location.driving_time_to(self.location)
        else:
            return self.previous_visit.location.driving_time_to(self.location)

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"Visit({self.id})"


@planning_entity
@dataclass
class Vehicle:
    id: Annotated[str, PlanningId]
    name: str
    capacity: int
    home_location: Location
    departure_time: datetime
    visits: Annotated[list[Visit], PlanningListVariable] = field(default_factory=list)

    @property
    def arrival_time(self) -> datetime:
        if len(self.visits) == 0:
            return self.departure_time
        return self.visits[-1].departure_time + timedelta(
            seconds=self.visits[-1].location.driving_time_to(self.home_location)
        )

    @property
    def total_demand(self) -> int:
        return self.calculate_total_demand()

    @property
    def total_driving_time_seconds(self) -> int:
        return self.calculate_total_driving_time_seconds()

    def calculate_total_demand(self) -> int:
        total_demand = 0
        for visit in self.visits:
            total_demand += visit.demand
        return total_demand

    def calculate_total_driving_time_seconds(self) -> int:
        if len(self.visits) == 0:
            return 0
        total_driving_time_seconds = 0
        previous_location = self.home_location

        for visit in self.visits:
            total_driving_time_seconds += previous_location.driving_time_to(
                visit.location
            )
            previous_location = visit.location

        total_driving_time_seconds += previous_location.driving_time_to(
            self.home_location
        )
        return total_driving_time_seconds

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Vehicle({self.id}, {self.name})"


@planning_solution
@dataclass
class VehicleRoutePlan:
    name: str
    south_west_corner: Location
    north_east_corner: Location
    vehicles: Annotated[list[Vehicle], PlanningEntityCollectionProperty]
    visits: Annotated[list[Visit], PlanningEntityCollectionProperty, ValueRangeProvider]
    score: Annotated[Optional[HardSoftScore], PlanningScore] = None
    solver_status: SolverStatus = SolverStatus.NOT_SOLVING

    @property
    def total_driving_time_seconds(self) -> int:
        out = 0
        for vehicle in self.vehicles:
            out += vehicle.total_driving_time_seconds
        return out

    def __str__(self):
        return f"VehicleRoutePlan(name={self.name}, vehicles={self.vehicles}, visits={self.visits})"


# Pydantic REST models for API (used for deserialization and context)
class LocationModel(JsonDomainBase):
    latitude: float
    longitude: float


class VisitModel(JsonDomainBase):
    id: str
    name: str
    location: List[float]  # [lat, lng] array
    demand: int
    min_start_time: str = Field(..., alias="minStartTime")  # ISO datetime string
    max_end_time: str = Field(..., alias="maxEndTime")  # ISO datetime string
    service_duration: int = Field(..., alias="serviceDuration")  # Duration in seconds
    vehicle: Union[str, "VehicleModel", None] = None
    previous_visit: Union[str, "VisitModel", None] = Field(None, alias="previousVisit")
    next_visit: Union[str, "VisitModel", None] = Field(None, alias="nextVisit")
    arrival_time: Optional[str] = Field(
        None, alias="arrivalTime"
    )  # ISO datetime string
    departure_time: Optional[str] = Field(
        None, alias="departureTime"
    )  # ISO datetime string
    driving_time_seconds_from_previous_standstill: Optional[int] = Field(
        None, alias="drivingTimeSecondsFromPreviousStandstill"
    )


class VehicleModel(JsonDomainBase):
    id: str
    name: str
    capacity: int
    home_location: List[float] = Field(..., alias="homeLocation")  # [lat, lng] array
    departure_time: str = Field(..., alias="departureTime")  # ISO datetime string
    visits: List[Union[str, VisitModel]] = Field(default_factory=list)
    total_demand: int = Field(0, alias="totalDemand")
    total_driving_time_seconds: int = Field(0, alias="totalDrivingTimeSeconds")
    arrival_time: Optional[str] = Field(
        None, alias="arrivalTime"
    )  # ISO datetime string


class VehicleRoutePlanModel(JsonDomainBase):
    name: str
    south_west_corner: List[float] = Field(
        ..., alias="southWestCorner"
    )  # [lat, lng] array
    north_east_corner: List[float] = Field(
        ..., alias="northEastCorner"
    )  # [lat, lng] array
    vehicles: List[VehicleModel]
    visits: List[VisitModel]
    score: Optional[str] = None
    solver_status: Optional[str] = None
    total_driving_time_seconds: int = Field(0, alias="totalDrivingTimeSeconds")
