from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from typing import Dict, List
from dataclasses import asdict
from enum import Enum
import logging

from .domain import VMPlacementPlan, VMPlacementPlanModel
from .converters import plan_to_model, model_to_plan
from .demo_data import generate_demo_data, DemoData
from .solver import solver_manager, solution_manager
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(docs_url='/q/swagger-ui')

data_sets: Dict[str, VMPlacementPlan] = {}


class ConstraintMatchDTO(BaseModel):
    name: str
    score: str
    justification: str


class ConstraintAnalysisDTO(BaseModel):
    name: str
    weight: str
    score: str
    matches: List[ConstraintMatchDTO]


@app.get("/demo-data")
async def get_demo_data():
    """Get available demo data sets."""
    return [demo.name for demo in DemoData]


@app.get("/demo-data/{demo_name}", response_model=VMPlacementPlanModel)
async def get_demo_data_by_name(demo_name: str) -> VMPlacementPlanModel:
    """Get a specific demo data set."""
    try:
        demo_data = DemoData[demo_name]
        domain_plan = generate_demo_data(demo_data)
        return plan_to_model(domain_plan)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Demo data '{demo_name}' not found")


@app.get("/placements/{problem_id}", response_model=VMPlacementPlanModel, response_model_exclude_none=True)
async def get_placement(problem_id: str) -> VMPlacementPlanModel:
    """Get the current VM placement solution for a given job ID."""
    placement = data_sets.get(problem_id)
    if not placement:
        raise HTTPException(status_code=404, detail="Placement plan not found")
    placement.solver_status = solver_manager.get_solver_status(problem_id)
    return plan_to_model(placement)


@app.post("/placements")
async def solve_placement(plan_model: VMPlacementPlanModel) -> str:
    """Start solving a VM placement problem. Returns a job ID."""
    job_id = str(uuid4())
    domain_plan = model_to_plan(plan_model)
    data_sets[job_id] = domain_plan
    solver_manager.solve_and_listen(
        job_id,
        domain_plan,
        lambda solution: data_sets.update({job_id: solution})
    )
    return job_id


@app.put("/placements/analyze")
async def analyze_placement(plan_model: VMPlacementPlanModel) -> dict:
    """Analyze constraints for a given VM placement solution."""
    domain_plan = model_to_plan(plan_model)
    analysis = solution_manager.analyze(domain_plan)
    constraints = []
    for constraint in getattr(analysis, 'constraint_analyses', []) or []:
        matches = [
            ConstraintMatchDTO(
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
    return {"constraints": [c.model_dump() for c in constraints]}


@app.get("/placements")
async def list_placements() -> List[str]:
    """List the job IDs of all submitted placement problems."""
    return list(data_sets.keys())


@app.get("/placements/{problem_id}/status")
async def get_placement_status(problem_id: str) -> dict:
    """Get the placement status and score for a given job ID."""
    placement = data_sets.get(problem_id)
    if not placement:
        raise HTTPException(status_code=404, detail="Placement plan not found")
    solver_status = solver_manager.get_solver_status(problem_id)
    return {
        "name": placement.name,
        "score": str(placement.score) if placement.score else None,
        "solverStatus": solver_status.name if solver_status else None,
        "activeServers": placement.active_servers,
        "unassignedVms": placement.unassigned_vms,
    }


@app.delete("/placements/{problem_id}", response_model=VMPlacementPlanModel)
async def stop_solving(problem_id: str) -> VMPlacementPlanModel:
    """Terminate solving for a given job ID. Returns the best solution so far."""
    solver_manager.terminate_early(problem_id)
    placement = data_sets.get(problem_id)
    if not placement:
        raise HTTPException(status_code=404, detail="Placement plan not found")
    placement.solver_status = solver_manager.get_solver_status(problem_id)
    return plan_to_model(placement)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
