from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from uuid import uuid4
from typing import Dict, List
from dataclasses import dataclass, asdict
import asyncio
import json

from pydantic import BaseModel, Field as PydanticField
from random import Random

from .domain import OrderPickingSolution, OrderPickingSolutionModel
from .converters import solution_to_model, model_to_solution
from .demo_data import (
    generate_demo_data, build_products, build_trolleys, build_orders,
    build_trolley_steps, validate_bucket_capacity, START_LOCATION, BUCKET_CAPACITY
)
from .solver import solver_manager, solution_manager
from .warehouse import calculate_distance_to_travel


app = FastAPI(docs_url='/q/swagger-ui')

data_sets: Dict[str, OrderPickingSolution] = {}
# Track solution versions for SSE change detection
solution_versions: Dict[str, int] = {}


@dataclass
class MatchAnalysisDTO:
    name: str
    score: str
    justification: str


@dataclass
class ConstraintAnalysisDTO:
    name: str
    weight: str
    score: str
    matches: List[MatchAnalysisDTO]


class TrolleyDistanceResponse(BaseModel):
    distance_to_travel_by_trolley: Dict[str, int] = PydanticField(
        ...,
        serialization_alias="distanceToTravelByTrolley"
    )

    model_config = {"populate_by_name": True}


class DemoConfigModel(BaseModel):
    """Configuration for generating custom demo data."""
    orders_count: int = PydanticField(default=8, ge=3, le=20, alias="ordersCount")
    trolleys_count: int = PydanticField(default=5, ge=2, le=10, alias="trolleysCount")
    bucket_count: int = PydanticField(default=4, ge=2, le=8, alias="bucketCount")

    model_config = {"populate_by_name": True}


@app.get("/demo-data")
async def get_demo_data_list() -> List[str]:
    """Get available demo data sets."""
    return ["DEFAULT"]


@app.get("/demo-data/{demo_name}", response_model=OrderPickingSolutionModel)
async def get_demo_data_by_name(demo_name: str) -> OrderPickingSolutionModel:
    """Get a specific demo data set."""
    if demo_name != "DEFAULT":
        raise HTTPException(status_code=404, detail=f"Demo data '{demo_name}' not found")
    domain_solution = generate_demo_data()
    return solution_to_model(domain_solution)


@app.post("/demo-data/generate", response_model=OrderPickingSolutionModel)
async def generate_custom_demo(config: DemoConfigModel) -> OrderPickingSolutionModel:
    """Generate demo data with custom configuration."""
    random = Random(37)  # Fixed seed for reproducibility

    validate_bucket_capacity(BUCKET_CAPACITY)

    products = build_products(random)
    trolleys = build_trolleys(
        config.trolleys_count,
        config.bucket_count,
        BUCKET_CAPACITY,
        START_LOCATION
    )
    orders = build_orders(config.orders_count, products, random)
    trolley_steps = build_trolley_steps(orders)

    domain_solution = OrderPickingSolution(
        trolleys=trolleys,
        trolley_steps=trolley_steps
    )
    return solution_to_model(domain_solution)


def on_best_solution(job_id: str, solution: OrderPickingSolution):
    """Callback when solver finds a new best solution."""
    data_sets[job_id] = solution
    # Increment version to trigger SSE updates
    solution_versions[job_id] = solution_versions.get(job_id, 0) + 1


@app.post("/schedules")
async def solve(solution_model: OrderPickingSolutionModel) -> str:
    """Submit a problem to solve."""
    job_id = str(uuid4())
    domain_solution = model_to_solution(solution_model)
    data_sets[job_id] = domain_solution
    solution_versions[job_id] = 0
    solver_manager.solve_and_listen(
        job_id,
        domain_solution,
        lambda solution: on_best_solution(job_id, solution)
    )
    return job_id


@app.get("/schedules/{problem_id}", response_model=OrderPickingSolutionModel)
async def get_solution(problem_id: str) -> OrderPickingSolutionModel:
    """Get the current solution for a given job ID."""
    solution = data_sets.get(problem_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    solution.solver_status = solver_manager.get_solver_status(problem_id)
    return solution_to_model(solution)


@app.get("/schedules/{problem_id}/status")
async def get_status(problem_id: str) -> dict:
    """Get the solution status and score for a given job ID."""
    solution = data_sets.get(problem_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    solver_status = solver_manager.get_solver_status(problem_id)
    return {
        "score": {
            "hardScore": solution.score.hard_score if solution.score else 0,
            "softScore": solution.score.soft_score if solution.score else 0,
        },
        "solverStatus": solver_status.name if solver_status else None,
    }


async def solution_event_generator(problem_id: str):
    """Generate SSE events when solution changes."""
    last_version = -1
    last_send_time = 0
    update_count = 0

    while True:
        solution = data_sets.get(problem_id)
        if not solution:
            yield f"event: error\ndata: Solution not found\n\n"
            break

        current_version = solution_versions.get(problem_id, 0)
        solver_status = solver_manager.get_solver_status(problem_id)
        now = asyncio.get_event_loop().time()

        # Send update if:
        # 1. Version changed (new best solution found)
        # 2. First message (version -1)
        # 3. Every 500ms as a keepalive with current state
        should_send = (
            current_version != last_version or
            (now - last_send_time) > 0.5
        )

        if should_send:
            last_version = current_version
            last_send_time = now
            update_count += 1

            # Build compact update payload
            distances = {}
            for trolley in solution.trolleys:
                distances[trolley.id] = calculate_distance_to_travel(trolley)

            model = solution_to_model(solution)
            model.solver_status = solver_status.name if solver_status else "NOT_SOLVING"

            event_data = {
                "version": current_version,
                "updateCount": update_count,
                "solution": model.model_dump(by_alias=True),
                "distances": distances,
            }

            yield f"event: update\ndata: {json.dumps(event_data)}\n\n"

        # Check if solving is done
        if solver_status is None or solver_status.name == "NOT_SOLVING":
            yield f"event: done\ndata: Solving complete\n\n"
            break

        # Poll every 100ms for changes
        await asyncio.sleep(0.1)


@app.get("/schedules/{problem_id}/stream")
async def stream_solution(problem_id: str):
    """Stream solution updates via Server-Sent Events."""
    if problem_id not in data_sets:
        raise HTTPException(status_code=404, detail="Solution not found")

    return StreamingResponse(
        solution_event_generator(problem_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/schedules/{problem_id}/distances")
async def get_distances(problem_id: str) -> TrolleyDistanceResponse:
    """Get the total distance to travel for each trolley."""
    solution = data_sets.get(problem_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    distances = {}
    for trolley in solution.trolleys:
        distances[trolley.id] = calculate_distance_to_travel(trolley)

    return TrolleyDistanceResponse(distance_to_travel_by_trolley=distances)


@app.delete("/schedules/{problem_id}")
async def stop_solving(problem_id: str) -> OrderPickingSolutionModel:
    """Terminate solving for a given job ID. Returns the best solution so far."""
    solver_manager.terminate_early(problem_id)
    solution = data_sets.get(problem_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    solution.solver_status = solver_manager.get_solver_status(problem_id)
    return solution_to_model(solution)


@app.put("/schedules/analyze")
async def analyze_solution(solution_model: OrderPickingSolutionModel) -> dict:
    """Analyze a solution and return constraint breakdowns."""
    domain_solution = model_to_solution(solution_model)
    analysis = solution_manager.analyze(domain_solution)
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


@app.get("/schedules")
async def list_solutions() -> List[str]:
    """List the job IDs of all submitted solutions."""
    return list(data_sets.keys())


app.mount("/", StaticFiles(directory="static", html=True), name="static")
