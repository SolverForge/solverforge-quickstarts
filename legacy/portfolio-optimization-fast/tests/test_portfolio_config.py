"""
Tests for PortfolioConfig - the constraint configuration dataclass.

PortfolioConfig holds the threshold values that constraints use:
- target_count: Number of stocks to select (default 20)
- max_per_sector: Maximum stocks per sector (default 5)
- unselected_penalty: Soft penalty per unselected stock (default 10000)

These tests verify:
1. PortfolioConfig dataclass behavior (defaults, equality, hashing)
2. Integration with converters (model_to_plan creates correct config)
3. Integration with demo_data (generate_demo_data creates correct config)
"""
import pytest
from dataclasses import FrozenInstanceError

from portfolio_optimization.domain import (
    PortfolioConfig,
    PortfolioOptimizationPlan,
    PortfolioOptimizationPlanModel,
    StockSelectionModel,
)
from portfolio_optimization.converters import model_to_plan
from portfolio_optimization.demo_data import generate_demo_data, DemoData


class TestPortfolioConfigDataclass:
    """Tests for the PortfolioConfig dataclass itself."""

    def test_default_values(self) -> None:
        """PortfolioConfig should have sensible defaults."""
        config = PortfolioConfig()
        assert config.target_count == 20
        assert config.max_per_sector == 5
        assert config.unselected_penalty == 10000

    def test_custom_values(self) -> None:
        """PortfolioConfig should accept custom values."""
        config = PortfolioConfig(
            target_count=30,
            max_per_sector=8,
            unselected_penalty=5000
        )
        assert config.target_count == 30
        assert config.max_per_sector == 8
        assert config.unselected_penalty == 5000

    def test_equality_same_values(self) -> None:
        """Two PortfolioConfigs with same values should be equal."""
        config1 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        config2 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        assert config1 == config2

    def test_equality_different_values(self) -> None:
        """Two PortfolioConfigs with different values should not be equal."""
        config1 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        config2 = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=10000)
        assert config1 != config2

    def test_equality_different_penalty(self) -> None:
        """PortfolioConfigs with different penalties should not be equal."""
        config1 = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=10000)
        config2 = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=5000)
        assert config1 != config2

    def test_hash_same_values(self) -> None:
        """Two PortfolioConfigs with same values should have same hash."""
        config1 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        config2 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        assert hash(config1) == hash(config2)

    def test_hash_different_values(self) -> None:
        """Two PortfolioConfigs with different values should (likely) have different hash."""
        config1 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        config2 = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=10000)
        # Hash collision is possible but unlikely
        assert hash(config1) != hash(config2)

    def test_usable_as_dict_key(self) -> None:
        """PortfolioConfig should be usable as a dictionary key."""
        config = PortfolioConfig(target_count=15, max_per_sector=4, unselected_penalty=8000)
        d = {config: "value"}
        assert d[config] == "value"

    def test_usable_in_set(self) -> None:
        """PortfolioConfig should be usable in a set."""
        config1 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        config2 = PortfolioConfig(target_count=10, max_per_sector=3, unselected_penalty=10000)
        config3 = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=10000)

        s = {config1, config2, config3}
        # config1 and config2 are equal, so set should have 2 items
        assert len(s) == 2


class TestPortfolioConfigInConverters:
    """Tests for PortfolioConfig creation in converters.model_to_plan()."""

    def _create_plan_model(
        self,
        target_position_count: int = 20,
        max_sector_percentage: float = 0.25
    ) -> PortfolioOptimizationPlanModel:
        """Helper to create a minimal plan model for testing."""
        return PortfolioOptimizationPlanModel(
            stocks=[
                StockSelectionModel(
                    stock_id="TEST",
                    stock_name="Test Corp",
                    sector="Technology",
                    predicted_return=0.10,
                    selected=None
                )
            ],
            target_position_count=target_position_count,
            max_sector_percentage=max_sector_percentage
        )

    def test_model_to_plan_creates_config(self) -> None:
        """model_to_plan should create a PortfolioConfig."""
        model = self._create_plan_model()
        plan = model_to_plan(model)
        assert plan.portfolio_config is not None
        assert isinstance(plan.portfolio_config, PortfolioConfig)

    def test_model_to_plan_config_has_correct_target(self) -> None:
        """model_to_plan should set target_count from target_position_count."""
        model = self._create_plan_model(target_position_count=30)
        plan = model_to_plan(model)
        assert plan.portfolio_config.target_count == 30

    def test_model_to_plan_config_calculates_max_per_sector(self) -> None:
        """model_to_plan should calculate max_per_sector from percentage * target."""
        # 25% of 20 = 5
        model = self._create_plan_model(target_position_count=20, max_sector_percentage=0.25)
        plan = model_to_plan(model)
        assert plan.portfolio_config.max_per_sector == 5

    def test_model_to_plan_config_calculates_max_per_sector_30(self) -> None:
        """max_per_sector calculation for 30 stocks at 25%."""
        # 25% of 30 = 7.5 -> 7 (int)
        model = self._create_plan_model(target_position_count=30, max_sector_percentage=0.25)
        plan = model_to_plan(model)
        assert plan.portfolio_config.max_per_sector == 7

    def test_model_to_plan_config_calculates_max_per_sector_40_percent(self) -> None:
        """max_per_sector calculation for 40% sector limit."""
        # 40% of 20 = 8
        model = self._create_plan_model(target_position_count=20, max_sector_percentage=0.40)
        plan = model_to_plan(model)
        assert plan.portfolio_config.max_per_sector == 8

    def test_model_to_plan_config_minimum_max_per_sector(self) -> None:
        """max_per_sector should be at least 1."""
        # 5% of 10 = 0.5 -> should be clamped to 1
        model = self._create_plan_model(target_position_count=10, max_sector_percentage=0.05)
        plan = model_to_plan(model)
        assert plan.portfolio_config.max_per_sector == 1

    def test_model_to_plan_config_default_penalty(self) -> None:
        """model_to_plan should set default unselected_penalty of 10000."""
        model = self._create_plan_model()
        plan = model_to_plan(model)
        assert plan.portfolio_config.unselected_penalty == 10000


