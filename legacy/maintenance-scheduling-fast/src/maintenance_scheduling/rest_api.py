"""
FastAPI REST endpoints for the maintenance scheduling application.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from typing import Dict, List
from dataclasses import asdict
import logging

from .domain import MaintenanceSchedule, MaintenanceScheduleModel
from .converters import schedule_to_model, model_to_schedule
from .score_analysis import ConstraintAnalysisDTO, MatchAnalysisDTO
from .demo_data import generate_demo_data, DemoData
from .solver import solver_manager, solution_manager


logger = logging.getLogger(__name__)

app = FastAPI(docs_url='/q/swagger-ui')

data_sets: Dict[str, MaintenanceSchedule] = {}


# ************************************************************************
# Demo Data Endpoints
# ************************************************************************


@app.get("/demo-data")
async def get_demo_data_list() -> List[str]:
    """Get available demo data sets."""
    return [demo.name for demo in DemoData]


@app.get("/demo-data/{demo_name}", response_model=MaintenanceScheduleModel)
async def get_demo_data_by_name(demo_name: str) -> MaintenanceScheduleModel:
    """Get a specific demo data set."""
    try:
        demo = DemoData[demo_name]
        schedule = generate_demo_data(demo)
        return schedule_to_model(schedule)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Demo data '{demo_name}' not found")


# ************************************************************************
# Schedule Endpoints
# ************************************************************************


@app.get("/schedules")
async def list_schedules() -> List[str]:
    """List the job IDs of all submitted schedules."""
    return list(data_sets.keys())


@app.post("/schedules")
async def solve_schedule(model: MaintenanceScheduleModel) -> str:
    """
    Submit a schedule for solving.

    Returns the job ID that can be used to track progress and retrieve results.
    """
    job_id = str(uuid4())
    schedule = model_to_schedule(model)
    data_sets[job_id] = schedule
    solver_manager.solve_and_listen(
        job_id,
        schedule,
        lambda solution: data_sets.update({job_id: solution})
    )
    return job_id


@app.get("/schedules/{job_id}", response_model=MaintenanceScheduleModel)
async def get_schedule(job_id: str) -> MaintenanceScheduleModel:
    """Get the current solution for a job."""
    schedule = data_sets.get(job_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.solver_status = solver_manager.get_solver_status(job_id)
    return schedule_to_model(schedule)


@app.get("/schedules/{job_id}/status")
async def get_schedule_status(job_id: str) -> dict:
    """Get the status and score for a job (lightweight, without full solution)."""
    schedule = data_sets.get(job_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    solver_status = solver_manager.get_solver_status(job_id)
    return {
        "score": str(schedule.score) if schedule.score else None,
        "solverStatus": solver_status.name if solver_status else None,
    }


@app.delete("/schedules/{job_id}", response_model=MaintenanceScheduleModel)
async def stop_solving(job_id: str) -> MaintenanceScheduleModel:
    """Terminate solving and return the best solution so far."""
    solver_manager.terminate_early(job_id)
    schedule = data_sets.get(job_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.solver_status = solver_manager.get_solver_status(job_id)
    return schedule_to_model(schedule)


# ************************************************************************
# Score Analysis Endpoint
# ************************************************************************


@app.put("/schedules/analyze")
async def analyze_schedule(model: MaintenanceScheduleModel) -> dict:
    """
    Analyze the constraints in a schedule.

    Returns detailed information about which constraints are satisfied or violated.
    """
    schedule = model_to_schedule(model)
    analysis = solution_manager.analyze(schedule)
    constraints = []
    for constraint in getattr(analysis, 'constraint_analyses', []) or []:
        matches = [
            MatchAnalysisDTO(
                name=str(getattr(getattr(match, 'constraint_ref', None), 'constraint_name', "")),
                score=str(getattr(match, 'score', "0hard/0soft")),
                justification=str(getattr(match, 'justification', ""))
            )
            for match in getattr(constraint, 'matches', []) or []
        ]
        constraints.append(ConstraintAnalysisDTO(
            name=str(getattr(constraint, 'constraint_name', "")),
            weight=str(getattr(constraint, 'weight', "0hard/0soft")),
            score=str(getattr(constraint, 'score', "0hard/0soft")),
            matches=matches
        ))
    return {"constraints": [asdict(constraint) for constraint in constraints]}


# ************************************************************************
# Health Check Endpoint
# ************************************************************************


@app.get("/healthz")
async def healthz():
    return {"status": "UP"}


# ************************************************************************
# Static Files
# ************************************************************************


app.mount("/", StaticFiles(directory="static", html=True), name="static")
