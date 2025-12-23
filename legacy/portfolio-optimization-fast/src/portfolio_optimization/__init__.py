"""
Portfolio Optimization Quickstart

A SolverForge quickstart demonstrating constraint-based portfolio optimization.
Combines ML predictions with constraint solving to select an optimal stock portfolio.
"""
import uvicorn

from .rest_api import app as app


def main():
    """Run the portfolio optimization REST API server."""
    config = uvicorn.Config(
        "portfolio_optimization:app",
        host="0.0.0.0",
        port=8080,
        log_config="logging.conf",
        use_colors=True,
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
