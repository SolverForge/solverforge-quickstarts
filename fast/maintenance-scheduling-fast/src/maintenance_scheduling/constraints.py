from solverforge_legacy.solver.score import (
    constraint_provider,
    HardSoftScore,
    Joiners,
    ConstraintFactory,
    Constraint,
)

from .domain import Job

# Constraint names
CREW_CONFLICT = "Crew conflict"
MIN_START_DATE = "Min start date"
MAX_END_DATE = "Max end date"
BEFORE_IDEAL_END_DATE = "Before ideal end date"
AFTER_IDEAL_END_DATE = "After ideal end date"
TAG_CONFLICT = "Tag conflict"


@constraint_provider
def define_constraints(constraint_factory: ConstraintFactory):
    """
    Defines all constraints for the maintenance scheduling problem.

    Args:
        constraint_factory: The constraint factory.

    Returns:
        List of all defined constraints.
    """
    return [
        # Hard constraints
        crew_conflict(constraint_factory),
        min_start_date(constraint_factory),
        max_end_date(constraint_factory),
        # Soft constraints
        before_ideal_end_date(constraint_factory),
        after_ideal_end_date(constraint_factory),
        tag_conflict(constraint_factory),
    ]


# ************************************************************************
# Hard constraints
# ************************************************************************


def crew_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    """
    A crew can do at most one maintenance job at the same time.

    Penalizes overlapping jobs assigned to the same crew, proportional to the
    number of overlapping days.
    """
    return (
        constraint_factory.for_each_unique_pair(
            Job,
            Joiners.equal(lambda job: job.crew),
            Joiners.overlapping(
                lambda job: job.start_date,
                lambda job: job.get_end_date(),
            ),
        )
        .filter(lambda job1, job2: job1.crew is not None)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda job1, job2: _calculate_overlap_days(job1, job2),
        )
        .as_constraint(CREW_CONFLICT)
    )


def min_start_date(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Don't start a maintenance job before it's ready to start.

    Penalizes jobs that start before their minimum start date, proportional
    to the number of days early.
    """
    return (
        constraint_factory.for_each(Job)
        .filter(
            lambda job: job.start_date is not None
            and job.min_start_date is not None
            and job.start_date < job.min_start_date
        )
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda job: (job.min_start_date - job.start_date).days,
        )
        .as_constraint(MIN_START_DATE)
    )


def max_end_date(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Don't end a maintenance job after it's due.

    Penalizes jobs that end after their maximum end date, proportional
    to the number of days late.
    """
    return (
        constraint_factory.for_each(Job)
        .filter(
            lambda job: job.get_end_date() is not None
            and job.max_end_date is not None
            and job.get_end_date() > job.max_end_date
        )
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda job: (job.get_end_date() - job.max_end_date).days,
        )
        .as_constraint(MAX_END_DATE)
    )


# ************************************************************************
# Soft constraints
# ************************************************************************


def before_ideal_end_date(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Early maintenance is expensive because maintenance cycles restart sooner.

    Penalizes jobs that finish before their ideal end date.
    Weight: 1 point per day early (lowest priority soft constraint).
    """
    return (
        constraint_factory.for_each(Job)
        .filter(
            lambda job: job.get_end_date() is not None
            and job.ideal_end_date is not None
            and job.get_end_date() < job.ideal_end_date
        )
        .penalize(
            HardSoftScore.ONE_SOFT,
            lambda job: (job.ideal_end_date - job.get_end_date()).days,
        )
        .as_constraint(BEFORE_IDEAL_END_DATE)
    )


def after_ideal_end_date(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Late maintenance is risky because delays can push it over the due date.

    Penalizes jobs that finish after their ideal end date.
    Weight: 1,000,000 points per day late (high priority soft constraint).
    """
    return (
        constraint_factory.for_each(Job)
        .filter(
            lambda job: job.get_end_date() is not None
            and job.ideal_end_date is not None
            and job.get_end_date() > job.ideal_end_date
        )
        .penalize(
            HardSoftScore.of_soft(1_000_000),
            lambda job: (job.get_end_date() - job.ideal_end_date).days,
        )
        .as_constraint(AFTER_IDEAL_END_DATE)
    )


def tag_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Avoid overlapping maintenance jobs with the same tag.

    For example, road maintenance in the same area should not overlap.
    Penalizes overlapping jobs that share tags, proportional to the number
    of shared tags and the overlap duration.
    Weight: 1,000 points per tag per day of overlap.
    """
    return (
        constraint_factory.for_each_unique_pair(
            Job,
            Joiners.overlapping(
                lambda job: job.start_date,
                lambda job: job.get_end_date(),
            ),
        )
        .filter(lambda job1, job2: len(job1.get_common_tags(job2)) > 0)
        .penalize(
            HardSoftScore.of_soft(1_000),
            lambda job1, job2: len(job1.get_common_tags(job2))
            * _calculate_overlap_days(job1, job2),
        )
        .as_constraint(TAG_CONFLICT)
    )


# ************************************************************************
# Helper functions
# ************************************************************************


def _calculate_overlap_days(job1: Job, job2: Job) -> int:
    """
    Calculate the number of overlapping calendar days between two jobs.

    Args:
        job1: First job
        job2: Second job

    Returns:
        Number of overlapping days (calendar days, not working days)
    """
    if job1.start_date is None or job2.start_date is None:
        return 0

    end1 = job1.get_end_date()
    end2 = job2.get_end_date()

    if end1 is None or end2 is None:
        return 0

    # Calculate overlap range
    overlap_start = max(job1.start_date, job2.start_date)
    overlap_end = min(end1, end2)

    if overlap_start >= overlap_end:
        return 0

    return (overlap_end - overlap_start).days
