"""
Unit tests for the maintenance scheduling constraints using ConstraintVerifier.
"""

from datetime import date, timedelta

from solverforge_legacy.solver.test import ConstraintVerifier

from maintenance_scheduling.domain import (
    Crew,
    Job,
    MaintenanceSchedule,
    WorkCalendar,
    calculate_end_date,
)
from maintenance_scheduling.constraints import (
    define_constraints,
    crew_conflict,
    min_start_date,
    max_end_date,
    before_ideal_end_date,
    after_ideal_end_date,
    tag_conflict,
)


# Test fixtures
CREW_A = Crew(id="A", name="Crew A")
CREW_B = Crew(id="B", name="Crew B")
START_DATE = date(2024, 1, 8)  # A Monday
WORK_CALENDAR = WorkCalendar(
    id="cal",
    from_date=START_DATE,
    to_date=START_DATE + timedelta(days=60)
)


constraint_verifier = ConstraintVerifier.build(
    define_constraints, MaintenanceSchedule, Job
)


def create_job(
    job_id: str,
    duration: int = 3,
    crew: Crew = None,
    start_offset: int = 0,
    tags: set = None,
    min_start_offset: int = 0,
    max_end_offset: int = 30,
    ideal_end_offset: int = 20,
) -> Job:
    """Helper function to create a Job with computed dates."""
    start = calculate_end_date(START_DATE, start_offset) if crew else None
    min_start = calculate_end_date(START_DATE, min_start_offset)
    max_end = calculate_end_date(START_DATE, max_end_offset)
    ideal_end = calculate_end_date(START_DATE, ideal_end_offset)

    return Job(
        id=job_id,
        name=f"Job {job_id}",
        duration_in_days=duration,
        min_start_date=min_start,
        max_end_date=max_end,
        ideal_end_date=ideal_end,
        tags=tags or set(),
        crew=crew,
        start_date=start,
    )


# ************************************************************************
# Crew conflict tests
# ************************************************************************


def test_crew_conflict_no_overlap():
    """Two jobs with same crew but no time overlap should not penalize."""
    # Job 1: days 0-2 (3 days)
    job1 = create_job("1", duration=3, crew=CREW_A, start_offset=0)
    # Job 2: days 5-7 (3 days) - no overlap
    job2 = create_job("2", duration=3, crew=CREW_A, start_offset=5)

    constraint_verifier.verify_that(crew_conflict).given(job1, job2).penalizes_by(0)


def test_crew_conflict_with_overlap():
    """Two jobs with same crew and overlapping dates should penalize."""
    # Job 1: days 0-4 (5 days)
    job1 = create_job("1", duration=5, crew=CREW_A, start_offset=0)
    # Job 2: days 3-7 (5 days) - overlaps on days 3-4
    job2 = create_job("2", duration=5, crew=CREW_A, start_offset=3)

    # Should penalize for the overlap
    constraint_verifier.verify_that(crew_conflict).given(job1, job2).penalizes()


def test_different_crews_no_conflict():
    """Two overlapping jobs with different crews should not penalize."""
    job1 = create_job("1", duration=5, crew=CREW_A, start_offset=0)
    job2 = create_job("2", duration=5, crew=CREW_B, start_offset=2)

    constraint_verifier.verify_that(crew_conflict).given(job1, job2).penalizes_by(0)


# ************************************************************************
# Min start date tests
# ************************************************************************


def test_min_start_date_valid():
    """Job starting on or after min start date should not penalize."""
    job = create_job(
        "1",
        duration=3,
        crew=CREW_A,
        start_offset=5,
        min_start_offset=0,  # Can start from day 0
    )

    constraint_verifier.verify_that(min_start_date).given(job).penalizes_by(0)


def test_min_start_date_violation():
    """Job starting before min start date should penalize."""
    job = create_job(
        "1",
        duration=3,
        crew=CREW_A,
        start_offset=0,
        min_start_offset=5,  # Can't start until day 5
    )

    # Started 5 days early
    constraint_verifier.verify_that(min_start_date).given(job).penalizes()


