from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from threading import Lock, Event
import re
import copy

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

# =============================================================================
# Thread-safe solution caching
# =============================================================================
# The solver runs in a Java thread (via JPype) and calls Python callbacks.
# We snapshot solution data IMMEDIATELY in the callback (while solver paused)
# and store the immutable snapshot. API handlers read from this cache.

# Thread-safe cache: stores SNAPSHOTS as dicts (immutable after creation)
cached_solutions: Dict[str, Dict[str, Any]] = {}
cached_distances: Dict[str, Dict[str, int]] = {}
cache_lock = Lock()

# Events to signal when first solution is ready
first_solution_events: Dict[str, Event] = {}

# Domain objects for score analysis
data_sets: Dict[str, OrderPickingSolution] = {}


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


class DemoConfigModel(BaseModel):
    """Configuration for generating custom demo data."""
    orders_count: int = PydanticField(default=40, ge=5, le=100, alias="ordersCount")
    trolleys_count: int = PydanticField(default=8, ge=2, le=15, alias="trolleysCount")
    bucket_count: int = PydanticField(default=6, ge=2, le=10, alias="bucketCount")

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

    # Pre-assign steps evenly across trolleys so we have paths to visualize immediately
    if trolleys:
        for i, step in enumerate(trolley_steps):
            trolley = trolleys[i % len(trolleys)]
            trolley.steps.append(step)
            step.trolley = trolley

    domain_solution = OrderPickingSolution(
        trolleys=trolleys,
        trolley_steps=trolley_steps
    )
    return solution_to_model(domain_solution)


def update_solution(job_id: str, solution: OrderPickingSolution):
    """
    Update solution cache. Called by solver callback from Java thread.

    CRITICAL: We snapshot ALL data IMMEDIATELY in the callback while the solver
    is paused. This prevents race conditions where the Java solver modifies
    domain objects while we're reading them.
    """
    # Snapshot step assignments for each trolley FIRST (before any iteration)
    trolley_snapshots = []
    for t in solution.trolleys:
        # Copy the steps list immediately - this is the critical snapshot
        step_ids = [s.id for s in t.steps]
        trolley_snapshots.append((t.id, len(step_ids), step_ids))

    # Log for debugging
    step_counts = [f"T{tid}:{count}" for tid, count, _ in trolley_snapshots]
    print(f"[CALLBACK] job={job_id} score={solution.score} steps=[{' '.join(step_counts)}]")

    # Now convert to API model (uses the same solution state we just logged)
    api_model = solution_to_model(solution)
    solution_dict = api_model.model_dump(by_alias=True)

    # Calculate distances
    distances = {}
    for trolley in solution.trolleys:
        distances[trolley.id] = calculate_distance_to_travel(trolley)

    # Update cache atomically
    with cache_lock:
        cached_solutions[job_id] = solution_dict
        cached_distances[job_id] = distances

    # Signal that first solution is ready
    if job_id in first_solution_events:
        first_solution_events[job_id].set()

    # Keep domain object reference for score analysis
    data_sets[job_id] = solution


@app.post("/schedules")
async def solve(solution_model: OrderPickingSolutionModel) -> str:
    """Submit a problem to solve. Returns job ID."""
    job_id = str(uuid4())
    domain_solution = model_to_solution(solution_model)

    data_sets[job_id] = domain_solution

    # Initialize cache with empty state - will be updated by callbacks
    with cache_lock:
        cached_solutions[job_id] = solution_to_model(domain_solution).model_dump(by_alias=True)
        cached_distances[job_id] = {}

    # Start solver - callbacks update cache when construction completes and on improvements
    (solver_manager.solve_builder()
        .with_problem_id(job_id)
        .with_problem(domain_solution)
        .with_first_initialized_solution_consumer(lambda solution: update_solution(job_id, solution))
        .with_best_solution_consumer(lambda solution: update_solution(job_id, solution))
        .run())

    return job_id


@app.get("/schedules/{problem_id}")
async def get_solution(problem_id: str) -> Dict[str, Any]:
    """Get the current solution for a given job ID."""
    solver_status = solver_manager.get_solver_status(problem_id)

    # Read from thread-safe cache (populated by solver callbacks)
    with cache_lock:
        cached = cached_solutions.get(problem_id)

    if not cached:
        raise HTTPException(status_code=404, detail="Solution not found")

    # Return cached solution with current status
    result = dict(cached)
    result["solverStatus"] = solver_status.name if solver_status else None

    return result


@app.get("/schedules/{problem_id}/status")
async def get_status(problem_id: str) -> dict:
    """Get the solution status, score, and distances for a given job ID."""
    # Read from thread-safe cache
    with cache_lock:
        cached = cached_solutions.get(problem_id)
        distances = cached_distances.get(problem_id, {})

    if not cached:
        raise HTTPException(status_code=404, detail="Solution not found")

    solver_status = solver_manager.get_solver_status(problem_id)

    # Parse score from cached solution
    score_str = cached.get("score", "")
    hard_score = 0
    soft_score = 0
    if score_str:
        # Parse score like "0hard/-12345soft"
        match = re.match(r"(-?\d+)hard/(-?\d+)soft", str(score_str))
        if match:
            hard_score = int(match.group(1))
            soft_score = int(match.group(2))

    return {
        "score": {
            "hardScore": hard_score,
            "softScore": soft_score,
        },
        "solverStatus": solver_status.name if solver_status else None,
        "distances": distances,
    }


@app.delete("/schedules/{problem_id}")
async def stop_solving(problem_id: str) -> Dict[str, Any]:
    """Terminate solving for a given job ID. Returns the best solution so far."""
    solver_manager.terminate_early(problem_id)

    # Read from thread-safe cache
    with cache_lock:
        cached = cached_solutions.get(problem_id)
        if not cached:
            raise HTTPException(status_code=404, detail="Solution not found")
        result = dict(cached)

    solver_status = solver_manager.get_solver_status(problem_id)
    result["solverStatus"] = solver_status.name if solver_status else None

    return result


@app.get("/schedules/{problem_id}/score-analysis")
async def analyze_score(problem_id: str) -> dict:
    """Get score analysis for current solution."""
    solution = data_sets.get(problem_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    analysis = solution_manager.analyze(solution)
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
