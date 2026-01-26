"""
Converters between domain objects and REST API models.

These functions handle the transformation between:
- Domain objects (dataclasses used by the solver)
- REST models (Pydantic models used by the API)
"""
from . import domain
from .domain import SELECTED, NOT_SELECTED, PortfolioConfig


def stock_to_model(stock: domain.StockSelection) -> domain.StockSelectionModel:
    """Convert a StockSelection domain object to REST model."""
    # Note: Pydantic model has populate_by_name=True, allowing snake_case field names
    return domain.StockSelectionModel(  # type: ignore[call-arg]
        stock_id=stock.stock_id,
        stock_name=stock.stock_name,
        sector=stock.sector,
        predicted_return=stock.predicted_return,
        selected=stock.selected,  # Uses the @property that returns bool
    )


def plan_to_metrics(plan: domain.PortfolioOptimizationPlan) -> domain.PortfolioMetricsModel | None:
    """Calculate business metrics from a plan."""
    if plan.get_selected_count() == 0:
        return None

    return domain.PortfolioMetricsModel(  # type: ignore[call-arg]
        expected_return=plan.get_expected_return(),
        sector_count=plan.get_sector_count(),
        max_sector_exposure=plan.get_max_sector_exposure(),
        herfindahl_index=plan.get_herfindahl_index(),
        diversification_score=plan.get_diversification_score(),
        return_volatility=plan.get_return_volatility(),
        sharpe_proxy=plan.get_sharpe_proxy(),
    )


def plan_to_model(plan: domain.PortfolioOptimizationPlan) -> domain.PortfolioOptimizationPlanModel:
    """Convert a PortfolioOptimizationPlan domain object to REST model."""
    # Note: Pydantic model has populate_by_name=True, allowing snake_case field names
    return domain.PortfolioOptimizationPlanModel(  # type: ignore[call-arg]
        stocks=[stock_to_model(s) for s in plan.stocks],
        target_position_count=plan.target_position_count,
        max_sector_percentage=plan.max_sector_percentage,
        score=str(plan.score) if plan.score else None,
        solver_status=plan.solver_status.name if plan.solver_status else None,
        metrics=plan_to_metrics(plan),
    )


def model_to_stock(model: domain.StockSelectionModel) -> domain.StockSelection:
    """Convert a StockSelectionModel REST model to domain object.

    Note: The REST model uses `selected: bool` but the domain uses
    `selection: SelectionValue`. We convert here.
    """
    # Convert bool to SelectionValue (or None if not set)
    selection = None
    if model.selected is True:
        selection = SELECTED
    elif model.selected is False:
        selection = NOT_SELECTED
    # If model.selected is None, leave selection as None

    return domain.StockSelection(
        stock_id=model.stock_id,
        stock_name=model.stock_name,
        sector=model.sector,
        predicted_return=model.predicted_return,
        selection=selection,
    )


def model_to_plan(model: domain.PortfolioOptimizationPlanModel) -> domain.PortfolioOptimizationPlan:
    """Convert a PortfolioOptimizationPlanModel REST model to domain object.

    Creates a PortfolioConfig from the model's target_position_count and
    max_sector_percentage so that constraints can access these values.
    """
    stocks = [model_to_stock(s) for s in model.stocks]

    # Parse score if provided
    score = None
    if model.score:
        from solverforge_legacy.solver.score import HardSoftScore
        score = HardSoftScore.parse(model.score)

    # Parse solver status if provided
    solver_status = domain.SolverStatus.NOT_SOLVING
    if model.solver_status:
        solver_status = domain.SolverStatus[model.solver_status]

    # Calculate max_per_sector from max_sector_percentage and target_position_count
    # Example: 25% of 20 stocks = 5 stocks max per sector
    target_count = model.target_position_count
    max_per_sector = max(1, int(model.max_sector_percentage * target_count))

    # Create PortfolioConfig for constraints to access
    portfolio_config = PortfolioConfig(
        target_count=target_count,
        max_per_sector=max_per_sector,
        unselected_penalty=10000,  # Default penalty
    )

    return domain.PortfolioOptimizationPlan(
        stocks=stocks,
        target_position_count=model.target_position_count,
        max_sector_percentage=model.max_sector_percentage,
        portfolio_config=portfolio_config,
        score=score,
        solver_status=solver_status,
    )
