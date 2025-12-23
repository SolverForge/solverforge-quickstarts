from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.domain import (
    planning_entity,
    planning_solution,
    PlanningId,
    PlanningVariable,
    PlanningEntityCollectionProperty,
    ProblemFactCollectionProperty,
    ValueRangeProvider,
    PlanningScore,
)
from solverforge_legacy.solver.score import HardSoftDecimalScore
from datetime import datetime, date
from typing import Annotated, List, Optional, Union
from dataclasses import dataclass, field
from .json_serialization import JsonDomainBase
from pydantic import Field


@dataclass
class Employee:
    name: Annotated[str, PlanningId]
    skills: set[str] = field(default_factory=set)
    unavailable_dates: set[date] = field(default_factory=set)
    undesired_dates: set[date] = field(default_factory=set)
    desired_dates: set[date] = field(default_factory=set)


@planning_entity
@dataclass
class Shift:
    id: Annotated[str, PlanningId]
    start: datetime
    end: datetime
    location: str
    required_skill: str
    employee: Annotated[Employee | None, PlanningVariable] = None

    def has_required_skill(self) -> bool:
        """Check if assigned employee has the required skill."""
        if self.employee is None:
            return False
        return self.required_skill in self.employee.skills

    def is_overlapping_with_date(self, dt: date) -> bool:
        """Check if shift overlaps with a specific date."""
        return self.start.date() == dt or self.end.date() == dt

    def get_overlapping_duration_in_minutes(self, dt: date) -> int:
        """Calculate overlap duration in minutes for a specific date."""
        start_date_time = datetime.combine(dt, datetime.min.time())
        end_date_time = datetime.combine(dt, datetime.max.time())

        # Calculate overlap between date range and shift range
        max_start_time = max(start_date_time, self.start)
        min_end_time = min(end_date_time, self.end)

        minutes = (min_end_time - max_start_time).total_seconds() / 60
        return int(max(0, minutes))


@planning_solution
@dataclass
class EmployeeSchedule:
    employees: Annotated[
        list[Employee], ProblemFactCollectionProperty, ValueRangeProvider
    ]
    shifts: Annotated[list[Shift], PlanningEntityCollectionProperty]
    score: Annotated[HardSoftDecimalScore | None, PlanningScore] = None
    solver_status: SolverStatus = SolverStatus.NOT_SOLVING


# Pydantic REST models for API (used for deserialization and context)
class EmployeeModel(JsonDomainBase):
    name: str
    skills: List[str] = Field(default_factory=list)
    unavailable_dates: List[str] = Field(default_factory=list, alias="unavailableDates")
    undesired_dates: List[str] = Field(default_factory=list, alias="undesiredDates")
    desired_dates: List[str] = Field(default_factory=list, alias="desiredDates")


class ShiftModel(JsonDomainBase):
    id: str
    start: str  # ISO datetime string
    end: str  # ISO datetime string
    location: str
    required_skill: str = Field(..., alias="requiredSkill")
    employee: Union[str, EmployeeModel, None] = None


class EmployeeScheduleModel(JsonDomainBase):
    employees: List[EmployeeModel]
    shifts: List[ShiftModel]
    score: Optional[str] = None
    solver_status: Optional[str] = None
