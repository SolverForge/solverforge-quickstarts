from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import List

from .domain import Product, Order, OrderItem, Trolley, TrolleyStep, OrderPickingSolution
from .warehouse import WarehouseLocation, Side, Column, Row, new_shelving_id, Shelving


# Configuration constants - matches Java timefold-quickstarts
TROLLEYS_COUNT = 5
BUCKET_COUNT = 4
BUCKET_CAPACITY = 60 * 40 * 20  # 48000 cm3
ORDERS_COUNT = 8
ORDER_ITEMS_SIZE_MINIMUM = 1

# Start location for all trolleys
START_LOCATION = WarehouseLocation(
    shelving_id=new_shelving_id(Column.COL_A, Row.ROW_1),
    side=Side.LEFT,
    row=0
)


class ProductFamily(Enum):
    GENERAL_FOOD = "GENERAL_FOOD"
    FRESH_FOOD = "FRESH_FOOD"
    MEET_AND_FISH = "MEET_AND_FISH"
    FROZEN_PRODUCTS = "FROZEN_PRODUCTS"
    FRUITS_AND_VEGETABLES = "FRUITS_AND_VEGETABLES"
    HOUSE_CLEANING = "HOUSE_CLEANING"
    DRINKS = "DRINKS"
    SNACKS = "SNACKS"
    PETS = "PETS"


@dataclass
class ProductTemplate:
    """Template for a product before location is assigned."""
    id: str
    name: str
    volume: int  # in cm3
    family: ProductFamily


