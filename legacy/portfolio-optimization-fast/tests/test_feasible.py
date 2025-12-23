"""
Feasibility tests for the Portfolio Optimization quickstart.

These tests verify that the solver can find valid solutions
for the demo datasets.
"""
from solverforge_legacy.solver import SolverFactory
from solverforge_legacy.solver.config import (
    SolverConfig,
    ScoreDirectorFactoryConfig,
    TerminationConfig,
    Duration,
)

from portfolio_optimization.domain import PortfolioOptimizationPlan, StockSelection
from portfolio_optimization.constraints import define_constraints
from portfolio_optimization.demo_data import generate_demo_data, DemoData

import pytest


def solve_portfolio(plan: PortfolioOptimizationPlan, seconds: int = 5) -> PortfolioOptimizationPlan:
    """Run the solver on a portfolio for a given number of seconds."""
    solver_config = SolverConfig(
        solution_class=PortfolioOptimizationPlan,
        entity_class_list=[StockSelection],
        score_director_factory_config=ScoreDirectorFactoryConfig(
            constraint_provider_function=define_constraints
        ),
        termination_config=TerminationConfig(spent_limit=Duration(seconds=seconds)),
    )

    solver = SolverFactory.create(solver_config).build_solver()
    return solver.solve(plan)


class TestFeasibility:
    """Test that the solver can find feasible solutions."""

    def test_small_dataset_feasible(self):
        """The SMALL dataset should be solvable to a feasible solution."""
        plan = generate_demo_data(DemoData.SMALL)

        solution = solve_portfolio(plan, seconds=10)

        # Check that we got a solution
        assert solution is not None
        assert solution.score is not None

        # Check feasibility (hard score = 0)
        assert solution.score.hard_score == 0, \
            f"Solution should be feasible, got hard score: {solution.score.hard_score}"

        # Check we selected exactly 20 stocks
        selected_count = solution.get_selected_count()
        assert selected_count == 20, \
            f"Should select 20 stocks, got {selected_count}"

    def test_large_dataset_feasible(self):
        """The LARGE dataset should be solvable to a feasible solution."""
        plan = generate_demo_data(DemoData.LARGE)

        solution = solve_portfolio(plan, seconds=15)

        # Check that we got a solution
        assert solution is not None
        assert solution.score is not None

        # Check feasibility (hard score = 0)
        assert solution.score.hard_score == 0, \
            f"Solution should be feasible, got hard score: {solution.score.hard_score}"

        # Check we selected exactly 20 stocks
        selected_count = solution.get_selected_count()
        assert selected_count == 20, \
            f"Should select 20 stocks, got {selected_count}"

    def test_sector_limits_respected(self):
        """The solver should respect sector exposure limits."""
        plan = generate_demo_data(DemoData.SMALL)

        solution = solve_portfolio(plan, seconds=10)

        # Check sector weights
        sector_weights = solution.get_sector_weights()

        for sector, weight in sector_weights.items():
            assert weight <= 0.26, \
                f"Sector {sector} has {weight*100:.1f}% weight, exceeds 25% limit"

    def test_positive_expected_return(self):
        """The solver should find a portfolio with positive expected return."""
        plan = generate_demo_data(DemoData.SMALL)

        solution = solve_portfolio(plan, seconds=10)

        expected_return = solution.get_expected_return()

        # With our demo data, we should get at least 5% expected return
        assert expected_return > 0.05, \
            f"Expected return should be > 5%, got {expected_return*100:.2f}%"

    def test_expected_return_reasonable(self):
        """The expected return should be reasonable for valid solutions."""
        plan = generate_demo_data(DemoData.SMALL)

        solution = solve_portfolio(plan, seconds=10)

        # Check expected return is positive
        expected_return = solution.get_expected_return()
        assert expected_return > 0, \
            f"Expected return should be positive, got {expected_return}"


class TestDemoData:
    """Test demo data generation."""

    def test_small_dataset_has_25_stocks(self):
        """SMALL dataset should have 25 stocks (5+ per sector for feasibility)."""
        plan = generate_demo_data(DemoData.SMALL)

        assert len(plan.stocks) == 25

    def test_large_dataset_has_51_stocks(self):
        """LARGE dataset should have 51 stocks."""
        plan = generate_demo_data(DemoData.LARGE)

        assert len(plan.stocks) == 51

    def test_stocks_have_sectors(self):
        """All stocks should have a sector assigned."""
        plan = generate_demo_data(DemoData.SMALL)

        for stock in plan.stocks:
            assert stock.sector is not None
            assert len(stock.sector) > 0

    def test_stocks_have_predictions(self):
        """All stocks should have predicted returns."""
        plan = generate_demo_data(DemoData.SMALL)

        for stock in plan.stocks:
            assert stock.predicted_return is not None
            # Predictions should be reasonable (-10% to +25%)
            assert -0.10 <= stock.predicted_return <= 0.25

    def test_stocks_initially_unselected(self):
        """All stocks should start with selected=None."""
        plan = generate_demo_data(DemoData.SMALL)

        for stock in plan.stocks:
            assert stock.selected is None

    def test_has_multiple_sectors(self):
        """Demo data should have multiple sectors for diversification testing."""
        plan = generate_demo_data(DemoData.SMALL)

        sectors = {stock.sector for stock in plan.stocks}

        assert len(sectors) >= 4, \
            f"Should have at least 4 sectors for diversification, got {len(sectors)}"
