"""
Portfolio Optimization Domain Model

This module defines the core domain entities for stock portfolio optimization:
- StockSelection: A stock that can be selected for the portfolio (planning entity)
- PortfolioOptimizationPlan: The complete portfolio optimization problem (planning solution)

The model uses a Boolean selection approach:
- Each stock has a `selected` field (True/False)
- Selected stocks get equal weight (100% / number_selected)
- This simplifies the optimization while still demonstrating constraint solving
"""
from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.domain import (
    planning_entity,
    planning_solution,
    PlanningId,
    PlanningVariable,
    PlanningEntityCollectionProperty,
    ProblemFactCollectionProperty,
    ProblemFactProperty,
    ValueRangeProvider,
    PlanningScore,
)
from solverforge_legacy.solver.score import HardSoftScore
from typing import Annotated, List, Optional
from dataclasses import dataclass, field
from .json_serialization import JsonDomainBase
from pydantic import Field


@dataclass
class SelectionValue:
    """
    Represents a possible selection state for a stock.

    We use this wrapper class instead of raw bool because SolverForge
    needs a reference type for the value range provider.
    """
    value: bool

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, SelectionValue):
            return self.value == other.value
        return False


# Pre-created selection values for the value range
SELECTED = SelectionValue(True)
NOT_SELECTED = SelectionValue(False)


@dataclass
class PortfolioConfig:
    """
    Configuration parameters for portfolio constraints.

    This is a problem fact that constraints can join against to access
    configurable threshold values.

    Attributes:
        target_count: Number of stocks to select (default 20)
        max_per_sector: Maximum stocks per sector (default 5, which is 25% of 20)
        unselected_penalty: Soft penalty per unselected stock (default 10000)
    """
    target_count: int = 20
    max_per_sector: int = 5
    unselected_penalty: int = 10000

    def __hash__(self) -> int:
        return hash((self.target_count, self.max_per_sector, self.unselected_penalty))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PortfolioConfig):
            return (
                self.target_count == other.target_count
                and self.max_per_sector == other.max_per_sector
                and self.unselected_penalty == other.unselected_penalty
            )
        return False


@planning_entity
@dataclass
class StockSelection:
    """
    Represents a stock that can be included in the portfolio.

    This is a planning entity - SolverForge decides whether to include
    each stock by setting the `selection` field.

    Attributes:
        stock_id: Unique identifier (ticker symbol, e.g., "AAPL")
        stock_name: Human-readable name (e.g., "Apple Inc.")
        sector: Industry sector (e.g., "Technology", "Healthcare")
        predicted_return: ML-predicted return as decimal (0.12 = 12%)
        selection: Planning variable - SELECTED or NOT_SELECTED
    """
    stock_id: Annotated[str, PlanningId]
    stock_name: str
    sector: str
    predicted_return: float  # e.g., 0.12 means 12% expected return

    # THE DECISION: Should we include this stock in the portfolio?
    # SolverForge will set this to SELECTED or NOT_SELECTED
    # Note: value_range_provider_refs links to the 'selection_range' field
    selection: Annotated[
        SelectionValue | None,
        PlanningVariable(value_range_provider_refs=["selection_range"])
    ] = None

    @property
    def selected(self) -> bool | None:
        """Convenience property to check if stock is selected."""
        if self.selection is None:
            return None
        return self.selection.value


