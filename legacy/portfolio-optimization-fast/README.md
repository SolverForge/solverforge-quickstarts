# Portfolio Optimization Quickstart

A SolverForge quickstart demonstrating **constraint-based stock portfolio optimization**.

## The Problem

You have **$100,000** to invest and must select **20 stocks** from a pool of candidates.
Each stock has an **ML-predicted return** (e.g., "Apple is expected to return 12%").

**The challenge**: Pick stocks that maximize your expected return while:
- Selecting exactly 20 stocks
- Not putting more than 25% in any single sector (diversification)

## Why Constraint Solving?

With constraints, you describe *what* a valid portfolio looks like, not *how* to build one. Adding a new business rule is a single constraint function—not a rewrite of your algorithm.

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e .

# 3. Run the application
run-app

# 4. Open http://localhost:8080 in your browser
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_constraints.py
```

## Comparison Script

Compare constraint solving vs greedy algorithms:

```bash
python scripts/comparison.py
```

Output shows expected return, sector allocation, and when each approach excels.

## Project Structure

```
portfolio-optimization-fast/
├── src/portfolio_optimization/
│   ├── domain.py          # StockSelection and PortfolioOptimizationPlan
│   ├── constraints.py     # Business rules (stock count, sector limits)
│   ├── solver.py          # SolverForge configuration
│   ├── demo_data.py       # Sample stocks with ML predictions
│   ├── rest_api.py        # FastAPI endpoints
│   └── converters.py      # Domain ↔ REST model conversion
├── tests/
│   ├── test_constraints.py  # Unit tests for each constraint
│   └── test_feasible.py     # Integration tests
├── static/
│   ├── index.html         # Web UI
│   └── app.js             # Frontend logic
├── scripts/
│   └── comparison.py      # Greedy vs Solver comparison
└── pyproject.toml         # Dependencies
```

## Constraints

### Hard Constraints (must be satisfied)

1. **Stock Count**: Must select exactly 20 stocks
2. **Sector Limit**: No sector can exceed 25% (max 5 stocks per sector)

### Soft Constraints (optimize for)

3. **Maximize Return**: Prefer stocks with higher ML-predicted returns

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/demo-data` | List available datasets |
| GET | `/demo-data/{id}` | Load demo data |
| POST | `/portfolios` | Submit for optimization |
| GET | `/portfolios/{id}` | Get current solution |
| GET | `/portfolios/{id}/status` | Get solving status |
| DELETE | `/portfolios/{id}` | Stop solving |
| PUT | `/portfolios/analyze` | Analyze portfolio score |

API documentation available at http://localhost:8080/q/swagger-ui

## Making Your First Customization

Want to add a custom constraint? Try uncommenting the **tutorial constraint** in `constraints.py`:

1. Open `src/portfolio_optimization/constraints.py`
2. Find the `preferred_sector_bonus` function (around line 95)
3. Uncomment it and add it to the `define_constraints` list
4. Restart the app and solve again
5. See how the portfolio shifts toward Technology and Healthcare!

## Finance Concepts

| Term | Definition |
|------|------------|
| **Portfolio** | Collection of stocks you own |
| **Weight** | Percentage of money in each stock |
| **Sector** | Industry category (Tech, Healthcare, etc.) |
| **Predicted Return** | ML model's expected profit/loss |
| **Diversification** | Spreading risk across sectors |

## Learn More

- [SolverForge Documentation](https://solverforge.org/docs)
- [Full Portfolio Optimization Guide](https://solverforge.org/docs/getting-started/portfolio-optimization)