# Product templates without locations (locations are assigned randomly)
PRODUCT_TEMPLATES: List[ProductTemplate] = [
    # GENERAL_FOOD
    ProductTemplate("0", "Kelloggs Cornflakes", 30 * 12 * 35, ProductFamily.GENERAL_FOOD),
    ProductTemplate("1", "Cream Crackers", 23 * 7 * 2, ProductFamily.GENERAL_FOOD),
    ProductTemplate("2", "Tea Bags 240 packet", 2 * 6 * 15, ProductFamily.GENERAL_FOOD),
    ProductTemplate("3", "Tomato Soup Can", 10 * 10 * 10, ProductFamily.GENERAL_FOOD),
    ProductTemplate("4", "Baked Beans in Tomato Sauce", 10 * 10 * 10, ProductFamily.GENERAL_FOOD),
    ProductTemplate("5", "Classic Mint Sauce", 8 * 10 * 8, ProductFamily.GENERAL_FOOD),
    ProductTemplate("6", "Raspberry Conserve", 8 * 10 * 8, ProductFamily.GENERAL_FOOD),
    ProductTemplate("7", "Orange Fine Shred Marmalade", 7 * 8 * 7, ProductFamily.GENERAL_FOOD),

    # FRESH_FOOD
    ProductTemplate("8", "Free Range Eggs 6 Pack", 15 * 10 * 8, ProductFamily.FRESH_FOOD),
    ProductTemplate("9", "Mature Cheddar 400G", 10 * 9 * 5, ProductFamily.FRESH_FOOD),
    ProductTemplate("10", "Butter Packet", 12 * 5 * 5, ProductFamily.FRESH_FOOD),

    # FRUITS_AND_VEGETABLES
    ProductTemplate("11", "Iceberg Lettuce Each", 2500, ProductFamily.FRUITS_AND_VEGETABLES),
    ProductTemplate("12", "Carrots 1Kg", 1000, ProductFamily.FRUITS_AND_VEGETABLES),
    ProductTemplate("13", "Organic Fair Trade Bananas 5 Pack", 1800, ProductFamily.FRUITS_AND_VEGETABLES),
    ProductTemplate("14", "Gala Apple Minimum 5 Pack", 25 * 20 * 10, ProductFamily.FRUITS_AND_VEGETABLES),
    ProductTemplate("15", "Orange Bag 3kg", 29 * 20 * 15, ProductFamily.FRUITS_AND_VEGETABLES),

    # HOUSE_CLEANING
    ProductTemplate("16", "Fairy Non Biological Laundry Liquid 4.55L", 5000, ProductFamily.HOUSE_CLEANING),
    ProductTemplate("17", "Toilet Tissue 8 Roll White", 50 * 20 * 20, ProductFamily.HOUSE_CLEANING),
    ProductTemplate("18", "Kitchen Roll 200 Sheets x 2", 30 * 30 * 15, ProductFamily.HOUSE_CLEANING),
    ProductTemplate("19", "Stainless Steel Cleaner 500Ml", 500, ProductFamily.HOUSE_CLEANING),
    ProductTemplate("20", "Antibacterial Surface Spray", 12 * 4 * 25, ProductFamily.HOUSE_CLEANING),

    # MEET_AND_FISH
    ProductTemplate("21", "Beef Lean Steak Mince 500g", 500, ProductFamily.MEET_AND_FISH),
    ProductTemplate("22", "Smoked Salmon 120G", 150, ProductFamily.MEET_AND_FISH),
    ProductTemplate("23", "Steak Burgers 454G", 450, ProductFamily.MEET_AND_FISH),
    ProductTemplate("24", "Pork Cooked Ham 125G", 125, ProductFamily.MEET_AND_FISH),
    ProductTemplate("25", "Chicken Breast Fillets 300G", 300, ProductFamily.MEET_AND_FISH),

    # DRINKS
    ProductTemplate("26", "6 Milk Bricks Pack", 22 * 16 * 21, ProductFamily.DRINKS),
    ProductTemplate("27", "Milk Brick", 1232, ProductFamily.DRINKS),
    ProductTemplate("28", "Skimmed Milk 2.5L", 2500, ProductFamily.DRINKS),
    ProductTemplate("29", "3L Orange Juice", 3 * 1000, ProductFamily.DRINKS),
    ProductTemplate("30", "Alcohol Free Beer 4 Pack", 30 * 15 * 30, ProductFamily.DRINKS),
    ProductTemplate("31", "Pepsi Regular Bottle", 1000, ProductFamily.DRINKS),
    ProductTemplate("32", "Pepsi Diet 6 x 330ml", 35 * 12 * 12, ProductFamily.DRINKS),
    ProductTemplate("33", "Schweppes Lemonade 2L", 2000, ProductFamily.DRINKS),
    ProductTemplate("34", "Coke Zero 8 x 330ml", 40 * 12 * 12, ProductFamily.DRINKS),
    ProductTemplate("35", "Natural Mineral Water Still 6 X 1.5Ltr", 6 * 1500, ProductFamily.DRINKS),

    # SNACKS
    ProductTemplate("36", "Cocktail Crisps 6 Pack", 20 * 10 * 10, ProductFamily.SNACKS),
]

# Shelving assignments per product family
SHELVINGS_PER_FAMILY = {
    ProductFamily.FRUITS_AND_VEGETABLES: [
        new_shelving_id(Column.COL_A, Row.ROW_1),
        new_shelving_id(Column.COL_A, Row.ROW_2),
    ],
    ProductFamily.FRESH_FOOD: [
        new_shelving_id(Column.COL_A, Row.ROW_3),
    ],
    ProductFamily.MEET_AND_FISH: [
        new_shelving_id(Column.COL_B, Row.ROW_2),
        new_shelving_id(Column.COL_B, Row.ROW_3),
    ],
    ProductFamily.FROZEN_PRODUCTS: [
        new_shelving_id(Column.COL_B, Row.ROW_2),
        new_shelving_id(Column.COL_B, Row.ROW_1),
    ],
    ProductFamily.DRINKS: [
        new_shelving_id(Column.COL_D, Row.ROW_1),
    ],
    ProductFamily.SNACKS: [
        new_shelving_id(Column.COL_D, Row.ROW_2),
    ],
    ProductFamily.GENERAL_FOOD: [
        new_shelving_id(Column.COL_B, Row.ROW_2),
        new_shelving_id(Column.COL_C, Row.ROW_3),
        new_shelving_id(Column.COL_D, Row.ROW_2),
        new_shelving_id(Column.COL_D, Row.ROW_3),
    ],
    ProductFamily.HOUSE_CLEANING: [
        new_shelving_id(Column.COL_E, Row.ROW_2),
        new_shelving_id(Column.COL_E, Row.ROW_1),
    ],
    ProductFamily.PETS: [
        new_shelving_id(Column.COL_E, Row.ROW_3),
    ],
}