@planning_solution
@dataclass
class PortfolioOptimizationPlan:
    """
    The complete portfolio optimization problem.

    This is the planning solution that contains:
    - All candidate stocks (planning entities)
    - Configuration parameters
    - The optimization score

    The solver will decide which stocks to select (set selected=True)
    while respecting constraints and maximizing expected return.
    """
    # All stocks we're choosing from (planning entities)
    stocks: Annotated[
        list[StockSelection],
        PlanningEntityCollectionProperty,
        ValueRangeProvider
    ]

    # Configuration
    target_position_count: int = 20  # How many stocks to select
    max_sector_percentage: float = 0.25  # Max 25% in any sector

    # Constraint configuration (problem fact for constraints to access)
    # This derives from target_position_count and max_sector_percentage
    portfolio_config: Annotated[
        PortfolioConfig,
        ProblemFactProperty
    ] = field(default_factory=PortfolioConfig)

    # Value range for the selection
    # The solver can set `selection` to SELECTED or NOT_SELECTED
    # Note: id="selection_range" must match the value_range_provider_refs in StockSelection
    selection_range: Annotated[
        list[SelectionValue],
        ValueRangeProvider(id="selection_range"),
        ProblemFactCollectionProperty
    ] = field(default_factory=lambda: [SELECTED, NOT_SELECTED])

    # Solution quality score (set by solver)
    score: Annotated[HardSoftScore | None, PlanningScore] = None

    # Current solver status
    solver_status: SolverStatus = SolverStatus.NOT_SOLVING

    def get_selected_stocks(self) -> list[StockSelection]:
        """Return only stocks that are selected for the portfolio."""
        return [s for s in self.stocks if s.selected is True]

    def get_selected_count(self) -> int:
        """Return count of selected stocks."""
        return len(self.get_selected_stocks())

    def get_weight_per_stock(self) -> float:
        """Calculate equal weight per selected stock (e.g., 20 stocks = 5% each)."""
        count = self.get_selected_count()
        return 1.0 / count if count > 0 else 0.0

    def get_sector_weights(self) -> dict[str, float]:
        """Calculate total weight per sector."""
        weight = self.get_weight_per_stock()
        sector_weights: dict[str, float] = {}
        for stock in self.get_selected_stocks():
            sector_weights[stock.sector] = sector_weights.get(stock.sector, 0.0) + weight
        return sector_weights

    def get_expected_return(self) -> float:
        """Calculate total expected portfolio return."""
        weight = self.get_weight_per_stock()
        return sum(s.predicted_return * weight for s in self.get_selected_stocks())

    def get_herfindahl_index(self) -> float:
        """
        Calculate the Herfindahl-Hirschman Index (HHI) for sector concentration.

        HHI = sum of (sector_weight)^2
        - Range: 1/n (perfectly diversified) to 1.0 (all in one sector)
        - Lower HHI = more diversified
        - Common thresholds: <0.15 (diversified), 0.15-0.25 (moderate), >0.25 (concentrated)
        """
        sector_weights = self.get_sector_weights()
        if not sector_weights:
            return 0.0
        return sum(w * w for w in sector_weights.values())

    def get_diversification_score(self) -> float:
        """
        Calculate diversification score as 1 - HHI.

        Range: 0.0 (all in one sector) to 1-1/n (perfectly diversified)
        Higher = more diversified
        """
        return 1.0 - self.get_herfindahl_index()

    def get_max_sector_exposure(self) -> float:
        """
        Get the highest single sector weight.

        Returns the weight of the most concentrated sector.
        Lower is better for diversification.
        """
        sector_weights = self.get_sector_weights()
        if not sector_weights:
            return 0.0
        return max(sector_weights.values())

    def get_sector_count(self) -> int:
        """Return count of unique sectors in selected stocks."""
        selected = self.get_selected_stocks()
        return len(set(s.sector for s in selected))

    def get_return_volatility(self) -> float:
        """
        Calculate standard deviation of predicted returns (proxy for risk).

        Higher volatility = higher risk portfolio.
        """
        selected = self.get_selected_stocks()
        if len(selected) < 2:
            return 0.0

        returns = [s.predicted_return for s in selected]
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    def get_sharpe_proxy(self) -> float:
        """
        Calculate a proxy for Sharpe ratio: return / volatility.

        Higher = better risk-adjusted return.
        Note: This is a simplified proxy, not true Sharpe (no risk-free rate).
        """
        volatility = self.get_return_volatility()
        if volatility == 0:
            return 0.0
        return self.get_expected_return() / volatility


# ============================================================
# Pydantic REST Models (for API serialization)
# ============================================================

class StockSelectionModel(JsonDomainBase):
    """REST API model for StockSelection."""
    stock_id: str = Field(..., alias="stockId")
    stock_name: str = Field(..., alias="stockName")
    sector: str
    predicted_return: float = Field(..., alias="predictedReturn")
    selected: Optional[bool] = None


class SolverConfigModel(JsonDomainBase):
    """REST API model for solver configuration options."""
    termination_seconds: int = Field(default=30, alias="terminationSeconds", ge=10, le=300)


class PortfolioMetricsModel(JsonDomainBase):
    """
    REST API model for portfolio business metrics (KPIs).

    These metrics provide business insight beyond the solver score:
    - Diversification measures (HHI, max sector exposure)
    - Risk/return measures (expected return, volatility, Sharpe proxy)
    """
    expected_return: float = Field(..., alias="expectedReturn")
    sector_count: int = Field(..., alias="sectorCount")
    max_sector_exposure: float = Field(..., alias="maxSectorExposure")
    herfindahl_index: float = Field(..., alias="herfindahlIndex")
    diversification_score: float = Field(..., alias="diversificationScore")
    return_volatility: float = Field(..., alias="returnVolatility")
    sharpe_proxy: float = Field(..., alias="sharpeProxy")


class PortfolioOptimizationPlanModel(JsonDomainBase):
    """REST API model for PortfolioOptimizationPlan."""
    stocks: List[StockSelectionModel]
    target_position_count: int = Field(default=20, alias="targetPositionCount")
    max_sector_percentage: float = Field(default=0.25, alias="maxSectorPercentage")
    score: Optional[str] = None
    solver_status: Optional[str] = Field(None, alias="solverStatus")
    solver_config: Optional[SolverConfigModel] = Field(None, alias="solverConfig")
    metrics: Optional[PortfolioMetricsModel] = None
