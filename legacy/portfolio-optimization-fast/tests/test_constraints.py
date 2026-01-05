"""
Constraint tests for the Portfolio Optimization quickstart.

Each constraint is tested with both penalizing and non-penalizing scenarios.
This ensures the constraints correctly encode the business rules.

Test Patterns:
1. Create minimal test data (just what's needed for the test)
2. Use constraint_verifier to check penalties/rewards
3. Provide PortfolioConfig as problem fact for parameterized constraints

Finance Concepts Tested:
- Stock selection (configurable target, default 20)
- Sector diversification (configurable max per sector, default 5)
- Return maximization (prefer high-return stocks)
"""
from solverforge_legacy.solver.test import ConstraintVerifier

from portfolio_optimization.domain import (
    StockSelection,
    PortfolioOptimizationPlan,
    PortfolioConfig,
    SelectionValue,
    SELECTED,
    NOT_SELECTED,
)
from portfolio_optimization.constraints import (
    define_constraints,
    must_select_target_count,
    penalize_unselected_stock,
    sector_exposure_limit,
    maximize_expected_return,
)

import pytest


# Create constraint verifier for testing
constraint_verifier = ConstraintVerifier.build(
    define_constraints, PortfolioOptimizationPlan, StockSelection
)

# Default config matches historical defaults
DEFAULT_CONFIG = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=10000)


# ========================================
# Helper Functions
# ========================================

def create_stock(
    stock_id: str,
    sector: str = "Technology",
    predicted_return: float = 0.10,
    selected: bool = True
) -> StockSelection:
    """Create a test stock with sensible defaults.

    Args:
        stock_id: Unique identifier for the stock
        sector: Industry sector (default "Technology")
        predicted_return: ML-predicted return as decimal (default 0.10 = 10%)
        selected: If True, stock is selected for portfolio. If False, not selected.

    Returns:
        StockSelection with the specified parameters
    """
    # Convert boolean to SelectionValue for the planning variable
    selection_value = SELECTED if selected else NOT_SELECTED

    return StockSelection(
        stock_id=stock_id,
        stock_name=f"{stock_id} Corp",
        sector=sector,
        predicted_return=predicted_return,
        selection=selection_value,
    )


# ========================================
# Must Select Target Count Tests
# ========================================

class TestMustSelectTargetCount:
    """Tests for the must_select_target_count constraint.

    This is a parameterized constraint that reads target_count from PortfolioConfig.
    Default is 20 stocks. Only penalizes when count EXCEEDS target.
    """

    def test_exactly_target_no_penalty(self) -> None:
        """Selecting exactly target_count stocks should not be penalized."""
        stocks = [create_stock(f"STK{i}", selected=True) for i in range(20)]

        constraint_verifier.verify_that(must_select_target_count).given(
            *stocks, DEFAULT_CONFIG
        ).penalizes(0)

    def test_one_over_target_penalizes_1(self) -> None:
        """Selecting target_count + 1 stocks should be penalized by 1."""
        stocks = [create_stock(f"STK{i}", selected=True) for i in range(21)]

        constraint_verifier.verify_that(must_select_target_count).given(
            *stocks, DEFAULT_CONFIG
        ).penalizes_by(1)

    def test_five_over_target_penalizes_5(self) -> None:
        """Selecting target_count + 5 stocks should be penalized by 5."""
        stocks = [create_stock(f"STK{i}", selected=True) for i in range(25)]

        constraint_verifier.verify_that(must_select_target_count).given(
            *stocks, DEFAULT_CONFIG
        ).penalizes_by(5)

    def test_under_target_no_penalty(self) -> None:
        """The max constraint doesn't penalize for too few stocks."""
        stocks = [create_stock(f"STK{i}", selected=True) for i in range(19)]

        constraint_verifier.verify_that(must_select_target_count).given(
            *stocks, DEFAULT_CONFIG
        ).penalizes(0)

    def test_custom_target_10(self) -> None:
        """Custom target_count=10: 11 stocks should penalize by 1."""
        config = PortfolioConfig(target_count=10, max_per_sector=5, unselected_penalty=10000)
        stocks = [create_stock(f"STK{i}", selected=True) for i in range(11)]

        constraint_verifier.verify_that(must_select_target_count).given(
            *stocks, config
        ).penalizes_by(1)

    def test_custom_target_30(self) -> None:
        """Custom target_count=30: exactly 30 stocks should not penalize."""
        config = PortfolioConfig(target_count=30, max_per_sector=8, unselected_penalty=10000)
        stocks = [create_stock(f"STK{i}", selected=True) for i in range(30)]

        constraint_verifier.verify_that(must_select_target_count).given(
            *stocks, config
        ).penalizes(0)