def get_max_product_size() -> int:
    """Get the maximum product volume."""
    return max(p.volume for p in PRODUCT_TEMPLATES)


def validate_bucket_capacity(bucket_capacity: int) -> None:
    """Ensure bucket capacity can hold the largest product."""
    max_size = get_max_product_size()
    if bucket_capacity < max_size:
        raise ValueError(
            f"The selected bucketCapacity: {bucket_capacity}, is lower than the "
            f"maximum product size: {max_size}. Please use a higher value."
        )


def build_products(random: Random) -> List[Product]:
    """Build products with random warehouse locations based on their family."""
    products = []
    for template in PRODUCT_TEMPLATES:
        shelving_ids = SHELVINGS_PER_FAMILY[template.family]
        shelving_id = random.choice(shelving_ids)
        side = random.choice(list(Side))
        row = random.randint(1, Shelving.ROWS_SIZE)

        location = WarehouseLocation(
            shelving_id=shelving_id,
            side=side,
            row=row
        )
        products.append(Product(
            id=template.id,
            name=template.name,
            volume=template.volume,
            location=location
        ))
    return products


def build_trolleys(
    count: int,
    bucket_count: int,
    bucket_capacity: int,
    start_location: WarehouseLocation
) -> List[Trolley]:
    """Build trolleys at the start location."""
    return [
        Trolley(
            id=str(i),
            bucket_count=bucket_count,
            bucket_capacity=bucket_capacity,
            location=start_location
        )
        for i in range(1, count + 1)
    ]


def build_orders(count: int, products: List[Product], random: Random) -> List[Order]:
    """Build orders with random products - matches Java implementation."""
    orders = []
    for order_num in range(1, count + 1):
        # Java: ORDER_ITEMS_SIZE_MINIMUM + random.nextInt(products.size() - ORDER_ITEMS_SIZE_MINIMUM)
        order_items_size = ORDER_ITEMS_SIZE_MINIMUM + random.randint(0, len(products) - ORDER_ITEMS_SIZE_MINIMUM - 1)

        order_items = []
        order_product_ids = set()
        order = Order(id=str(order_num), items=order_items)

        item_num = 1
        for _ in range(order_items_size):
            product_index = random.randint(0, len(products) - 1)
            product = products[product_index]
            # Avoid duplicate products in the same order
            if product.id not in order_product_ids:
                order_items.append(OrderItem(
                    id=str(item_num),
                    order=order,
                    product=product
                ))
                order_product_ids.add(product.id)
                item_num += 1

        orders.append(order)
    return orders


def build_trolley_steps(orders: List[Order]) -> List[TrolleyStep]:
    """Build trolley steps from order items."""
    steps = []
    for order in orders:
        for idx, item in enumerate(order.items):
            steps.append(TrolleyStep(
                id=f"{order.id}-{idx}",
                order_item=item
            ))
    return steps


def generate_demo_data() -> OrderPickingSolution:
    """Generate the complete demo data set."""
    random = Random(37)  # Fixed seed for reproducibility

    validate_bucket_capacity(BUCKET_CAPACITY)

    products = build_products(random)
    trolleys = build_trolleys(TROLLEYS_COUNT, BUCKET_COUNT, BUCKET_CAPACITY, START_LOCATION)
    orders = build_orders(ORDERS_COUNT, products, random)
    trolley_steps = build_trolley_steps(orders)

    # Pre-assign steps evenly across trolleys so we have paths to visualize immediately
    # The solver will optimize the distribution
    if trolleys:
        for i, step in enumerate(trolley_steps):
            trolley = trolleys[i % len(trolleys)]
            trolley.steps.append(step)
            step.trolley = trolley

    return OrderPickingSolution(
        trolleys=trolleys,
        trolley_steps=trolley_steps
    )
