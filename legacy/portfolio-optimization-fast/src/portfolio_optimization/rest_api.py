"""
REST API for Portfolio Optimization

This module provides HTTP endpoints for the portfolio optimization quickstart:

Endpoints:
- GET  /demo-data           - List available demo datasets
- GET  /demo-data/{id}      - Load a specific demo dataset
- POST /portfolios          - Submit a portfolio for optimization
- GET  /portfolios/{id}     - Get current solution for a job
- GET  /portfolios/{id}/status - Get solving status
- DELETE /portfolios/{id}   - Stop solving
- PUT  /portfolios/analyze  - Analyze a submitted portfolio's score

The API follows the same patterns as other SolverForge quickstarts.
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from dataclasses import replace
from typing import Any

from solverforge_legacy.solver import SolverManager, SolverFactory

from .domain import PortfolioOptimizationPlan, PortfolioOptimizationPlanModel
from .converters import plan_to_model, model_to_plan
from .demo_data import DemoData, generate_demo_data
from .solver import solver_manager, solution_manager, create_solver_config
from .score_analysis import ConstraintAnalysisDTO, MatchAnalysisDTO


app = FastAPI(
    title="Portfolio Optimization Quickstart",
    description="SolverForge quickstart for stock portfolio optimization",
    docs_url='/q/swagger-ui'
)

# In-memory storage for submitted portfolios and their solver managers
data_sets: dict[str, PortfolioOptimizationPlan] = {}
solver_managers: dict[str, SolverManager] = {}


@app.get("/demo-data")
async def demo_data_list() -> list[DemoData]:
    """List available demo datasets."""
    return [e for e in DemoData]


@app.get("/demo-data/{dataset_id}", response_model_exclude_none=True)
async def get_demo_data(dataset_id: str) -> PortfolioOptimizationPlanModel:
    """Load a specific demo dataset."""
    demo_data = getattr(DemoData, dataset_id)
    domain_plan = generate_demo_data(demo_data)
    return plan_to_model(domain_plan)


@app.get("/portfolios/{problem_id}", response_model_exclude_none=True)
async def get_portfolio(problem_id: str) -> PortfolioOptimizationPlanModel:
    """Get current solution for a portfolio optimization job."""
    plan = data_sets[problem_id]
    # Use per-job solver manager if available, otherwise use default
    manager = solver_managers.get(problem_id, solver_manager)
    updated_plan = replace(plan, solver_status=manager.get_solver_status(problem_id))
    return plan_to_model(updated_plan)


def update_portfolio(problem_id: str, plan: PortfolioOptimizationPlan) -> None:
    """Callback to update the stored solution as solver improves it."""
    global data_sets
    data_sets[problem_id] = plan


@app.post("/portfolios")
async def solve_portfolio(plan_model: PortfolioOptimizationPlanModel) -> str:
    """
    Submit a portfolio for optimization.

    Returns a job ID that can be used to retrieve the solution.
    Supports custom solver configuration via solverConfig field.
    """
    job_id = str(uuid4())
    plan = model_to_plan(plan_model)
    data_sets[job_id] = plan

    # Get termination time from config or use default
    termination_seconds = 30
    if plan_model.solver_config and plan_model.solver_config.termination_seconds:
        termination_seconds = plan_model.solver_config.termination_seconds

    # Create solver with dynamic config
    config = create_solver_config(termination_seconds)
    manager: SolverManager = SolverManager.create(SolverFactory.create(config))
    solver_managers[job_id] = manager

    manager.solve_and_listen(
        job_id,
        plan,
        lambda solution: update_portfolio(job_id, solution)
    )
    return job_id


@app.get("/portfolios")
async def list_portfolios() -> list[str]:
    """List all job IDs of submitted portfolios."""
    return list(data_sets.keys())


@app.get("/portfolios/{problem_id}/status")
async def get_status(problem_id: str) -> dict[str, Any]:
    """Get the portfolio status and score for a given job ID."""
    if problem_id not in data_sets:
        raise ValueError(f"No portfolio found with ID {problem_id}")

    plan = data_sets[problem_id]
    # Use per-job solver manager if available, otherwise use default
    manager = solver_managers.get(problem_id, solver_manager)
    solver_status = manager.get_solver_status(problem_id)

    # Calculate additional metrics
    selected_count = plan.get_selected_count()
    expected_return = plan.get_expected_return() if selected_count > 0 else 0

    return {
        "score": {
            "hardScore": plan.score.hard_score if plan.score else 0,
            "softScore": plan.score.soft_score if plan.score else 0,
        },
        "solverStatus": solver_status.name,
        "selectedCount": selected_count,
        "expectedReturn": expected_return,
        "sectorWeights": plan.get_sector_weights() if selected_count > 0 else {},
    }


@app.delete("/portfolios/{problem_id}")
async def stop_solving(problem_id: str) -> PortfolioOptimizationPlanModel:
    """Terminate solving for a given job ID."""
    if problem_id not in data_sets:
        raise ValueError(f"No portfolio found with ID {problem_id}")

    # Use per-job solver manager if available, otherwise use default
    manager = solver_managers.get(problem_id, solver_manager)
    try:
        manager.terminate_early(problem_id)
    except Exception as e:
        print(f"Warning: terminate_early failed for {problem_id}: {e}")

    return await get_portfolio(problem_id)


@app.put("/portfolios/analyze")
async def analyze_portfolio(request: Request) -> dict[str, Any]:
    """Submit a portfolio to analyze its score in detail."""
    json_data = await request.json()

    # Parse the incoming JSON using Pydantic models
    plan_model = PortfolioOptimizationPlanModel.model_validate(json_data)

    # Convert to domain model for analysis
    domain_plan = model_to_plan(plan_model)

    analysis = solution_manager.analyze(domain_plan)

    # Convert to DTOs for proper serialization
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


# Mount static files for the web UI
app.mount("/", StaticFiles(directory="static", html=True), name="static")
