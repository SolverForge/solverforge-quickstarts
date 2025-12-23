"""
Demo Data for Portfolio Optimization

This module provides sample stock data for the portfolio optimization quickstart.
The data includes 20 stocks across 4 sectors with ML-predicted returns.

In a real application, these predictions would come from an ML model trained
on historical stock data. For this quickstart, we use hardcoded realistic values.

FINANCE CONCEPTS:
- predicted_return: Expected percentage gain (0.12 = 12% expected return)
- sector: Industry classification for diversification
- Equal weight: Each selected stock gets 100%/20 = 5% of the portfolio
"""
from enum import Enum
from dataclasses import dataclass

from .domain import StockSelection, PortfolioOptimizationPlan, PortfolioConfig


class DemoData(Enum):
    """Available demo datasets."""
    SMALL = 'SMALL'   # 20 stocks - good for learning
    LARGE = 'LARGE'   # 50 stocks - more realistic


@dataclass
class DemoDataConfig:
    """Configuration for demo data generation."""
    target_position_count: int
    max_sector_percentage: float


demo_data_configs = {
    DemoData.SMALL: DemoDataConfig(
        target_position_count=20,
        max_sector_percentage=0.25,
    ),
    DemoData.LARGE: DemoDataConfig(
        target_position_count=20,
        max_sector_percentage=0.25,
    ),
}


# Stock data with realistic ML predictions
# Format: (ticker, name, sector, predicted_return)
#
# SMALL dataset: 25 stocks, need to select 20
# This is FEASIBLE because we have 5+ stocks in each of 4 sectors (5*4=20 max from limits)
# Plus we have extra stocks to choose from in each sector
SMALL_DATASET_STOCKS = [
    # TECHNOLOGY (7 stocks) - typically higher predicted returns
    # Solver can pick max 5, so must choose best 5 from 7
    ("AAPL", "Apple Inc.", "Technology", 0.12),
    ("GOOGL", "Alphabet (Google)", "Technology", 0.15),
    ("MSFT", "Microsoft Corp.", "Technology", 0.10),
    ("NVDA", "NVIDIA Corp.", "Technology", 0.18),
    ("META", "Meta Platforms", "Technology", 0.08),
    ("TSLA", "Tesla Inc.", "Technology", 0.20),
    ("AMD", "AMD Inc.", "Technology", 0.14),

    # HEALTHCARE (6 stocks) - moderate returns
    # Solver can pick max 5, so must choose best 5 from 6
    ("JNJ", "Johnson & Johnson", "Healthcare", 0.09),
    ("UNH", "UnitedHealth Group", "Healthcare", 0.11),
    ("PFE", "Pfizer Inc.", "Healthcare", 0.07),
    ("ABBV", "AbbVie Inc.", "Healthcare", 0.10),
    ("TMO", "Thermo Fisher", "Healthcare", 0.13),
    ("DHR", "Danaher Corp.", "Healthcare", 0.12),

    # FINANCE (6 stocks) - stable returns
    # Solver can pick max 5, so must choose best 5 from 6
    ("JPM", "JPMorgan Chase", "Finance", 0.08),
    ("BAC", "Bank of America", "Finance", 0.06),
    ("WFC", "Wells Fargo", "Finance", 0.07),
    ("GS", "Goldman Sachs", "Finance", 0.09),
    ("MS", "Morgan Stanley", "Finance", 0.08),
    ("C", "Citigroup", "Finance", 0.05),

    # ENERGY (6 stocks) - variable returns
    # Solver can pick max 5, so must choose best 5 from 6
    ("XOM", "Exxon Mobil", "Energy", 0.04),
    ("CVX", "Chevron Corp.", "Energy", 0.05),
    ("COP", "ConocoPhillips", "Energy", 0.06),
    ("SLB", "Schlumberger", "Energy", 0.03),
    ("EOG", "EOG Resources", "Energy", 0.07),
    ("PXD", "Pioneer Natural", "Energy", 0.08),
]