# ************************************************************************
# Max end date tests
# ************************************************************************


def test_max_end_date_valid():
    """Job ending on or before max end date should not penalize."""
    job = create_job(
        "1",
        duration=3,
        crew=CREW_A,
        start_offset=0,
        max_end_offset=30,  # Due day 30
    )

    constraint_verifier.verify_that(max_end_date).given(job).penalizes_by(0)


def test_max_end_date_violation():
    """Job ending after max end date should penalize."""
    job = create_job(
        "1",
        duration=10,
        crew=CREW_A,
        start_offset=0,
        max_end_offset=5,  # Due day 5, but job takes 10 days
    )

    constraint_verifier.verify_that(max_end_date).given(job).penalizes()


# ************************************************************************
# Before ideal end date tests
# ************************************************************************


def test_before_ideal_end_date_valid():
    """Job ending at or after ideal end date should not penalize."""
    job = create_job(
        "1",
        duration=15,
        crew=CREW_A,
        start_offset=0,
        ideal_end_offset=10,  # Ideal by day 10, job ends after
    )

    constraint_verifier.verify_that(before_ideal_end_date).given(job).penalizes_by(0)


def test_before_ideal_end_date_violation():
    """Job ending before ideal end date should penalize."""
    job = create_job(
        "1",
        duration=3,
        crew=CREW_A,
        start_offset=0,
        ideal_end_offset=20,  # Ideal by day 20, but job ends day 3
    )

    constraint_verifier.verify_that(before_ideal_end_date).given(job).penalizes()


# ************************************************************************
# After ideal end date tests
# ************************************************************************


def test_after_ideal_end_date_valid():
    """Job ending at or before ideal end date should not penalize."""
    job = create_job(
        "1",
        duration=3,
        crew=CREW_A,
        start_offset=0,
        ideal_end_offset=20,  # Ideal by day 20
    )

    constraint_verifier.verify_that(after_ideal_end_date).given(job).penalizes_by(0)


def test_after_ideal_end_date_violation():
    """Job ending after ideal end date should penalize heavily."""
    job = create_job(
        "1",
        duration=10,
        crew=CREW_A,
        start_offset=0,
        ideal_end_offset=5,  # Ideal by day 5, but job takes 10 days
    )

    constraint_verifier.verify_that(after_ideal_end_date).given(job).penalizes()


# ************************************************************************
# Tag conflict tests
# ************************************************************************


def test_tag_conflict_no_common_tags():
    """Overlapping jobs with no common tags should not penalize."""
    job1 = create_job("1", duration=5, crew=CREW_A, start_offset=0, tags={"Downtown"})
    job2 = create_job("2", duration=5, crew=CREW_B, start_offset=2, tags={"Airport"})

    constraint_verifier.verify_that(tag_conflict).given(job1, job2).penalizes_by(0)


def test_tag_conflict_with_common_tags():
    """Overlapping jobs with common tags should penalize."""
    job1 = create_job(
        "1", duration=5, crew=CREW_A, start_offset=0,
        tags={"Downtown", "Subway"}
    )
    job2 = create_job(
        "2", duration=5, crew=CREW_B, start_offset=2,
        tags={"Downtown"}  # Shares "Downtown" tag
    )

    constraint_verifier.verify_that(tag_conflict).given(job1, job2).penalizes()


def test_tag_conflict_no_overlap():
    """Non-overlapping jobs with common tags should not penalize."""
    job1 = create_job("1", duration=3, crew=CREW_A, start_offset=0, tags={"Downtown"})
    job2 = create_job("2", duration=3, crew=CREW_B, start_offset=10, tags={"Downtown"})

    constraint_verifier.verify_that(tag_conflict).given(job1, job2).penalizes_by(0)