class TestPortfolioConfigInDemoData:
    """Tests for PortfolioConfig creation in generate_demo_data()."""

    def test_small_demo_creates_config(self) -> None:
        """generate_demo_data(SMALL) should create a PortfolioConfig."""
        plan = generate_demo_data(DemoData.SMALL)
        assert plan.portfolio_config is not None
        assert isinstance(plan.portfolio_config, PortfolioConfig)

    def test_large_demo_creates_config(self) -> None:
        """generate_demo_data(LARGE) should create a PortfolioConfig."""
        plan = generate_demo_data(DemoData.LARGE)
        assert plan.portfolio_config is not None
        assert isinstance(plan.portfolio_config, PortfolioConfig)

    def test_small_demo_config_values(self) -> None:
        """SMALL demo should have default config values (20 target, 5 max per sector)."""
        plan = generate_demo_data(DemoData.SMALL)
        assert plan.portfolio_config.target_count == 20
        assert plan.portfolio_config.max_per_sector == 5
        assert plan.portfolio_config.unselected_penalty == 10000

    def test_large_demo_config_values(self) -> None:
        """LARGE demo should have default config values (20 target, 5 max per sector)."""
        plan = generate_demo_data(DemoData.LARGE)
        assert plan.portfolio_config.target_count == 20
        assert plan.portfolio_config.max_per_sector == 5
        assert plan.portfolio_config.unselected_penalty == 10000

    def test_demo_config_matches_plan_fields(self) -> None:
        """PortfolioConfig values should match plan's target_position_count."""
        plan = generate_demo_data(DemoData.SMALL)
        assert plan.portfolio_config.target_count == plan.target_position_count

    def test_demo_config_max_per_sector_matches_percentage(self) -> None:
        """max_per_sector should equal max_sector_percentage * target_position_count."""
        plan = generate_demo_data(DemoData.SMALL)
        expected = int(plan.max_sector_percentage * plan.target_position_count)
        assert plan.portfolio_config.max_per_sector == expected


class TestPortfolioConfigEdgeCases:
    """Edge case tests for PortfolioConfig."""

    def test_very_small_target(self) -> None:
        """PortfolioConfig should work with small target count."""
        config = PortfolioConfig(target_count=5, max_per_sector=2, unselected_penalty=10000)
        assert config.target_count == 5
        assert config.max_per_sector == 2

    def test_very_large_target(self) -> None:
        """PortfolioConfig should work with large target count."""
        config = PortfolioConfig(target_count=100, max_per_sector=25, unselected_penalty=10000)
        assert config.target_count == 100
        assert config.max_per_sector == 25

    def test_zero_penalty(self) -> None:
        """PortfolioConfig should allow zero penalty (disables selection driving)."""
        config = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=0)
        assert config.unselected_penalty == 0

    def test_large_penalty(self) -> None:
        """PortfolioConfig should allow large penalties."""
        config = PortfolioConfig(target_count=20, max_per_sector=5, unselected_penalty=1000000)
        assert config.unselected_penalty == 1000000

    def test_equality_with_non_config(self) -> None:
        """PortfolioConfig should not equal non-PortfolioConfig objects."""
        config = PortfolioConfig()
        assert config != "not a config"
        assert config != 20
        assert config != {"target_count": 20}

    def test_repr(self) -> None:
        """PortfolioConfig should have a useful repr."""
        config = PortfolioConfig(target_count=15, max_per_sector=4, unselected_penalty=8000)
        repr_str = repr(config)
        assert "15" in repr_str
        assert "4" in repr_str
        assert "8000" in repr_str
