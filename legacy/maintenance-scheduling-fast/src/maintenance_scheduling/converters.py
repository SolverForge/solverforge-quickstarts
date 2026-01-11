"""
Converters for bidirectional transformation between domain objects and API models.
"""

from datetime import date
from typing import Dict, List, Optional

from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.score import HardSoftScore

from . import domain


# ************************************************************************
# Helper functions
# ************************************************************************


def date_to_iso(d: Optional[date]) -> Optional[str]:
    """Convert a date to ISO format string."""
    return d.isoformat() if d else None


def iso_to_date(s: Optional[str]) -> Optional[date]:
    """Convert an ISO format string to a date."""
    return date.fromisoformat(s) if s else None


# ************************************************************************
# Domain -> Model conversions
# ************************************************************************


def work_calendar_to_model(wc: domain.WorkCalendar) -> domain.WorkCalendarModel:
    """Convert a WorkCalendar domain object to its API model."""
    return domain.WorkCalendarModel(
        id=wc.id,
        from_date=date_to_iso(wc.from_date),
        to_date=date_to_iso(wc.to_date),
    )


def crew_to_model(crew: domain.Crew) -> domain.CrewModel:
    """Convert a Crew domain object to its API model."""
    return domain.CrewModel(id=crew.id, name=crew.name)


def job_to_model(job: domain.Job) -> domain.JobModel:
    """Convert a Job domain object to its API model."""
    return domain.JobModel(
        id=job.id,
        name=job.name,
        duration_in_days=job.duration_in_days,
        min_start_date=date_to_iso(job.min_start_date),
        max_end_date=date_to_iso(job.max_end_date),
        ideal_end_date=date_to_iso(job.ideal_end_date),
        tags=list(job.tags),
        crew=crew_to_model(job.crew) if job.crew else None,
        start_date=date_to_iso(job.start_date),
        end_date=date_to_iso(job.get_end_date()),
    )


def schedule_to_model(schedule: domain.MaintenanceSchedule) -> domain.MaintenanceScheduleModel:
    """Convert a MaintenanceSchedule domain object to its API model."""
    return domain.MaintenanceScheduleModel(
        work_calendar=work_calendar_to_model(schedule.work_calendar),
        crews=[crew_to_model(c) for c in schedule.crews],
        jobs=[job_to_model(j) for j in schedule.jobs],
        start_date_range=[date_to_iso(d) for d in schedule.start_date_range],
        score=str(schedule.score) if schedule.score else None,
        solver_status=schedule.solver_status.name if schedule.solver_status else None,
    )


# ************************************************************************
# Model -> Domain conversions
# ************************************************************************


def model_to_work_calendar(model: domain.WorkCalendarModel) -> domain.WorkCalendar:
    """Convert a WorkCalendarModel to its domain object."""
    return domain.WorkCalendar(
        id=model.id,
        from_date=iso_to_date(model.from_date),
        to_date=iso_to_date(model.to_date),
    )


def model_to_crew(model: domain.CrewModel) -> domain.Crew:
    """Convert a CrewModel to its domain object."""
    return domain.Crew(id=model.id, name=model.name)


def model_to_schedule(model: domain.MaintenanceScheduleModel) -> domain.MaintenanceSchedule:
    """
    Convert a MaintenanceScheduleModel to its domain object.

    Handles reference resolution for crew assignments.
    """
    # Create work calendar
    work_calendar = model_to_work_calendar(model.work_calendar)

    # Create crews and lookup
    crews: List[domain.Crew] = [model_to_crew(c) for c in model.crews]
    crew_lookup: Dict[str, domain.Crew] = {c.id: c for c in crews}

    # Create jobs with crew references resolved
    jobs: List[domain.Job] = []
    for job_model in model.jobs:
        # Resolve crew reference
        crew = None
        if job_model.crew:
            if isinstance(job_model.crew, str):
                crew = crew_lookup.get(job_model.crew)
            elif isinstance(job_model.crew, domain.CrewModel):
                crew = crew_lookup.get(job_model.crew.id)

        job = domain.Job(
            id=job_model.id,
            name=job_model.name,
            duration_in_days=job_model.duration_in_days,
            min_start_date=iso_to_date(job_model.min_start_date),
            max_end_date=iso_to_date(job_model.max_end_date),
            ideal_end_date=iso_to_date(job_model.ideal_end_date),
            tags=set(job_model.tags) if job_model.tags else set(),
            crew=crew,
            start_date=iso_to_date(job_model.start_date) if job_model.start_date else None,
        )
        jobs.append(job)

    # Parse start_date_range
    start_date_range = (
        [iso_to_date(d) for d in model.start_date_range]
        if model.start_date_range
        else []
    )

    # Parse score
    score = None
    if model.score:
        score = HardSoftScore.parse(model.score)

    # Parse solver status
    solver_status = SolverStatus.NOT_SOLVING
    if model.solver_status:
        solver_status = SolverStatus[model.solver_status]

    return domain.MaintenanceSchedule(
        work_calendar=work_calendar,
        crews=crews,
        jobs=jobs,
        start_date_range=start_date_range,
        score=score,
        solver_status=solver_status,
    )
