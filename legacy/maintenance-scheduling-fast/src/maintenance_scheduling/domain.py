from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Annotated, Union, Set

from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.score import HardSoftScore
from solverforge_legacy.solver.domain import (
    planning_entity,
    planning_solution,
    PlanningId,
    PlanningVariable,
    PlanningEntityCollectionProperty,
    ProblemFactCollectionProperty,
    ProblemFactProperty,
    ValueRangeProvider,
    PlanningScore,
)
from .json_serialization import JsonDomainBase
from pydantic import Field


# ************************************************************************
# Utility functions for working day calculations
# ************************************************************************


def calculate_end_date(start_date: Optional[date], duration_in_days: int) -> Optional[date]:
    """
    Calculate the end date by adding working days to the start date, skipping weekends.

    The end date is exclusive (like Java's implementation).

    Args:
        start_date: The start date (inclusive)
        duration_in_days: Number of working days the job takes

    Returns:
        The end date (exclusive), or None if start_date is None
    """
    if start_date is None:
        return None

    # Skip weekends. Does not work for holidays.
    # Keep in sync with create_start_date_range().
    # Formula: For every 5 working days plus the weekday offset, add 2 weekend days
    # Python weekday(): Monday=0, Tuesday=1, ..., Sunday=6
    weekend_padding = 2 * ((duration_in_days + start_date.weekday()) // 5)
    return start_date + timedelta(days=duration_in_days + weekend_padding)


def count_working_days_between(start: date, end: date) -> int:
    """
    Count the number of working days (Mon-Fri) between two dates.

    Args:
        start: Start date (inclusive)
        end: End date (exclusive)

    Returns:
        Number of working days between the dates
    """
    if start >= end:
        return 0

    count = 0
    current = start
    while current < end:
        if current.weekday() < 5:  # Monday=0 to Friday=4
            count += 1
        current += timedelta(days=1)
    return count


def create_start_date_range(from_date: date, to_date: date) -> List[date]:
    """
    Generate a list of working days (Mon-Fri) within the date range.

    Args:
        from_date: Start of range (inclusive)
        to_date: End of range (exclusive)

    Returns:
        List of working days in the range
    """
    dates = []
    current = from_date
    while current < to_date:
        if current.weekday() < 5:  # Monday=0 to Friday=4
            dates.append(current)
        current += timedelta(days=1)
    return dates


# ************************************************************************
# Domain classes
# ************************************************************************


@dataclass
class WorkCalendar:
    """Defines the planning window for the schedule."""
    id: Annotated[str, PlanningId]
    from_date: date  # Inclusive
    to_date: date    # Exclusive


@dataclass
class Crew:
    """A maintenance crew that can be assigned to jobs."""
    id: Annotated[str, PlanningId]
    name: str

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Crew):
            return self.id == other.id
        return False

    def __str__(self):
        return f"{self.name}({self.id})"


@planning_entity
@dataclass
class Job:
    """
    A maintenance job that needs to be scheduled.

    Planning variables:
    - crew: The crew assigned to this job
    - start_date: When the job starts (inclusive)

    The end_date is computed from start_date and duration_in_days.
    """
    id: Annotated[str, PlanningId]
    name: str
    duration_in_days: int
    min_start_date: date    # Inclusive - earliest the job can start
    max_end_date: date      # Exclusive - latest the job can end
    ideal_end_date: date    # Exclusive - preferred end date
    tags: Set[str] = field(default_factory=set)

    # Planning variables
    crew: Annotated[Optional[Crew], PlanningVariable] = None
    start_date: Annotated[Optional[date], PlanningVariable] = None

    def get_end_date(self) -> Optional[date]:
        """Calculate the end date based on start_date and duration."""
        return calculate_end_date(self.start_date, self.duration_in_days)

    @property
    def end_date(self) -> Optional[date]:
        """End date property for convenient access."""
        return self.get_end_date()

    def calculate_overlap(self, other: "Job") -> int:
        """
        Calculate the number of overlapping working days with another job.

        Args:
            other: The other job to compare with

        Returns:
            Number of overlapping working days
        """
        if self.start_date is None or other.start_date is None:
            return 0

        self_end = self.get_end_date()
        other_end = other.get_end_date()

        if self_end is None or other_end is None:
            return 0

        # Calculate overlap range
        overlap_start = max(self.start_date, other.start_date)
        overlap_end = min(self_end, other_end)

        if overlap_start >= overlap_end:
            return 0

        return count_working_days_between(overlap_start, overlap_end)

    def get_common_tags(self, other: "Job") -> Set[str]:
        """Get the tags that both jobs share."""
        return self.tags & other.tags

    def __str__(self):
        return f"{self.name}({self.id})"


@planning_solution
@dataclass
class MaintenanceSchedule:
    """
    The planning solution containing the schedule to be optimized.
    """
    work_calendar: Annotated[WorkCalendar, ProblemFactProperty]
    crews: Annotated[List[Crew], ProblemFactCollectionProperty, ValueRangeProvider]
    jobs: Annotated[List[Job], PlanningEntityCollectionProperty]
    start_date_range: Annotated[
        List[date], ProblemFactCollectionProperty, ValueRangeProvider
    ] = field(default_factory=list)
    score: Annotated[Optional[HardSoftScore], PlanningScore] = None
    solver_status: SolverStatus = SolverStatus.NOT_SOLVING

    def __post_init__(self):
        """Initialize start_date_range if not provided."""
        if not self.start_date_range and self.work_calendar:
            self.start_date_range = create_start_date_range(
                self.work_calendar.from_date,
                self.work_calendar.to_date
            )


# ************************************************************************
# Pydantic REST models for API
# ************************************************************************


class WorkCalendarModel(JsonDomainBase):
    id: str
    from_date: str = Field(..., alias="fromDate")  # ISO date string
    to_date: str = Field(..., alias="toDate")


class CrewModel(JsonDomainBase):
    id: str
    name: str


class JobModel(JsonDomainBase):
    id: str
    name: str
    duration_in_days: int = Field(..., alias="durationInDays")
    min_start_date: str = Field(..., alias="minStartDate")
    max_end_date: str = Field(..., alias="maxEndDate")
    ideal_end_date: str = Field(..., alias="idealEndDate")
    tags: List[str] = Field(default_factory=list)
    crew: Optional[Union[str, CrewModel]] = None
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")


class MaintenanceScheduleModel(JsonDomainBase):
    work_calendar: WorkCalendarModel = Field(..., alias="workCalendar")
    crews: List[CrewModel]
    jobs: List[JobModel]
    start_date_range: List[str] = Field(default_factory=list, alias="startDateRange")
    score: Optional[str] = None
    solver_status: Optional[str] = Field(None, alias="solverStatus")
