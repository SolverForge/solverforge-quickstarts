"""
Tests for business metrics in the Portfolio Optimization quickstart.

These tests verify the financial KPIs calculated by the domain model:
- Herfindahl-Hirschman Index (HHI) for concentration
- Diversification score (1 - HHI)
- Max sector exposure
- Expected return
- Return volatility
- Sharpe proxy (return / volatility)

These metrics provide business insight beyond the solver score.
"""
import pytest
import math

from portfolio_optimization.domain import (
    StockSelection,
    PortfolioOptimizationPlan,
    PortfolioConfig,
    PortfolioMetricsModel,
    SELECTED,
    NOT_SELECTED,
)
from portfolio_optimization.converters import plan_to_metrics


def create_stock(
    stock_id: str,
    sector: str = "Technology",
    predicted_return: float = 0.10,
    selected: bool = True
) -> StockSelection:
    """Create a test stock with sensible defaults."""
    return StockSelection(
        stock_id=stock_id,
        stock_name=f"{stock_id} Corp",
        sector=sector,
        predicted_return=predicted_return,
        selection=SELECTED if selected else NOT_SELECTED,
    )


def create_plan(stocks: list[StockSelection]) -> PortfolioOptimizationPlan:
    """Create a test plan with given stocks."""
    return PortfolioOptimizationPlan(
        stocks=stocks,
        target_position_count=20,
        max_sector_percentage=0.25,
        portfolio_config=PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=10000),
    )


