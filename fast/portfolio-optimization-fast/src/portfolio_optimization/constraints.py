"""
Portfolio Optimization Constraints

This module defines the business rules for portfolio construction:

HARD CONSTRAINTS (must be satisfied):
1. must_select_target_count: Pick exactly N stocks (configurable, default 20)
2. sector_exposure_limit: No sector can exceed X stocks (configurable, default 5)

SOFT CONSTRAINTS (optimize for):
3. penalize_unselected_stock: Drive solver to select stocks (high penalty)
4. maximize_expected_return: Prefer stocks with higher ML-predicted returns

WHY CONSTRAINT SOLVING BEATS IF/ELSE:
- With 50 stocks and 5 sectors, there are millions of possible portfolios
- Multiple constraints interact: selecting high-return stocks might violate sector limits
- Greedy algorithms get stuck in local optima
- Constraint solvers explore the solution space systematically

CONFIGURATION:
- Constraints read thresholds from PortfolioConfig (a problem fact)
- target_count: Number of stocks to select
- max_per_sector: Maximum stocks allowed in any single sector
- unselected_penalty: Soft penalty per unselected stock (drives selection)

FINANCE CONCEPTS:
- Sector diversification: Don't put all eggs in one basket
- Expected return: ML model's prediction of future stock performance
- Equal weight: Each selected stock gets the same percentage (5% for 20 stocks)
"""
from typing import Any

from solverforge_legacy.solver.score import (
    constraint_provider,
    ConstraintFactory,
    HardSoftScore,
    ConstraintCollectors,
    Constraint,
)

from .domain import StockSelection, PortfolioConfig


@constraint_provider
def define_constraints(constraint_factory: ConstraintFactory) -> list[Constraint]:
    """
    Define all portfolio optimization constraints.

    Returns a list of constraint functions that the solver will enforce.
    Hard constraints must be satisfied; soft constraints are optimized.

    IMPLEMENTATION NOTE:
    The stock count is enforced via:
    1. must_select_exactly_20_stocks - hard constraint, penalizes if MORE than 20 selected
    2. penalize_unselected_stock - soft constraint with high penalty, drives solver to select stocks

    We don't use a hard "minimum 20" constraint because group_by(count()) on an
    empty stream returns nothing (not 0). Instead, we rely on the large soft penalty
    for unselected stocks to push the solver toward selecting exactly 20.
    """
    return [
        # Hard constraints (must be satisfied)
        must_select_target_count(constraint_factory),  # Max target_count selected
        sector_exposure_limit(constraint_factory),  # Max per sector

        # Soft constraints (maximize/minimize)
        penalize_unselected_stock(constraint_factory),  # Drives selection toward target
        maximize_expected_return(constraint_factory),  # Optimize returns

        # ============================================================
        # TUTORIAL: Uncomment the constraint below to add sector preference
        # ============================================================
        # preferred_sector_bonus(constraint_factory),
    ]


