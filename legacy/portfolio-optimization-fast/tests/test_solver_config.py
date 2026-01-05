"""
Tests for solver configuration functionality.

Tests the create_solver_config factory function and dynamic termination time.
"""
import pytest
from portfolio_optimization.solver import create_solver_config
from portfolio_optimization.domain import SolverConfigModel


class TestCreateSolverConfig:
    """Tests for the create_solver_config factory function."""

    def test_default_termination(self):
        """Default solver should terminate after 30 seconds."""
        config = create_solver_config()
        assert config.termination_config.spent_limit.seconds == 30

    def test_custom_termination_60s(self):
        """Custom termination time of 60 seconds should be respected."""
        config = create_solver_config(termination_seconds=60)
        assert config.termination_config.spent_limit.seconds == 60

    def test_custom_termination_10s(self):
        """Minimum termination time of 10 seconds should work."""
        config = create_solver_config(termination_seconds=10)
        assert config.termination_config.spent_limit.seconds == 10

    def test_custom_termination_300s(self):
        """Maximum termination time of 300 seconds (5 min) should work."""
        config = create_solver_config(termination_seconds=300)
        assert config.termination_config.spent_limit.seconds == 300

    def test_solver_config_has_correct_solution_class(self):
        """Solver config should reference PortfolioOptimizationPlan."""
        from portfolio_optimization.domain import PortfolioOptimizationPlan
        config = create_solver_config()
        assert config.solution_class == PortfolioOptimizationPlan

    def test_solver_config_has_correct_entity_class(self):
        """Solver config should include StockSelection entity."""
        from portfolio_optimization.domain import StockSelection
        config = create_solver_config()
        assert StockSelection in config.entity_class_list


class TestSolverConfigModel:
    """Tests for the SolverConfigModel Pydantic model."""

    def test_default_values(self):
        """SolverConfigModel should have default termination of 30 seconds."""
        model = SolverConfigModel()
        assert model.termination_seconds == 30

    def test_custom_termination(self):
        """SolverConfigModel should accept custom termination."""
        model = SolverConfigModel(termination_seconds=60)
        assert model.termination_seconds == 60

    def test_alias_serialization(self):
        """SolverConfigModel should serialize with camelCase alias."""
        model = SolverConfigModel(termination_seconds=45)
        data = model.model_dump(by_alias=True)
        assert "terminationSeconds" in data
        assert data["terminationSeconds"] == 45

    def test_alias_deserialization(self):
        """SolverConfigModel should deserialize from camelCase."""
        model = SolverConfigModel.model_validate({"terminationSeconds": 90})
        assert model.termination_seconds == 90

    def test_minimum_validation(self):
        """SolverConfigModel should reject termination < 10 seconds."""
        with pytest.raises(ValueError):
            SolverConfigModel(termination_seconds=5)

    def test_maximum_validation(self):
        """SolverConfigModel should reject termination > 300 seconds."""
        with pytest.raises(ValueError):
            SolverConfigModel(termination_seconds=400)

    def test_boundary_min(self):
        """SolverConfigModel should accept exactly 10 seconds."""
        model = SolverConfigModel(termination_seconds=10)
        assert model.termination_seconds == 10

    def test_boundary_max(self):
        """SolverConfigModel should accept exactly 300 seconds."""
        model = SolverConfigModel(termination_seconds=300)
        assert model.termination_seconds == 300
