from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from dataclasses import replace
from typing import Dict, List

from .domain import EmployeeSchedule, EmployeeScheduleModel
from .converters import (
    schedule_to_model, model_to_schedule
)
from .demo_data import DemoData, generate_demo_data
from .solver import solver_manager, solution_manager
from .score_analysis import ConstraintAnalysisDTO, MatchAnalysisDTO

app = FastAPI(docs_url='/q/swagger-ui')
data_sets: dict[str, EmployeeSchedule] = {}


@app.get("/demo-data")
async def demo_data_list() -> list[DemoData]:
    return [e for e in DemoData]


@app.get("/demo-data/{dataset_id}", response_model_exclude_none=True)
async def get_demo_data(dataset_id: str) -> EmployeeScheduleModel:
    demo_data = getattr(DemoData, dataset_id)
    domain_schedule = generate_demo_data(demo_data)
    return schedule_to_model(domain_schedule)


@app.get("/schedules/{problem_id}", response_model_exclude_none=True)
async def get_timetable(problem_id: str) -> EmployeeScheduleModel:
    schedule = data_sets[problem_id]
    updated_schedule = replace(schedule, solver_status=solver_manager.get_solver_status(problem_id))
    return schedule_to_model(updated_schedule)


def update_schedule(problem_id: str, schedule: EmployeeSchedule):
    global data_sets
    data_sets[problem_id] = schedule


@app.post("/schedules")
async def solve_timetable(schedule_model: EmployeeScheduleModel) -> str:
    job_id = str(uuid4())
    schedule = model_to_schedule(schedule_model)
    data_sets[job_id] = schedule
    solver_manager.solve_and_listen(job_id, schedule,
                                    lambda solution: update_schedule(job_id, solution))
    return job_id


@app.get("/schedules")
async def list_schedules() -> List[str]:
    """List all job IDs of submitted schedules."""
    return list(data_sets.keys())


@app.get("/schedules/{problem_id}/status")
async def get_status(problem_id: str) -> Dict:
    """Get the schedule status and score for a given job ID."""
    if problem_id not in data_sets:
        raise ValueError(f"No schedule found with ID {problem_id}")

    schedule = data_sets[problem_id]
    solver_status = solver_manager.get_solver_status(problem_id)

    return {
        "score": {
            "hardScore": schedule.score.hard_score if schedule.score else 0,
            "softScore": schedule.score.soft_score if schedule.score else 0,
        },
        "solverStatus": solver_status.name,
    }


@app.delete("/schedules/{problem_id}")
async def stop_solving(problem_id: str) -> EmployeeScheduleModel:
    """Terminate solving for a given job ID."""
    if problem_id not in data_sets:
        raise ValueError(f"No schedule found with ID {problem_id}")

    try:
        solver_manager.terminate_early(problem_id)
    except Exception as e:
        print(f"Warning: terminate_early failed for {problem_id}: {e}")

    return await get_timetable(problem_id)


@app.put("/schedules/analyze")
async def analyze_schedule(request: Request) -> Dict:
    """Submit a schedule to analyze its score."""
    json_data = await request.json()

    # Parse the incoming JSON using Pydantic models
    schedule_model = EmployeeScheduleModel.model_validate(json_data)

    # Convert to domain model for analysis
    domain_schedule = model_to_schedule(schedule_model)

    analysis = solution_manager.analyze(domain_schedule)

    # Convert to proper DTOs for correct serialization
    # Use str() for scores and justification to avoid Java object serialization issues
    constraints = []
    for constraint in getattr(analysis, 'constraint_analyses', []) or []:
        matches = [
            MatchAnalysisDTO(
                name=str(getattr(getattr(match, 'constraint_ref', None), 'constraint_name', "")),
                score=str(getattr(match, 'score', "0hard/0soft")),
                justification=str(getattr(match, 'justification', "")),
            )
            for match in getattr(constraint, 'matches', []) or []
        ]

        constraint_dto = ConstraintAnalysisDTO(
            name=str(getattr(constraint, 'constraint_name', "")),
            weight=str(getattr(constraint, 'weight', "0hard/0soft")),
            score=str(getattr(constraint, 'score', "0hard/0soft")),
            matches=matches,
        )
        constraints.append(constraint_dto)

    return {"constraints": [constraint.model_dump() for constraint in constraints]}


@app.get("/healthz")
async def healthz():
    return {"status": "UP"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