class TestPenalizeUnselectedStock:
    """Tests for the penalize_unselected_stock soft constraint.

    This is a parameterized constraint that reads unselected_penalty from PortfolioConfig.
    Default penalty is 10000 per unselected stock.
    It drives the solver to select stocks without affecting hard feasibility.
    """

    def test_selected_stock_no_penalty(self) -> None:
        """A selected stock should not be penalized."""
        stock = create_stock("STK1", selected=True)

        constraint_verifier.verify_that(penalize_unselected_stock).given(
            stock, DEFAULT_CONFIG
        ).penalizes(0)

    def test_unselected_stock_penalized(self) -> None:
        """An unselected stock should be penalized by unselected_penalty (default 10000)."""
        stock = create_stock("STK1", selected=False)

        # 1 unselected * 10000 penalty = 10000
        constraint_verifier.verify_that(penalize_unselected_stock).given(
            stock, DEFAULT_CONFIG
        ).penalizes_by(10000)

    def test_mixed_selection(self) -> None:
        """Mix of selected and unselected stocks - only unselected penalized."""
        selected = [create_stock(f"SEL{i}", selected=True) for i in range(10)]
        unselected = [create_stock(f"UNS{i}", selected=False) for i in range(5)]

        # 5 unselected * 10000 penalty = 50000
        constraint_verifier.verify_that(penalize_unselected_stock).given(
            *selected, *unselected, DEFAULT_CONFIG
        ).penalizes_by(50000)

    def test_custom_penalty(self) -> None:
        """Custom unselected_penalty=5000: 2 unselected should penalize by 10000."""
        config = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=5000)
        unselected = [create_stock(f"UNS{i}", selected=False) for i in range(2)]

        # 2 unselected * 5000 penalty = 10000
        constraint_verifier.verify_that(penalize_unselected_stock).given(
            *unselected, config
        ).penalizes_by(10000)


# ========================================
# Sector Exposure Limit Tests
# ========================================

class TestSectorExposureLimit:
    """Tests for the sector_exposure_limit constraint.

    This is a parameterized constraint that reads max_per_sector from PortfolioConfig.
    Default is 5 stocks per sector (= 25% with 20 total stocks).
    """

    def test_at_limit_no_penalty(self) -> None:
        """Having exactly max_per_sector stocks in each sector should not be penalized."""
        # 5 tech + 5 healthcare + 5 finance + 5 energy = 20 stocks, all at limit
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(5)]
        health = [create_stock(f"HLTH{i}", sector="Healthcare", selected=True) for i in range(5)]
        finance = [create_stock(f"FIN{i}", sector="Finance", selected=True) for i in range(5)]
        energy = [create_stock(f"NRG{i}", sector="Energy", selected=True) for i in range(5)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *tech, *health, *finance, *energy, DEFAULT_CONFIG
        ).penalizes(0)

    def test_one_over_limit_penalizes_1(self) -> None:
        """Having max_per_sector + 1 stocks in a sector should be penalized by 1."""
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(6)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *tech, DEFAULT_CONFIG
        ).penalizes_by(1)

    def test_three_over_limit_penalizes_3(self) -> None:
        """Having max_per_sector + 3 stocks in a sector should be penalized by 3."""
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(8)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *tech, DEFAULT_CONFIG
        ).penalizes_by(3)

    def test_multiple_sectors_over_limit(self) -> None:
        """Multiple sectors over limit should each contribute penalty."""
        # 6 tech (penalty 1) + 7 healthcare (penalty 2) = total penalty 3
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(6)]
        health = [create_stock(f"HLTH{i}", sector="Healthcare", selected=True) for i in range(7)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *tech, *health, DEFAULT_CONFIG
        ).penalizes_by(3)

    def test_unselected_stocks_not_counted(self) -> None:
        """Unselected stocks should not count toward sector limits."""
        # 5 selected tech (at limit) + 5 unselected tech (ignored) = no penalty
        selected = [create_stock(f"STECH{i}", sector="Technology", selected=True) for i in range(5)]
        unselected = [create_stock(f"UTECH{i}", sector="Technology", selected=False) for i in range(5)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *selected, *unselected, DEFAULT_CONFIG
        ).penalizes(0)

    def test_single_sector_at_limit_no_penalty(self) -> None:
        """A single sector with exactly max_per_sector stocks should not be penalized."""
        stocks = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(5)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *stocks, DEFAULT_CONFIG
        ).penalizes(0)

    def test_custom_max_per_sector_3(self) -> None:
        """Custom max_per_sector=3: 4 stocks should penalize by 1."""
        config = PortfolioConfig(target_count=15, max_per_sector=3, unselected_penalty=10000)
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(4)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *tech, config
        ).penalizes_by(1)

    def test_custom_max_per_sector_8(self) -> None:
        """Custom max_per_sector=8: 8 stocks should not penalize."""
        config = PortfolioConfig(target_count=30, max_per_sector=8, unselected_penalty=10000)
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(8)]

        constraint_verifier.verify_that(sector_exposure_limit).given(
            *tech, config
        ).penalizes(0)


# ========================================
# Maximize Expected Return Tests
# ========================================