class TestHerfindahlIndex:
    """Tests for the Herfindahl-Hirschman Index (HHI) calculation."""

    def test_single_sector_hhi_is_one(self) -> None:
        """All stocks in one sector should have HHI = 1.0 (max concentration)."""
        stocks = [create_stock(f"STK{i}", sector="Technology") for i in range(5)]
        plan = create_plan(stocks)

        # All in one sector: HHI = 1.0^2 = 1.0
        assert plan.get_herfindahl_index() == 1.0

    def test_two_equal_sectors_hhi(self) -> None:
        """Two sectors with equal stocks should have HHI = 0.5."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(5)],
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(5)],
        ]
        plan = create_plan(stocks)

        # 50% in each sector: HHI = 0.5^2 + 0.5^2 = 0.5
        assert abs(plan.get_herfindahl_index() - 0.5) < 0.001

    def test_four_equal_sectors_hhi(self) -> None:
        """Four sectors with equal stocks should have HHI = 0.25."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(5)],
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(5)],
            *[create_stock(f"FIN{i}", sector="Finance") for i in range(5)],
            *[create_stock(f"NRG{i}", sector="Energy") for i in range(5)],
        ]
        plan = create_plan(stocks)

        # 25% in each sector: HHI = 4 * 0.25^2 = 0.25
        assert abs(plan.get_herfindahl_index() - 0.25) < 0.001

    def test_empty_portfolio_hhi_is_zero(self) -> None:
        """Empty portfolio should have HHI = 0."""
        stocks = [create_stock(f"STK{i}", selected=False) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_herfindahl_index() == 0.0

    def test_unequal_sectors_hhi(self) -> None:
        """Unequal sector distribution should give correct HHI."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(6)],  # 60%
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(4)],  # 40%
        ]
        plan = create_plan(stocks)

        # HHI = 0.6^2 + 0.4^2 = 0.36 + 0.16 = 0.52
        assert abs(plan.get_herfindahl_index() - 0.52) < 0.001


class TestDiversificationScore:
    """Tests for the diversification score (1 - HHI)."""

    def test_single_sector_diversification_is_zero(self) -> None:
        """All stocks in one sector should have diversification = 0."""
        stocks = [create_stock(f"STK{i}", sector="Technology") for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_diversification_score() == 0.0

    def test_two_equal_sectors_diversification(self) -> None:
        """Two equal sectors should have diversification = 0.5."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(5)],
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(5)],
        ]
        plan = create_plan(stocks)

        assert abs(plan.get_diversification_score() - 0.5) < 0.001

    def test_four_equal_sectors_diversification(self) -> None:
        """Four equal sectors should have diversification = 0.75."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(5)],
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(5)],
            *[create_stock(f"FIN{i}", sector="Finance") for i in range(5)],
            *[create_stock(f"NRG{i}", sector="Energy") for i in range(5)],
        ]
        plan = create_plan(stocks)

        # 1 - HHI = 1 - 0.25 = 0.75
        assert abs(plan.get_diversification_score() - 0.75) < 0.001


class TestMaxSectorExposure:
    """Tests for max sector exposure calculation."""

    def test_single_sector_max_exposure_is_one(self) -> None:
        """All stocks in one sector should have max exposure = 1.0."""
        stocks = [create_stock(f"STK{i}", sector="Technology") for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_max_sector_exposure() == 1.0

    def test_two_equal_sectors_max_exposure(self) -> None:
        """Two equal sectors should have max exposure = 0.5."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(5)],
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(5)],
        ]
        plan = create_plan(stocks)

        assert abs(plan.get_max_sector_exposure() - 0.5) < 0.001

    def test_unequal_sectors_max_exposure(self) -> None:
        """Unequal sectors should return the larger weight."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology") for i in range(7)],  # 70%
            *[create_stock(f"HLTH{i}", sector="Healthcare") for i in range(3)],  # 30%
        ]
        plan = create_plan(stocks)

        assert abs(plan.get_max_sector_exposure() - 0.7) < 0.001

    def test_empty_portfolio_max_exposure_is_zero(self) -> None:
        """Empty portfolio should have max exposure = 0."""
        stocks = [create_stock(f"STK{i}", selected=False) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_max_sector_exposure() == 0.0


class TestSectorCount:
    """Tests for sector count calculation."""

    def test_single_sector(self) -> None:
        """All stocks in one sector should return count = 1."""
        stocks = [create_stock(f"STK{i}", sector="Technology") for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_sector_count() == 1

    def test_multiple_sectors(self) -> None:
        """Stocks in multiple sectors should return correct count."""
        stocks = [
            create_stock("TECH1", sector="Technology"),
            create_stock("HLTH1", sector="Healthcare"),
            create_stock("FIN1", sector="Finance"),
            create_stock("NRG1", sector="Energy"),
        ]
        plan = create_plan(stocks)

        assert plan.get_sector_count() == 4

    def test_empty_portfolio_sector_count_is_zero(self) -> None:
        """Empty portfolio should have sector count = 0."""
        stocks = [create_stock(f"STK{i}", selected=False) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_sector_count() == 0


class TestExpectedReturn:
    """Tests for expected return calculation."""

    def test_uniform_returns(self) -> None:
        """Stocks with same returns should give that return."""
        stocks = [create_stock(f"STK{i}", predicted_return=0.10) for i in range(5)]
        plan = create_plan(stocks)

        assert abs(plan.get_expected_return() - 0.10) < 0.001

    def test_mixed_returns(self) -> None:
        """Mixed returns should give weighted average."""
        stocks = [
            create_stock("STK1", predicted_return=0.10),  # 10%
            create_stock("STK2", predicted_return=0.20),  # 20%
        ]
        plan = create_plan(stocks)

        # Equal weight: (0.10 + 0.20) / 2 = 0.15
        assert abs(plan.get_expected_return() - 0.15) < 0.001

    def test_empty_portfolio_return_is_zero(self) -> None:
        """Empty portfolio should have return = 0."""
        stocks = [create_stock(f"STK{i}", selected=False) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_expected_return() == 0.0


class TestReturnVolatility:
    """Tests for return volatility (std dev) calculation."""

    def test_uniform_returns_zero_volatility(self) -> None:
        """All same returns should give volatility = 0."""
        stocks = [create_stock(f"STK{i}", predicted_return=0.10) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_return_volatility() == 0.0

    def test_varied_returns_nonzero_volatility(self) -> None:
        """Varied returns should give positive volatility."""
        stocks = [
            create_stock("STK1", predicted_return=0.05),
            create_stock("STK2", predicted_return=0.10),
            create_stock("STK3", predicted_return=0.15),
            create_stock("STK4", predicted_return=0.20),
        ]
        plan = create_plan(stocks)

        # Mean = 0.125, variance = ((0.05-0.125)^2 + (0.10-0.125)^2 + (0.15-0.125)^2 + (0.20-0.125)^2) / 4
        # = (0.005625 + 0.000625 + 0.000625 + 0.005625) / 4 = 0.003125
        # Std dev = sqrt(0.003125) ≈ 0.0559
        expected_vol = math.sqrt(0.003125)
        assert abs(plan.get_return_volatility() - expected_vol) < 0.0001

    def test_single_stock_zero_volatility(self) -> None:
        """Single stock should have volatility = 0 (need at least 2)."""
        stocks = [create_stock("STK1", predicted_return=0.10)]
        plan = create_plan(stocks)

        assert plan.get_return_volatility() == 0.0


class TestSharpeProxy:
    """Tests for Sharpe ratio proxy calculation."""

    def test_positive_sharpe(self) -> None:
        """Positive return with volatility should give positive Sharpe."""
        stocks = [
            create_stock("STK1", predicted_return=0.05),
            create_stock("STK2", predicted_return=0.10),
            create_stock("STK3", predicted_return=0.15),
            create_stock("STK4", predicted_return=0.20),
        ]
        plan = create_plan(stocks)

        # Return = 0.125, volatility = 0.0559
        # Sharpe = 0.125 / 0.0559 ≈ 2.24
        sharpe = plan.get_sharpe_proxy()
        assert sharpe > 2.0
        assert sharpe < 2.5

    def test_zero_volatility_zero_sharpe(self) -> None:
        """Zero volatility should give Sharpe = 0 (undefined)."""
        stocks = [create_stock(f"STK{i}", predicted_return=0.10) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_sharpe_proxy() == 0.0

    def test_empty_portfolio_zero_sharpe(self) -> None:
        """Empty portfolio should have Sharpe = 0."""
        stocks = [create_stock(f"STK{i}", selected=False) for i in range(5)]
        plan = create_plan(stocks)

        assert plan.get_sharpe_proxy() == 0.0


class TestPlanToMetrics:
    """Tests for the plan_to_metrics converter function."""

    def test_metrics_from_valid_portfolio(self) -> None:
        """plan_to_metrics should return all metrics for valid portfolio."""
        stocks = [
            *[create_stock(f"TECH{i}", sector="Technology", predicted_return=0.12) for i in range(5)],
            *[create_stock(f"HLTH{i}", sector="Healthcare", predicted_return=0.08) for i in range(5)],
        ]
        plan = create_plan(stocks)

        metrics = plan_to_metrics(plan)

        assert metrics is not None
        assert isinstance(metrics, PortfolioMetricsModel)
        assert metrics.sector_count == 2
        assert abs(metrics.expected_return - 0.10) < 0.001
        assert abs(metrics.diversification_score - 0.5) < 0.001
        assert abs(metrics.herfindahl_index - 0.5) < 0.001
        assert abs(metrics.max_sector_exposure - 0.5) < 0.001

    def test_metrics_from_empty_portfolio_is_none(self) -> None:
        """plan_to_metrics should return None for empty portfolio."""
        stocks = [create_stock(f"STK{i}", selected=False) for i in range(5)]
        plan = create_plan(stocks)

        metrics = plan_to_metrics(plan)

        assert metrics is None

    def test_metrics_serialization(self) -> None:
        """Metrics should serialize with camelCase aliases."""
        stocks = [create_stock(f"STK{i}") for i in range(5)]
        plan = create_plan(stocks)

        metrics = plan_to_metrics(plan)
        assert metrics is not None

        data = metrics.model_dump(by_alias=True)
        assert "expectedReturn" in data
        assert "sectorCount" in data
        assert "maxSectorExposure" in data
        assert "herfindahlIndex" in data
        assert "diversificationScore" in data
        assert "returnVolatility" in data
        assert "sharpeProxy" in data