LARGE_DATASET_STOCKS = SMALL_DATASET_STOCKS + [
    # Additional TECHNOLOGY (6 more -> 13 total)
    ("CRM", "Salesforce", "Technology", 0.11),
    ("ADBE", "Adobe Inc.", "Technology", 0.09),
    ("ORCL", "Oracle Corp.", "Technology", 0.07),
    ("CSCO", "Cisco Systems", "Technology", 0.06),
    ("IBM", "IBM Corp.", "Technology", 0.04),
    ("QCOM", "Qualcomm", "Technology", 0.13),

    # Additional HEALTHCARE (6 more -> 12 total)
    ("MRK", "Merck & Co.", "Healthcare", 0.08),
    ("LLY", "Eli Lilly", "Healthcare", 0.16),
    ("BMY", "Bristol-Myers", "Healthcare", 0.06),
    ("AMGN", "Amgen Inc.", "Healthcare", 0.09),
    ("GILD", "Gilead Sciences", "Healthcare", 0.05),
    ("ISRG", "Intuitive Surgical", "Healthcare", 0.14),

    # Additional FINANCE (4 more -> 10 total, no duplicates)
    ("AXP", "American Express", "Finance", 0.10),
    ("BLK", "BlackRock", "Finance", 0.11),
    ("SCHW", "Charles Schwab", "Finance", 0.07),
    ("USB", "U.S. Bancorp", "Finance", 0.04),

    # Additional ENERGY (2 more -> 8 total, no duplicates)
    ("OXY", "Occidental Petroleum", "Energy", 0.06),
    ("HAL", "Halliburton", "Energy", 0.05),

    # CONSUMER (new sector - 8 stocks)
    ("AMZN", "Amazon.com", "Consumer", 0.14),
    ("WMT", "Walmart", "Consumer", 0.06),
    ("HD", "Home Depot", "Consumer", 0.08),
    ("MCD", "McDonald's", "Consumer", 0.07),
    ("NKE", "Nike Inc.", "Consumer", 0.09),
    ("SBUX", "Starbucks", "Consumer", 0.05),
    ("PG", "Procter & Gamble", "Consumer", 0.04),
    ("KO", "Coca-Cola", "Consumer", 0.05),
]
# LARGE total: 25 + 6 + 6 + 4 + 2 + 8 = 51 stocks


def generate_demo_data(demo_data: DemoData) -> PortfolioOptimizationPlan:
    """
    Generate demo data for portfolio optimization.

    Args:
        demo_data: Which demo dataset to generate (SMALL or LARGE)

    Returns:
        PortfolioOptimizationPlan with candidate stocks (all unselected initially)

    Example:
        >>> plan = generate_demo_data(DemoData.SMALL)
        >>> len(plan.stocks)
        20
        >>> plan.stocks[0].stock_id
        'AAPL'
    """
    config = demo_data_configs[demo_data]
    stock_data = SMALL_DATASET_STOCKS if demo_data == DemoData.SMALL else LARGE_DATASET_STOCKS

    stocks = [
        StockSelection(
            stock_id=ticker,
            stock_name=name,
            sector=sector,
            predicted_return=predicted_return,
            selection=None,  # To be decided by solver
        )
        for ticker, name, sector, predicted_return in stock_data
    ]

    # Calculate max_per_sector from percentage
    target_count = config.target_position_count
    max_per_sector = max(1, int(config.max_sector_percentage * target_count))

    # Create PortfolioConfig for constraints to access
    portfolio_config = PortfolioConfig(
        target_count=target_count,
        max_per_sector=max_per_sector,
        unselected_penalty=10000,
    )

    return PortfolioOptimizationPlan(
        stocks=stocks,
        target_position_count=config.target_position_count,
        max_sector_percentage=config.max_sector_percentage,
        portfolio_config=portfolio_config,
    )


def get_stock_summary(plan: PortfolioOptimizationPlan) -> str:
    """
    Generate a human-readable summary of the portfolio.

    Useful for debugging and understanding the solution.
    """
    lines = [
        "=" * 60,
        "PORTFOLIO SUMMARY",
        "=" * 60,
    ]

    selected = plan.get_selected_stocks()
    if not selected:
        lines.append("No stocks selected yet.")
        return "\n".join(lines)

    weight = plan.get_weight_per_stock()
    expected_return = plan.get_expected_return()

    lines.append(f"Selected: {len(selected)} stocks @ {weight*100:.1f}% each")
    lines.append(f"Expected Return: {expected_return*100:.2f}%")
    lines.append("")

    # Group by sector
    sector_stocks: dict[str, list[StockSelection]] = {}
    for stock in selected:
        if stock.sector not in sector_stocks:
            sector_stocks[stock.sector] = []
        sector_stocks[stock.sector].append(stock)

    lines.append("BY SECTOR:")
    for sector, stocks in sorted(sector_stocks.items()):
        sector_weight = len(stocks) * weight * 100
        lines.append(f"  {sector}: {len(stocks)} stocks = {sector_weight:.1f}%")
        for stock in sorted(stocks, key=lambda s: -s.predicted_return):
            lines.append(f"    - {stock.stock_id}: {stock.stock_name} ({stock.predicted_return*100:.1f}% pred)")

    lines.append("")
    lines.append(f"Score: {plan.score}")
    lines.append("=" * 60)

    return "\n".join(lines)
