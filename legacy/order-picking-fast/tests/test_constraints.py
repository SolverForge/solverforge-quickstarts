from solverforge_legacy.solver.test import ConstraintVerifier

from order_picking.domain import (
    Product, Order, OrderItem, Trolley, TrolleyStep, OrderPickingSolution
)
from order_picking.warehouse import WarehouseLocation, Side, new_shelving_id, Column, Row
from order_picking.constraints import (
    define_constraints,
    required_number_of_buckets,
    minimize_order_split_by_trolley,
    minimize_total_distance,
)


# Test locations
LOCATION_A1_LEFT_5 = WarehouseLocation(
    shelving_id=new_shelving_id(Column.COL_A, Row.ROW_1),
    side=Side.LEFT,
    row=5
)
LOCATION_A1_LEFT_8 = WarehouseLocation(
    shelving_id=new_shelving_id(Column.COL_A, Row.ROW_1),
    side=Side.LEFT,
    row=8
)
LOCATION_B1_LEFT_3 = WarehouseLocation(
    shelving_id=new_shelving_id(Column.COL_B, Row.ROW_1),
    side=Side.LEFT,
    row=3
)
LOCATION_E3_RIGHT_9 = WarehouseLocation(
    shelving_id=new_shelving_id(Column.COL_E, Row.ROW_3),
    side=Side.RIGHT,
    row=9
)

# Bucket capacity for tests (48,000 cm3)
BUCKET_CAPACITY = 48000


constraint_verifier = ConstraintVerifier.build(
    define_constraints, OrderPickingSolution, Trolley, TrolleyStep
)


def create_product(id: str, volume: int, location: WarehouseLocation) -> Product:
    return Product(id=id, name=f"Product {id}", volume=volume, location=location)


def create_order_with_items(order_id: str, products: list[Product]) -> tuple[Order, list[OrderItem]]:
    order = Order(id=order_id, items=[])
    items = []
    for i, product in enumerate(products):
        item = OrderItem(id=f"{order_id}-{i}", order=order, product=product)
        order.items.append(item)
        items.append(item)
    return order, items


def connect(trolley: Trolley, *steps: TrolleyStep):
    """Set up trolley-step relationships."""
    trolley.steps = list(steps)
    for i, step in enumerate(steps):
        step.trolley = trolley
        step.previous_step = steps[i - 1] if i > 0 else None
        step.next_step = steps[i + 1] if i < len(steps) - 1 else None


class TestRequiredNumberOfBuckets:
    def test_not_penalized_when_under_capacity(self):
        """Trolley with enough buckets should not be penalized."""
        trolley = Trolley(
            id="1",
            bucket_count=4,
            bucket_capacity=BUCKET_CAPACITY,
            location=LOCATION_A1_LEFT_5
        )
        product = create_product("p1", 10000, LOCATION_B1_LEFT_3)
        order, items = create_order_with_items("o1", [product])
        step = TrolleyStep(id="s1", order_item=items[0])

        connect(trolley, step)

        constraint_verifier.verify_that(required_number_of_buckets).given(
            trolley, step
        ).penalizes_by(0)

    def test_penalized_when_over_bucket_count(self):
        """Trolley with too few buckets should be penalized."""
        trolley = Trolley(
            id="1",
            bucket_count=1,  # Only 1 bucket
            bucket_capacity=BUCKET_CAPACITY,
            location=LOCATION_A1_LEFT_5
        )
        # Create order with volume requiring 2 buckets
        product1 = create_product("p1", 40000, LOCATION_B1_LEFT_3)
        product2 = create_product("p2", 40000, LOCATION_A1_LEFT_8)
        order, items = create_order_with_items("o1", [product1, product2])
        step1 = TrolleyStep(id="s1", order_item=items[0])
        step2 = TrolleyStep(id="s2", order_item=items[1])

        connect(trolley, step1, step2)

        # Total volume: 80000, bucket capacity: 48000
        # Required buckets: ceil(80000/48000) = 2
        # Available: 1, excess: 1
        constraint_verifier.verify_that(required_number_of_buckets).given(
            trolley, step1, step2
        ).penalizes_by(1)


class TestMinimizeOrderSplitByTrolley:
    def test_single_trolley_per_order(self):
        """Order on single trolley should be minimally penalized."""
        trolley = Trolley(
            id="1",
            bucket_count=4,
            bucket_capacity=BUCKET_CAPACITY,
            location=LOCATION_A1_LEFT_5
        )
        product = create_product("p1", 10000, LOCATION_B1_LEFT_3)
        order, items = create_order_with_items("o1", [product])
        step = TrolleyStep(id="s1", order_item=items[0])

        connect(trolley, step)

        # 1 trolley * 1000 = 1000
        constraint_verifier.verify_that(minimize_order_split_by_trolley).given(
            trolley, step
        ).penalizes_by(1000)

    def test_order_split_across_trolleys(self):
        """Order split across trolleys should be penalized more."""
        trolley1 = Trolley(
            id="1",
            bucket_count=4,
            bucket_capacity=BUCKET_CAPACITY,
            location=LOCATION_A1_LEFT_5
        )
        trolley2 = Trolley(
            id="2",
            bucket_count=4,
            bucket_capacity=BUCKET_CAPACITY,
            location=LOCATION_A1_LEFT_5
        )
        product1 = create_product("p1", 10000, LOCATION_B1_LEFT_3)
        product2 = create_product("p2", 10000, LOCATION_A1_LEFT_8)
        order, items = create_order_with_items("o1", [product1, product2])
        step1 = TrolleyStep(id="s1", order_item=items[0])
        step2 = TrolleyStep(id="s2", order_item=items[1])

        connect(trolley1, step1)
        connect(trolley2, step2)

        # 2 trolleys * 1000 = 2000
        constraint_verifier.verify_that(minimize_order_split_by_trolley).given(
            trolley1, trolley2, step1, step2
        ).penalizes_by(2000)


class TestMinimizeTotalDistance:
    def test_total_distance_single_step(self):
        """Total distance for trolley with single step.

        Note: In constraint verification tests, shadow variables aren't triggered,
        so distance_from_previous is None. The constraint only calculates the return
        distance from last step back to origin.
        """
        trolley = Trolley(
            id="1",
            bucket_count=4,
            bucket_capacity=BUCKET_CAPACITY,
            location=LOCATION_A1_LEFT_5
        )
        product = create_product("p1", 10000, LOCATION_A1_LEFT_8)
        order, items = create_order_with_items("o1", [product])
        step = TrolleyStep(id="s1", order_item=items[0])

        connect(trolley, step)

        # Same shelving, same side: |8 - 5| = 3 meters (return distance only in tests)
        constraint_verifier.verify_that(minimize_total_distance).given(
            trolley, step
        ).penalizes_by(3)