class TestMaximizeExpectedReturn:
    """Tests for the maximize_expected_return constraint.

    This constraint rewards selected stocks based on predicted_return * 10000.
    It does not use PortfolioConfig (not parameterized).
    """

    def test_high_return_stock_rewarded(self) -> None:
        """Stock with 12% predicted return should be rewarded 1200 points."""
        # 0.12 * 10000 = 1200
        stock = create_stock("AAPL", predicted_return=0.12, selected=True)

        constraint_verifier.verify_that(maximize_expected_return).given(
            stock
        ).rewards_with(1200)

    def test_low_return_stock_rewarded_less(self) -> None:
        """Stock with 5% predicted return should be rewarded 500 points."""
        # 0.05 * 10000 = 500
        stock = create_stock("INTC", predicted_return=0.05, selected=True)

        constraint_verifier.verify_that(maximize_expected_return).given(
            stock
        ).rewards_with(500)

    def test_multiple_stocks_reward_sum(self) -> None:
        """Multiple selected stocks should have rewards summed."""
        # 0.10 * 10000 = 1000, 0.15 * 10000 = 1500, total = 2500
        stock1 = create_stock("STK1", predicted_return=0.10, selected=True)
        stock2 = create_stock("STK2", predicted_return=0.15, selected=True)

        constraint_verifier.verify_that(maximize_expected_return).given(
            stock1, stock2
        ).rewards_with(2500)

    def test_unselected_stock_not_rewarded(self) -> None:
        """Unselected stocks should not contribute to reward."""
        stock = create_stock("STK1", predicted_return=0.20, selected=False)

        constraint_verifier.verify_that(maximize_expected_return).given(
            stock
        ).rewards(0)


# ========================================
# Integration Tests
# ========================================

class TestIntegration:
    """Integration tests for the complete constraint set."""

    def test_valid_portfolio_no_sector_violations(self) -> None:
        """A valid portfolio should have 0 hard constraint violations."""
        # Create valid portfolio: 20 stocks, max 5 per sector
        tech = [create_stock(f"TECH{i}", sector="Technology", predicted_return=0.15, selected=True) for i in range(5)]
        health = [create_stock(f"HLTH{i}", sector="Healthcare", predicted_return=0.10, selected=True) for i in range(5)]
        finance = [create_stock(f"FIN{i}", sector="Finance", predicted_return=0.08, selected=True) for i in range(5)]
        energy = [create_stock(f"NRG{i}", sector="Energy", predicted_return=0.05, selected=True) for i in range(5)]

        all_stocks = tech + health + finance + energy

        # Verify no hard constraint violations
        constraint_verifier.verify_that(sector_exposure_limit).given(*all_stocks, DEFAULT_CONFIG).penalizes(0)
        constraint_verifier.verify_that(must_select_target_count).given(*all_stocks, DEFAULT_CONFIG).penalizes(0)

    def test_high_return_portfolio_preferred(self) -> None:
        """Higher return stocks should result in higher soft score."""
        # Portfolio A: all 10% return stocks
        low_return = [create_stock(f"LOW{i}", predicted_return=0.10, selected=True) for i in range(5)]

        # Portfolio B: all 15% return stocks
        high_return = [create_stock(f"HIGH{i}", predicted_return=0.15, selected=True) for i in range(5)]

        # Calculate rewards
        low_reward = 5 * 1000  # 5 stocks * 0.10 * 10000
        high_reward = 5 * 1500  # 5 stocks * 0.15 * 10000

        constraint_verifier.verify_that(maximize_expected_return).given(*low_return).rewards_with(low_reward)
        constraint_verifier.verify_that(maximize_expected_return).given(*high_return).rewards_with(high_reward)

        assert high_reward > low_reward, "High return portfolio should have higher reward"

    def test_custom_config_integration(self) -> None:
        """Test that custom config values are respected across constraints."""
        # Custom config: target 10 stocks, max 3 per sector
        config = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=5000)

        # Create portfolio: 10 stocks total, 3 per sector (within limits)
        tech = [create_stock(f"TECH{i}", sector="Technology", selected=True) for i in range(3)]
        health = [create_stock(f"HLTH{i}", sector="Healthcare", selected=True) for i in range(3)]
        finance = [create_stock(f"FIN{i}", sector="Finance", selected=True) for i in range(3)]
        energy = [create_stock(f"NRG{i}", sector="Energy", selected=True) for i in range(1)]
        unselected = [create_stock(f"UNS{i}", sector="Other", selected=False) for i in range(2)]

        all_stocks = tech + health + finance + energy + unselected

        # Verify: 10 selected stocks should not penalize target count constraint
        constraint_verifier.verify_that(must_select_target_count).given(*all_stocks, config).penalizes(0)

        # Verify: 3 per sector should not penalize sector limit
        constraint_verifier.verify_that(sector_exposure_limit).given(*all_stocks, config).penalizes(0)

        # Verify: 2 unselected * 5000 penalty = 10000
        constraint_verifier.verify_that(penalize_unselected_stock).given(*all_stocks, config).penalizes_by(10000)
