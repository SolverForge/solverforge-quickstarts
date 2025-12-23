from typing import Dict
from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.score import HardSoftDecimalScore

from . import domain
from .warehouse import WarehouseLocation, Side


# =============================================================================
# Domain to API Model Conversion
# =============================================================================

def location_to_model(location: WarehouseLocation) -> domain.WarehouseLocationModel:
    return domain.WarehouseLocationModel(
        shelving_id=location.shelving_id,
        side=location.side.name,
        row=location.row
    )


def product_to_model(product: domain.Product) -> domain.ProductModel:
    return domain.ProductModel(
        id=product.id,
        name=product.name,
        volume=product.volume,
        location=location_to_model(product.location)
    )


def order_item_to_model(item: domain.OrderItem) -> domain.OrderItemModel:
    return domain.OrderItemModel(
        id=item.id,
        order_id=item.order_id,
        product=product_to_model(item.product)
    )


def order_to_model(order: domain.Order) -> domain.OrderModel:
    return domain.OrderModel(
        id=order.id,
        items=[order_item_to_model(item) for item in order.items]
    )


def trolley_step_to_model(step: domain.TrolleyStep) -> domain.TrolleyStepModel:
    return domain.TrolleyStepModel(
        id=step.id,
        order_item=order_item_to_model(step.order_item),
        trolley=step.trolley.id if step.trolley else None,
        trolley_id=step.trolley_id
    )


def trolley_to_model(trolley: domain.Trolley) -> domain.TrolleyModel:
    return domain.TrolleyModel(
        id=trolley.id,
        bucket_count=trolley.bucket_count,
        bucket_capacity=trolley.bucket_capacity,
        location=location_to_model(trolley.location),
        steps=[step.id for step in trolley.steps]
    )


def solution_to_model(solution: domain.OrderPickingSolution) -> domain.OrderPickingSolutionModel:
    return domain.OrderPickingSolutionModel(
        trolleys=[trolley_to_model(t) for t in solution.trolleys],
        trolley_steps=[trolley_step_to_model(s) for s in solution.trolley_steps],
        score=str(solution.score) if solution.score else None,
        solver_status=solution.solver_status.name if solution.solver_status else None
    )


# =============================================================================
# API Model to Domain Conversion
# =============================================================================

def model_to_location(model: domain.WarehouseLocationModel) -> WarehouseLocation:
    return WarehouseLocation(
        shelving_id=model.shelving_id,
        side=Side[model.side],
        row=model.row
    )


def model_to_product(model: domain.ProductModel) -> domain.Product:
    return domain.Product(
        id=model.id,
        name=model.name,
        volume=model.volume,
        location=model_to_location(model.location)
    )


def model_to_solution(model: domain.OrderPickingSolutionModel) -> domain.OrderPickingSolution:
    """Convert API model to domain object."""
    # First pass: create all products and orders without cross-references
    products: Dict[str, domain.Product] = {}
    orders: Dict[str, domain.Order] = {}

    # Extract unique products and orders from trolley steps
    for step_model in model.trolley_steps:
        item_model = step_model.order_item
        product_model = item_model.product

        # Create product if not seen
        if product_model.id not in products:
            products[product_model.id] = model_to_product(product_model)

        # Create order if not seen
        order_id = item_model.order_id
        if order_id and order_id not in orders:
            orders[order_id] = domain.Order(id=order_id, items=[])

    # Second pass: create order items and trolley steps
    trolley_steps = []
    step_lookup: Dict[str, domain.TrolleyStep] = {}

    for step_model in model.trolley_steps:
        item_model = step_model.order_item
        product = products[item_model.product.id]
        order = orders.get(item_model.order_id) if item_model.order_id else None

        order_item = domain.OrderItem(
            id=item_model.id,
            order=order,
            product=product
        )

        # Add item to order's item list
        if order:
            order.items.append(order_item)

        step = domain.TrolleyStep(
            id=step_model.id,
            order_item=order_item
        )
        trolley_steps.append(step)
        step_lookup[step.id] = step

    # Third pass: create trolleys and set up relationships
    trolleys = []
    trolley_lookup: Dict[str, domain.Trolley] = {}

    for trolley_model in model.trolleys:
        trolley = domain.Trolley(
            id=trolley_model.id,
            bucket_count=trolley_model.bucket_count,
            bucket_capacity=trolley_model.bucket_capacity,
            location=model_to_location(trolley_model.location),
            steps=[]
        )
        trolleys.append(trolley)
        trolley_lookup[trolley.id] = trolley

        # Populate steps list
        for step_ref in trolley_model.steps:
            step_id = step_ref if isinstance(step_ref, str) else step_ref.id
            if step_id in step_lookup:
                step = step_lookup[step_id]
                trolley.steps.append(step)
                # Set shadow variable (for consistency, though solver will reset)
                step.trolley = trolley

    # Set up previous/next step references based on list order
    for trolley in trolleys:
        for i, step in enumerate(trolley.steps):
            step.previous_step = trolley.steps[i - 1] if i > 0 else None
            step.next_step = trolley.steps[i + 1] if i < len(trolley.steps) - 1 else None

    # Handle score
    score = None
    if model.score:
        score = HardSoftDecimalScore.parse(model.score)

    # Handle solver status
    solver_status = SolverStatus.NOT_SOLVING
    if model.solver_status:
        solver_status = SolverStatus[model.solver_status]

    return domain.OrderPickingSolution(
        trolleys=trolleys,
        trolley_steps=trolley_steps,
        score=score,
        solver_status=solver_status
    )
