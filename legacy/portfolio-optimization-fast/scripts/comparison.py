#!/usr/bin/env python3
"""
Comparison Script: Constraint Solver vs Greedy Algorithm

This script compares two approaches to portfolio optimization:

1. GREEDY ALGORITHM (if/else logic):
   - Sort stocks by predicted return
   - Pick top N stocks
   - Check sector limits, skip if violated

2. CONSTRAINT SOLVER (SolverForge):
   - Define constraints declaratively
   - Let solver explore solution space

For this simplified problem (Boolean selection with sector limits), both
approaches find good solutions. The value of constraint solving emerges
when you add complex business rules - each new constraint is just a
function, not a rewrite of your algorithm.

Run this script:
    cd portfolio-optimization-fast
    python scripts/comparison.py

OUTPUT SHOWS:
- Expected return comparison
- Sector allocation differences
- Which stocks each method selects
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from portfolio_optimization.demo_data import generate_demo_data, DemoData
from portfolio_optimization.domain import (
    PortfolioOptimizationPlan,
    StockSelection,
    SELECTED,
    NOT_SELECTED,
)


def calculate_score(plan: PortfolioOptimizationPlan) -> int:
    """Calculate the soft score for a portfolio using the same logic as constraints."""
    selected = [s for s in plan.stocks if s.selected is True]
    unselected = [s for s in plan.stocks if s.selected is False]

    # Penalty for unselected stocks
    unselected_penalty = len(unselected) * plan.portfolio_config.unselected_penalty

    # Reward for selected stock returns
    return_reward = sum(int(s.predicted_return * 10000) for s in selected)

    soft_score = return_reward - unselected_penalty
    return soft_score


def greedy_portfolio(plan: PortfolioOptimizationPlan) -> PortfolioOptimizationPlan:
    """
    Build portfolio using greedy if/else logic.

    Algorithm:
    1. Sort stocks by predicted return (highest first)
    2. For each stock:
       - If we have fewer than target_count stocks AND
       - Adding this stock won't exceed sector limit
       - Then select it
    3. Assign equal weights

    This is how many developers would implement portfolio construction
    without knowing about constraint solvers.
    """
    # Configuration
    target_count = plan.target_position_count
    max_per_sector = 5  # 5 stocks * 5% = 25% sector limit

    # Sort by predicted return (highest first)
    sorted_stocks = sorted(
        plan.stocks,
        key=lambda s: s.predicted_return,
        reverse=True
    )

    # Track selections
    selected_ids = set()
    sector_counts: dict[str, int] = {}

    for stock in sorted_stocks:
        # Stop if we have enough stocks
        if len(selected_ids) >= target_count:
            break

        # Check sector limit
        current_sector_count = sector_counts.get(stock.sector, 0)
        if current_sector_count >= max_per_sector:
            continue  # Skip - would violate sector limit

        # Select this stock
        selected_ids.add(stock.stock_id)
        sector_counts[stock.sector] = current_sector_count + 1

    # Create result with selections
    result_stocks = [
        StockSelection(
            stock_id=s.stock_id,
            stock_name=s.stock_name,
            sector=s.sector,
            predicted_return=s.predicted_return,
            selection=SELECTED if s.stock_id in selected_ids else NOT_SELECTED
        )
        for s in plan.stocks
    ]

    return PortfolioOptimizationPlan(
        stocks=result_stocks,
        target_position_count=target_count,
        max_sector_percentage=plan.max_sector_percentage,
    )


def solver_portfolio(plan: PortfolioOptimizationPlan) -> PortfolioOptimizationPlan:
    """
    Build portfolio using SolverForge constraint solver.

    This uses the same constraints defined in constraints.py:
    - Must select exactly 20 stocks
    - Max 5 stocks per sector (25%)
    - Maximize expected return
    """
    from solverforge_legacy.solver import SolverFactory
    from solverforge_legacy.solver.config import (
        SolverConfig,
        ScoreDirectorFactoryConfig,
        TerminationConfig,
        Duration,
    )
    from portfolio_optimization.constraints import define_constraints

    # Configure solver with 30-second time limit for comparison
    solver_config = SolverConfig(
        solution_class=PortfolioOptimizationPlan,
        entity_class_list=[StockSelection],
        score_director_factory_config=ScoreDirectorFactoryConfig(
            constraint_provider_function=define_constraints
        ),
        termination_config=TerminationConfig(spent_limit=Duration(seconds=30)),
    )

    solver = SolverFactory.create(solver_config).build_solver()
    solution = solver.solve(plan)

    return solution


def calculate_metrics(plan: PortfolioOptimizationPlan) -> dict:
    """Calculate portfolio metrics for comparison."""
    selected = [s for s in plan.stocks if s.selected]
    count = len(selected)

    if count == 0:
        return {
            'selected_count': 0,
            'expected_return': 0,
            'sector_allocation': {},
            'selected_tickers': [],
        }

    weight = 1.0 / count
    expected_return = sum(s.predicted_return * weight for s in selected)

    # Sector allocation
    sector_counts: dict[str, int] = {}
    for s in selected:
        sector_counts[s.sector] = sector_counts.get(s.sector, 0) + 1

    sector_allocation = {
        sector: count * weight * 100
        for sector, count in sector_counts.items()
    }

    return {
        'selected_count': count,
        'expected_return': expected_return * 100,  # As percentage
        'sector_allocation': sector_allocation,
        'selected_tickers': sorted([s.stock_id for s in selected]),
    }


def print_comparison(greedy_metrics: dict, solver_metrics: dict):
    """Print side-by-side comparison of the two approaches."""
    print("=" * 70)
    print("PORTFOLIO OPTIMIZATION: GREEDY vs CONSTRAINT SOLVER")
    print("=" * 70)
    print()

    # Basic metrics
    print("SUMMARY")
    print("-" * 70)
    print(f"{'Metric':<25} {'Greedy':>20} {'Solver':>20}")
    print("-" * 70)
    print(f"{'Selected Stocks':<25} {greedy_metrics['selected_count']:>20} {solver_metrics['selected_count']:>20}")
    print(f"{'Expected Return':<25} {greedy_metrics['expected_return']:>19.2f}% {solver_metrics['expected_return']:>19.2f}%")

    # Return difference
    diff = solver_metrics['expected_return'] - greedy_metrics['expected_return']
    print(f"{'Solver Advantage':<25} {'':>20} {diff:>+19.2f}%")
    print()

    # Sector allocation
    print("SECTOR ALLOCATION")
    print("-" * 70)
    all_sectors = set(greedy_metrics['sector_allocation'].keys()) | set(solver_metrics['sector_allocation'].keys())

    for sector in sorted(all_sectors):
        greedy_pct = greedy_metrics['sector_allocation'].get(sector, 0)
        solver_pct = solver_metrics['sector_allocation'].get(sector, 0)
        print(f"  {sector:<23} {greedy_pct:>19.1f}% {solver_pct:>19.1f}%")
    print()

    # Stock differences
    greedy_set = set(greedy_metrics['selected_tickers'])
    solver_set = set(solver_metrics['selected_tickers'])

    only_greedy = greedy_set - solver_set
    only_solver = solver_set - greedy_set
    both = greedy_set & solver_set

    print("STOCK SELECTION DIFFERENCES")
    print("-" * 70)
    print(f"  Stocks in both:        {len(both)}")
    print(f"  Only in Greedy:        {len(only_greedy)} - {', '.join(sorted(only_greedy)) or 'None'}")
    print(f"  Only in Solver:        {len(only_solver)} - {', '.join(sorted(only_solver)) or 'None'}")
    print()

    # Analysis
    print("ANALYSIS")
    print("-" * 70)
    if diff > 0.5:
        print(f"  The constraint solver found a portfolio with {diff:.2f}% higher expected return!")
        print()
        print("  Why? The greedy algorithm:")
        print("  - Makes locally optimal choices (always picks highest return next)")
        print("  - Gets stuck when sector limits are reached")
        print("  - Can't backtrack to find better global solutions")
        print()
        print("  The constraint solver:")
        print("  - Explores the full solution space systematically")
        print("  - Balances high returns with sector diversification")
        print("  - Finds the globally optimal portfolio")
    elif diff > -0.5:
        print("  Both methods found similar solutions for this dataset.")
        print()
        print("  This is expected for portfolio selection problems where greedy")
        print("  algorithms perform well. The value of constraint solvers becomes")
        print("  apparent with more complex constraints (minimum sector holdings,")
        print("  stock correlations, risk limits) or larger search spaces.")
    else:
        print(f"  The greedy algorithm found a better solution ({-diff:.2f}% higher return)!")
        print()
        print("  Why? For simple portfolio selection problems, greedy algorithms")
        print("  are highly effective because:")
        print("  - The objective (maximize return) aligns with greedy choices")
        print("  - Sector limits are easy to satisfy by skipping stocks")
        print()
        print("  Constraint solvers excel with more complex constraints like:")
        print("  - Minimum stocks per sector (diversification floors)")
        print("  - Correlation limits between selected stocks")
        print("  - Multi-objective optimization (return vs risk)")
    print()
    print("=" * 70)


def main():
    print("\nLoading demo data...")
    plan = generate_demo_data(DemoData.LARGE)

    # Count unique sectors
    sectors = set(s.sector for s in plan.stocks)
    print(f"Dataset: {len(plan.stocks)} stocks across {len(sectors)} sectors")
    print(f"Target: Select {plan.target_position_count} stocks with max 25% per sector")
    print()

    print("Running GREEDY algorithm...")
    greedy_result = greedy_portfolio(plan)
    greedy_metrics = calculate_metrics(greedy_result)
    print(f"  Selected {greedy_metrics['selected_count']} stocks, {greedy_metrics['expected_return']:.2f}% expected return")

    print("Running CONSTRAINT SOLVER (30 seconds)...")
    solver_result = solver_portfolio(plan)
    solver_metrics = calculate_metrics(solver_result)
    print(f"  Selected {solver_metrics['selected_count']} stocks, {solver_metrics['expected_return']:.2f}% expected return")
    print()

    print_comparison(greedy_metrics, solver_metrics)


if __name__ == "__main__":
    main()
