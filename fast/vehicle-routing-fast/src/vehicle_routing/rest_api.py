from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from typing import Dict, List
from dataclasses import asdict

from .domain import VehicleRoutePlan
from .converters import plan_to_model, model_to_plan
from .domain import VehicleRoutePlanModel
from .score_analysis import ConstraintAnalysisDTO, MatchAnalysisDTO
from .demo_data import generate_demo_data, DemoData
from .solver import solver_manager, solution_manager
from pydantic import BaseModel, Field

app = FastAPI(docs_url='/q/swagger-ui')

data_sets: Dict[str, VehicleRoutePlan] = {}


# Request/Response models for recommendation endpoints
class VehicleRecommendation(BaseModel):
    """Recommendation for assigning a visit to a vehicle at a specific index."""
    vehicle_id: str = Field(..., alias="vehicleId")
    index: int

    class Config:
        populate_by_name = True


class RecommendedAssignmentResponse(BaseModel):
    """Response from the recommendation API."""
    proposition: VehicleRecommendation
    score_diff: str = Field(..., alias="scoreDiff")

    class Config:
        populate_by_name = True


class RecommendationRequest(BaseModel):
    """Request for visit assignment recommendations."""
    solution: VehicleRoutePlanModel
    visit_id: str = Field(..., alias="visitId")

    class Config:
        populate_by_name = True


class ApplyRecommendationRequest(BaseModel):
    """Request to apply a recommendation."""
    solution: VehicleRoutePlanModel
    visit_id: str = Field(..., alias="visitId")
    vehicle_id: str = Field(..., alias="vehicleId")
    index: int

    class Config:
        populate_by_name = True


def json_to_vehicle_route_plan(json_data: dict) -> VehicleRoutePlan:
    """Convert JSON data to VehicleRoutePlan using the model converters."""
    plan_model = VehicleRoutePlanModel.model_validate(json_data)
    return model_to_plan(plan_model)


@app.get("/demo-data")
async def get_demo_data():
    """Get available demo data sets."""
    return [demo.name for demo in DemoData]

@app.get("/demo-data/{demo_name}", response_model=VehicleRoutePlanModel)
async def get_demo_data_by_name(demo_name: str, distanceMode: str = "ON_DEMAND") -> VehicleRoutePlanModel:
    """
    Get a specific demo data set.

    Args:
        demo_name: Name of the demo dataset (PHILADELPHIA, HARTFORT, FIRENZE)
        distanceMode: Distance calculation mode:
            - ON_DEMAND: Calculate distances using Haversine formula on each call (default)
            - PRECOMPUTED: Pre-compute distance matrix for O(1) lookups (faster solving)
    """
    try:
        demo_data = DemoData[demo_name]
        use_precomputed = distanceMode == "PRECOMPUTED"
        domain_plan = generate_demo_data(demo_data, use_precomputed_matrix=use_precomputed)
        return plan_to_model(domain_plan)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Demo data '{demo_name}' not found")

@app.get("/route-plans/{problem_id}", response_model=VehicleRoutePlanModel, response_model_exclude_none=True)
async def get_route(problem_id: str) -> VehicleRoutePlanModel:
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")
    route.solver_status = solver_manager.get_solver_status(problem_id)
    return plan_to_model(route)

@app.post("/route-plans")
async def solve_route(plan_model: VehicleRoutePlanModel) -> str:
    job_id = str(uuid4())
    # Convert to domain model for solver
    domain_plan = model_to_plan(plan_model)
    data_sets[job_id] = domain_plan
    solver_manager.solve_and_listen(
        job_id,
        domain_plan,
        lambda solution: data_sets.update({job_id: solution})
    )
    return job_id

@app.put("/route-plans/analyze")
async def analyze_route(plan_model: VehicleRoutePlanModel) -> dict:
    domain_plan = model_to_plan(plan_model)
    analysis = solution_manager.analyze(domain_plan)
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

@app.get("/route-plans")
async def list_route_plans() -> List[str]:
    """List the job IDs of all submitted route plans."""
    return list(data_sets.keys())


@app.get("/route-plans/{problem_id}/status")
async def get_route_status(problem_id: str) -> dict:
    """Get the route plan status and score for a given job ID."""
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")
    solver_status = solver_manager.get_solver_status(problem_id)
    return {
        "name": route.name,
        "score": str(route.score) if route.score else None,
        "solverStatus": solver_status.name if solver_status else None,
    }


@app.delete("/route-plans/{problem_id}")
async def stop_solving(problem_id: str) -> VehicleRoutePlanModel:
    """Terminate solving for a given job ID. Returns the best solution so far."""
    solver_manager.terminate_early(problem_id)
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")
    route.solver_status = solver_manager.get_solver_status(problem_id)
    return plan_to_model(route)


@app.post("/route-plans/recommendation")
async def recommend_assignment(request: RecommendationRequest) -> List[RecommendedAssignmentResponse]:
    """
    Request recommendations for assigning a visit to vehicles.

    Returns a list of recommended assignments sorted by score impact.
    """
    domain_plan = model_to_plan(request.solution)

    # Find the visit by ID
    visit = None
    for v in domain_plan.visits:
        if v.id == request.visit_id:
            visit = v
            break

    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit {request.visit_id} not found")

    # Get recommendations using solution_manager
    try:
        recommendations = solution_manager.recommend_assignment(
            domain_plan,
            visit,
            lambda v: VehicleRecommendation(vehicle_id=v.vehicle.id, index=v.vehicle.visits.index(v))
        )

        # Convert to response format (limit to top 5)
        result = []
        for rec in recommendations[:5]:
            result.append(RecommendedAssignmentResponse(
                proposition=rec.proposition,
                score_diff=str(rec.score_diff) if hasattr(rec, 'score_diff') else "0hard/0soft"
            ))
        return result
    except Exception:
        # If recommend_assignment is not available, return empty list
        return []


@app.post("/route-plans/recommendation/apply")
async def apply_recommendation(request: ApplyRecommendationRequest) -> VehicleRoutePlanModel:
    """
    Apply a recommendation to assign a visit to a vehicle at a specific index.

    Returns the updated solution.
    """
    domain_plan = model_to_plan(request.solution)

    # Find the vehicle by ID
    vehicle = None
    for v in domain_plan.vehicles:
        if v.id == request.vehicle_id:
            vehicle = v
            break

    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle {request.vehicle_id} not found")

    # Find the visit by ID
    visit = None
    for v in domain_plan.visits:
        if v.id == request.visit_id:
            visit = v
            break

    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit {request.visit_id} not found")

    # Insert visit at the specified index
    vehicle.visits.insert(request.index, visit)

    # Update the solution to recalculate shadow variables
    solution_manager.update(domain_plan)

    return plan_to_model(domain_plan)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
