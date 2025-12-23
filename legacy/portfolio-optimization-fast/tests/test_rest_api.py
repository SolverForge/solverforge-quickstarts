"""
Tests for REST API endpoints.

Tests that configuration is properly received and applied.
"""
import pytest
from fastapi.testclient import TestClient
from portfolio_optimization.rest_api import app
from portfolio_optimization.domain import (
    PortfolioOptimizationPlanModel,
    StockSelectionModel,
    SolverConfigModel,
)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestDemoDataEndpoints:
    """Tests for demo data endpoints."""

    def test_list_demo_data(self, client):
        """GET /demo-data should return available datasets."""
        response = client.get("/demo-data")
        assert response.status_code == 200
        data = response.json()
        assert "SMALL" in data
        assert "LARGE" in data

    def test_get_small_demo_data(self, client):
        """GET /demo-data/SMALL should return 25 stocks."""
        response = client.get("/demo-data/SMALL")
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert len(data["stocks"]) == 25

    def test_get_large_demo_data(self, client):
        """GET /demo-data/LARGE should return 51 stocks."""
        response = client.get("/demo-data/LARGE")
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert len(data["stocks"]) == 51


class TestSolverConfigEndpoints:
    """Tests for solver configuration handling."""

    def test_plan_model_accepts_solver_config(self):
        """PortfolioOptimizationPlanModel should accept solverConfig."""
        model = PortfolioOptimizationPlanModel(
            stocks=[
                StockSelectionModel(
                    stockId="AAPL",
                    stockName="Apple",
                    sector="Technology",
                    predictedReturn=0.12,
                    selected=None
                )
            ],
            targetPositionCount=20,
            maxSectorPercentage=0.25,
            solverConfig=SolverConfigModel(terminationSeconds=60)
        )
        assert model.solver_config is not None
        assert model.solver_config.termination_seconds == 60

    def test_plan_model_serializes_solver_config(self):
        """solverConfig should serialize with camelCase aliases."""
        model = PortfolioOptimizationPlanModel(
            stocks=[],
            solverConfig=SolverConfigModel(terminationSeconds=90)
        )
        data = model.model_dump(by_alias=True)
        assert "solverConfig" in data
        assert data["solverConfig"]["terminationSeconds"] == 90

    def test_plan_model_deserializes_solver_config(self):
        """solverConfig should deserialize from JSON."""
        json_data = {
            "stocks": [
                {
                    "stockId": "AAPL",
                    "stockName": "Apple",
                    "sector": "Technology",
                    "predictedReturn": 0.12,
                    "selected": None
                }
            ],
            "targetPositionCount": 15,
            "maxSectorPercentage": 0.30,
            "solverConfig": {
                "terminationSeconds": 120
            }
        }
        model = PortfolioOptimizationPlanModel.model_validate(json_data)
        assert model.target_position_count == 15
        assert model.max_sector_percentage == 0.30
        assert model.solver_config is not None
        assert model.solver_config.termination_seconds == 120

    def test_plan_without_solver_config(self):
        """Plan should work without solverConfig (uses defaults)."""
        json_data = {
            "stocks": [],
            "targetPositionCount": 20,
            "maxSectorPercentage": 0.25
        }
        model = PortfolioOptimizationPlanModel.model_validate(json_data)
        assert model.solver_config is None  # None is OK, will use default 30s

    def test_post_portfolio_with_solver_config(self, client):
        """POST /portfolios should accept solverConfig in request body."""
        # First get demo data
        demo_response = client.get("/demo-data/SMALL")
        plan_data = demo_response.json()

        # Add solver config
        plan_data["solverConfig"] = {
            "terminationSeconds": 10  # Use short time for test
        }

        # Submit for solving
        response = client.post("/portfolios", json=plan_data)
        assert response.status_code == 200
        job_id = response.json()
        assert job_id is not None
        assert len(job_id) > 0

        # Stop solving immediately (we just want to verify config was accepted)
        stop_response = client.delete(f"/portfolios/{job_id}")
        assert stop_response.status_code == 200