def must_select_target_count(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Hard constraint: Must not select MORE than target_count stocks.

    Business rule: "Pick at most N stocks for the portfolio"
    (N is configurable via PortfolioConfig.target_count, default 20)

    This constraint only fires when count > target_count. Combined with
    penalize_unselected_stock, ensures the target count is reached.

    Note: We use the 'selected' property which returns True/False based on selection.value
    """
    return (
        constraint_factory.for_each(StockSelection)
        .filter(lambda stock: stock.selected is True)
        .group_by(ConstraintCollectors.count())
        .join(PortfolioConfig)
        .filter(lambda count, config: count > config.target_count)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda count, config: count - config.target_count  # Penalty = stocks over target
        )
        .as_constraint("Must select target count")
    )


def penalize_unselected_stock(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Soft constraint: Penalize each unselected stock.

    This constraint drives the solver to select stocks. Without it,
    the solver might leave all stocks unselected (0 hard score from
    other constraints due to empty stream issue).

    We use a LARGE soft penalty (configurable, default 10000) to ensure
    the solver prioritizes selecting stocks before optimizing returns.
    This is higher than the max return reward (~2000 per stock).

    With 25 stocks and 20 needed, the optimal has 5 unselected = -50000 soft.
    """
    return (
        constraint_factory.for_each(StockSelection)
        .filter(lambda stock: stock.selected is False)
        .join(PortfolioConfig)
        .penalize(
            HardSoftScore.ONE_SOFT,
            lambda stock, config: config.unselected_penalty
        )
        .as_constraint("Penalize unselected stock")
    )


def sector_exposure_limit(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Hard constraint: No sector can exceed max_per_sector stocks.

    Business rule: "Maximum N stocks from any single sector"
    (N is configurable via PortfolioConfig.max_per_sector, default 5)

    Why this matters (DIVERSIFICATION):
    - If Tech sector crashes 50%, you only lose X% * 50% of portfolio
    - Without this limit, you might pick all Tech stocks (they have highest returns!)
    - Diversification protects against sector-specific risks

    Example with default (5 stocks max = 25%):
    - Technology: 6 stocks selected = 30% exposure
    - Sector limit: 25% (5 stocks max)
    - Penalty: 6 - 5 = 1 (one stock over limit)
    """
    return (
        constraint_factory.for_each(StockSelection)
        .filter(lambda stock: stock.selected is True)
        .group_by(
            lambda stock: stock.sector,  # Group by sector name
            ConstraintCollectors.count()  # Count stocks per sector
        )
        .join(PortfolioConfig)
        .filter(lambda sector, count, config: count > config.max_per_sector)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda sector, count, config: count - config.max_per_sector
        )
        .as_constraint("Max stocks per sector")
    )


def maximize_expected_return(constraint_factory: ConstraintFactory) -> Constraint:
    """
    Soft constraint: Maximize total expected portfolio return.

    Business rule: "Among all valid portfolios, pick stocks with highest predicted returns"

    Why this is a SOFT constraint:
    - It's our optimization objective, not a hard rule
    - We WANT high returns, but we MUST respect sector limits
    - The solver balances this against hard constraints

    Math:
    - Portfolio return = sum of (weight * predicted_return) for each stock
    - With 20 stocks at 5% each: return = sum of (0.05 * predicted_return)
    - We reward based on predicted_return to prefer high-return stocks

    Example:
    - Apple: predicted_return = 0.12 (12%)
    - Weight: 5% = 0.05
    - Contribution to score: 0.05 * 0.12 * 10000 = 60 points

    Note: We multiply by 10000 to convert decimals to integer scores
    """
    return (
        constraint_factory.for_each(StockSelection)
        .filter(lambda stock: stock.selected is True)
        .reward(
            HardSoftScore.ONE_SOFT,
            # Reward = predicted return (scaled to integer)
            # Higher predicted return = higher reward
            lambda stock: int(stock.predicted_return * 10000)
        )
        .as_constraint("Maximize expected return")
    )


# ============================================================
# TUTORIAL CONSTRAINT: Preferred Sector Bonus
# ============================================================
# Uncomment this constraint to give a small bonus to preferred sectors.
# This demonstrates how to add custom business logic to the optimization.
#
# Scenario: Your investment committee wants to slightly favor Technology
# and Healthcare sectors because they expect these sectors to outperform.
#
# def preferred_sector_bonus(constraint_factory: ConstraintFactory):
#     """
#     Soft constraint: Give a small bonus to stocks from preferred sectors.
#
#     This is a TUTORIAL constraint - uncomment to see how it affects
#     the portfolio composition.
#
#     Business rule: "Slightly prefer Technology and Healthcare stocks"
#
#     Note: This is intentionally a SMALL bonus so it doesn't override
#     the expected return constraint. It just acts as a tiebreaker.
#     """
#     PREFERRED_SECTORS = {"Technology", "Healthcare"}
#     BONUS_POINTS = 50  # Small bonus per preferred stock
#
#     return (
#         constraint_factory.for_each(StockSelection)
#         .filter(lambda stock: stock.selected is True)
#         .filter(lambda stock: stock.sector in PREFERRED_SECTORS)
#         .reward(
#             HardSoftScore.ONE_SOFT,
#             lambda stock: BONUS_POINTS
#         )
#         .as_constraint("Preferred sector bonus")
#     )
