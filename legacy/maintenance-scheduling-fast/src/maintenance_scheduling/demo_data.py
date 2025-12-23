from datetime import date, timedelta
from enum import Enum
from random import Random
from typing import List

from .domain import (
    Crew,
    Job,
    MaintenanceSchedule,
    WorkCalendar,
    calculate_end_date,
    create_start_date_range,
)


class DemoData(Enum):
    SMALL = "SMALL"
    LARGE = "LARGE"


# Job area names for generating job names
JOB_AREA_NAMES = [
    "Downtown", "Uptown", "Park", "Airport", "Bay", "Hill", "Forest", "Station",
    "Hospital", "Harbor", "Market", "Fort", "Beach", "Garden", "River", "Springs",
    "Tower", "Mountain"
]

# Job target names for generating job names
JOB_TARGET_NAMES = [
    "Street", "Bridge", "Tunnel", "Highway", "Boulevard", "Avenue", "Square", "Plaza"
]


def _get_next_monday(from_date: date) -> date:
    """Get the next Monday on or after the given date."""
    days_until_monday = (7 - from_date.weekday()) % 7
    if days_until_monday == 0 and from_date.weekday() != 0:
        days_until_monday = 7
    return from_date + timedelta(days=days_until_monday)


def generate_demo_data(demo_data: DemoData) -> MaintenanceSchedule:
    """
    Generate demo data for the maintenance scheduling problem.

    Args:
        demo_data: The demo data type (SMALL or LARGE)

    Returns:
        A MaintenanceSchedule with crews, work calendar, and jobs
    """
    # Create crews
    crews: List[Crew] = [
        Crew(id="1", name="Alpha crew"),
        Crew(id="2", name="Beta crew"),
        Crew(id="3", name="Gamma crew"),
    ]
    if demo_data == DemoData.LARGE:
        crews.append(Crew(id="4", name="Delta crew"))
        crews.append(Crew(id="5", name="Epsilon crew"))

    # Create work calendar
    from_date = _get_next_monday(date.today())
    week_list_size = 16 if demo_data == DemoData.LARGE else 8
    to_date = from_date + timedelta(weeks=week_list_size)
    work_calendar = WorkCalendar(id="1", from_date=from_date, to_date=to_date)

    workday_total = week_list_size * 5

    # Create jobs
    jobs: List[Job] = []
    job_list_size = week_list_size * len(crews) * 3 // 5
    job_area_target_limit = min(len(JOB_TARGET_NAMES), len(crews) * 2)
    random = Random(17)  # Same seed as Java

    for i in range(job_list_size):
        job_area = JOB_AREA_NAMES[i // job_area_target_limit]
        job_target = JOB_TARGET_NAMES[i % job_area_target_limit]

        # 1 day to 2 workweeks (1 workweek on average)
        duration_in_days = 1 + random.randint(0, 9)

        # Calculate date constraints with at least 5 days of flexibility
        min_max_between_workdays = (
            duration_in_days + 5
            + random.randint(0, workday_total - (duration_in_days + 5) - 1)
        )
        min_workday_offset = random.randint(0, workday_total - min_max_between_workdays)
        min_ideal_end_between_workdays = min_max_between_workdays - 1 - random.randint(0, 3)

        # Calculate dates using the weekend-skipping calculation
        min_start_date = calculate_end_date(from_date, min_workday_offset)
        max_end_date = calculate_end_date(min_start_date, min_max_between_workdays)
        ideal_end_date = calculate_end_date(min_start_date, min_ideal_end_between_workdays)

        # 10% chance of having "Subway" tag
        if random.random() < 0.1:
            tags = {job_area, "Subway"}
        else:
            tags = {job_area}

        jobs.append(Job(
            id=str(i),
            name=f"{job_area} {job_target}",
            duration_in_days=duration_in_days,
            min_start_date=min_start_date,
            max_end_date=max_end_date,
            ideal_end_date=ideal_end_date,
            tags=tags,
        ))

    # Create and return the schedule
    schedule = MaintenanceSchedule(
        work_calendar=work_calendar,
        crews=crews,
        jobs=jobs,
    )

    # The start_date_range will be auto-populated by __post_init__
    # But let's ensure it's populated
    if not schedule.start_date_range:
        schedule.start_date_range = create_start_date_range(from_date, to_date)

    return schedule
