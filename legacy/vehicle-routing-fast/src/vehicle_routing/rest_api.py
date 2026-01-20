from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from uuid import uuid4
from typing import Dict, List, Optional
from dataclasses import asdict
from enum import Enum
import logging
import json
import asyncio

from .domain import VehicleRoutePlan, Location
from .converters import plan_to_model, model_to_plan
from .domain import VehicleRoutePlanModel
from .score_analysis import ConstraintAnalysisDTO, MatchAnalysisDTO
from .demo_data import generate_demo_data, DemoData
from .solver import solver_manager, solution_manager
from .routing import compute_distance_matrix_with_progress, DistanceMatrix
from pydantic import BaseModel, Field


class RoutingMode(str, Enum):
    """Routing mode for distance calculations."""
    HAVERSINE = "haversine"  # Fast, straight-line estimation
    REAL_ROADS = "real_roads"  # Slower, uses OSMnx for real road routes

logger = logging.getLogger(__name__)

app = FastAPI(docs_url='/q/swagger-ui')

data_sets: Dict[str, VehicleRoutePlan] = {}


# Request/Response models for recommendation endpoints
class VehicleRecommendation(BaseModel):
    """Recommendation for assigning a visit to a vehicle at a specific index."""
    vehicle_id: str = Field(..., alias="vehicleId")
    index: int

    class Config:
        populate_by_name = True


class RecommendedAssignmentResponse(BaseModel):
    """Response from the recommendation API."""
    proposition: VehicleRecommendation
    score_diff: str = Field(..., alias="scoreDiff")

    class Config:
        populate_by_name = True


class RecommendationRequest(BaseModel):
    """Request for visit assignment recommendations."""
    solution: VehicleRoutePlanModel
    visit_id: str = Field(..., alias="visitId")

    class Config:
        populate_by_name = True


class ApplyRecommendationRequest(BaseModel):
    """Request to apply a recommendation."""
    solution: VehicleRoutePlanModel
    visit_id: str = Field(..., alias="visitId")
    vehicle_id: str = Field(..., alias="vehicleId")
    index: int

    class Config:
        populate_by_name = True


def json_to_vehicle_route_plan(json_data: dict) -> VehicleRoutePlan:
    """Convert JSON data to VehicleRoutePlan using the model converters."""
    plan_model = VehicleRoutePlanModel.model_validate(json_data)
    return model_to_plan(plan_model)


@app.get("/demo-data")
async def get_demo_data():
    """Get available demo data sets."""
    return [demo.name for demo in DemoData]

def _extract_all_locations(plan: VehicleRoutePlan) -> list[Location]:
    """Extract all unique locations from a route plan."""
    locations = []
    seen = set()

    for vehicle in plan.vehicles:
        key = (vehicle.home_location.latitude, vehicle.home_location.longitude)
        if key not in seen:
            locations.append(vehicle.home_location)
            seen.add(key)

    for visit in plan.visits:
        key = (visit.location.latitude, visit.location.longitude)
        if key not in seen:
            locations.append(visit.location)
            seen.add(key)

    return locations


def _extract_route_geometries(plan: VehicleRoutePlan) -> Dict[str, List[Optional[str]]]:
    """
    Extract route geometries from the distance matrix for all vehicles.
    Returns empty dict if no distance matrix is available.
    """
    distance_matrix = Location.get_distance_matrix()
    if distance_matrix is None:
        return {}

    geometries: Dict[str, List[Optional[str]]] = {}

    for vehicle in plan.vehicles:
        segments: List[Optional[str]] = []

        if not vehicle.visits:
            geometries[vehicle.id] = segments
            continue

        # Segment from depot to first visit
        prev_location = vehicle.home_location
        for visit in vehicle.visits:
            geometry = distance_matrix.get_geometry(prev_location, visit.location)
            segments.append(geometry)
            prev_location = visit.location

        # Segment from last visit back to depot
        geometry = distance_matrix.get_geometry(prev_location, vehicle.home_location)
        segments.append(geometry)

        geometries[vehicle.id] = segments

    return geometries


def _initialize_distance_matrix(
    plan: VehicleRoutePlan,
    use_real_roads: bool = False,
    progress_callback=None
) -> Optional[DistanceMatrix]:
    """
    Initialize the distance matrix for a route plan.

    Args:
        plan: The route plan with locations
        use_real_roads: If True, use OSMnx for real road routing (slower)
                       If False, use haversine estimation (fast, default)
        progress_callback: Optional callback for progress updates

    Returns the computed matrix, or None if routing failed.
    """
    locations = _extract_all_locations(plan)
    if not locations:
        return None

    logger.info(f"Computing distance matrix for {len(locations)} locations (mode: {'real_roads' if use_real_roads else 'haversine'})...")

    # Compute bounding box from the plan
    bbox = (
        plan.north_east_corner.latitude,
        plan.south_west_corner.latitude,
        plan.north_east_corner.longitude,
        plan.south_west_corner.longitude,
    )

    try:
        matrix = compute_distance_matrix_with_progress(
            locations,
            bbox=bbox,
            use_osm=use_real_roads,
            progress_callback=progress_callback
        )
        Location.set_distance_matrix(matrix)
        logger.info("Distance matrix computed and set successfully")
        return matrix
    except Exception as e:
        logger.warning(f"Failed to compute distance matrix: {e}")
        return None


@app.get("/demo-data/{demo_name}", response_model=VehicleRoutePlanModel)
async def get_demo_data_by_name(
    demo_name: str,
    routing: RoutingMode = Query(
        default=RoutingMode.HAVERSINE,
        description="Routing mode: 'haversine' (fast, default) or 'real_roads' (slower, accurate)"
    )
) -> VehicleRoutePlanModel:
    """
    Get a specific demo data set.

    Args:
        demo_name: Name of the demo dataset (PHILADELPHIA, HARTFORT, FIRENZE)
        routing: Routing mode - 'haversine' (fast default) or 'real_roads' (slower, accurate)

    When routing=real_roads, computes the distance matrix using real road network
    data (OSMnx) for accurate routing. The first call may take 5-15 seconds
    to download the OSM network (cached for subsequent calls).
    """
    try:
        demo_data = DemoData[demo_name]
        domain_plan = generate_demo_data(demo_data)

        # Initialize distance matrix with selected routing mode
        use_real_roads = routing == RoutingMode.REAL_ROADS
        _initialize_distance_matrix(domain_plan, use_real_roads=use_real_roads)

        return plan_to_model(domain_plan)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Demo data '{demo_name}' not found")


# Progress tracking for SSE
_progress_queues: Dict[str, asyncio.Queue] = {}


@app.get("/demo-data/{demo_name}/stream")
async def get_demo_data_with_progress(
    demo_name: str,
    routing: RoutingMode = Query(
        default=RoutingMode.HAVERSINE,
        description="Routing mode: 'haversine' (fast, default) or 'real_roads' (slower, accurate)"
    )
):
    """
    Get demo data with Server-Sent Events (SSE) progress updates.

    This endpoint streams progress updates while computing the distance matrix,
    then returns the final solution. Use this when routing=real_roads and you
    want to show progress to the user.

    Events emitted:
    - progress: {phase, message, percent, detail}
    - complete: {solution: VehicleRoutePlanModel}
    - error: {message}
    """
    async def generate():
        try:
            demo_data = DemoData[demo_name]
            domain_plan = generate_demo_data(demo_data)

            use_real_roads = routing == RoutingMode.REAL_ROADS

            if not use_real_roads:
                # Fast path - no progress needed for haversine
                yield f"data: {json.dumps({'event': 'progress', 'phase': 'computing', 'message': 'Computing distances...', 'percent': 50})}\n\n"
                _initialize_distance_matrix(domain_plan, use_real_roads=False)
                yield f"data: {json.dumps({'event': 'progress', 'phase': 'complete', 'message': 'Ready!', 'percent': 100})}\n\n"
                result = plan_to_model(domain_plan)
                # Include geometries (straight lines in haversine mode)
                geometries = _extract_route_geometries(domain_plan)
                yield f"data: {json.dumps({'event': 'complete', 'solution': result.model_dump(by_alias=True), 'geometries': geometries})}\n\n"
            else:
                # Slow path - stream progress for OSMnx
                progress_events = []

                def progress_callback(phase: str, message: str, percent: int, detail: str = ""):
                    progress_events.append({
                        'event': 'progress',
                        'phase': phase,
                        'message': message,
                        'percent': percent,
                        'detail': detail
                    })

                # Run computation in thread pool to not block
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        _initialize_distance_matrix,
                        domain_plan,
                        use_real_roads=True,
                        progress_callback=progress_callback
                    )

                    # Stream progress events while waiting
                    last_sent = 0
                    while not future.done():
                        await asyncio.sleep(0.1)
                        while last_sent < len(progress_events):
                            yield f"data: {json.dumps(progress_events[last_sent])}\n\n"
                            last_sent += 1

                    # Send any remaining progress events
                    while last_sent < len(progress_events):
                        yield f"data: {json.dumps(progress_events[last_sent])}\n\n"
                        last_sent += 1

                    # Get result (will raise if exception occurred)
                    future.result()

                yield f"data: {json.dumps({'event': 'progress', 'phase': 'complete', 'message': 'Ready!', 'percent': 100})}\n\n"
                result = plan_to_model(domain_plan)

                # Include geometries in response for real roads mode
                geometries = _extract_route_geometries(domain_plan)
                yield f"data: {json.dumps({'event': 'complete', 'solution': result.model_dump(by_alias=True), 'geometries': geometries})}\n\n"

        except KeyError:
            yield f"data: {json.dumps({'event': 'error', 'message': f'Demo data not found: {demo_name}'})}\n\n"
        except Exception as e:
            logger.exception(f"Error in SSE stream: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/route-plans/{problem_id}", response_model=VehicleRoutePlanModel, response_model_exclude_none=True)
async def get_route(problem_id: str) -> VehicleRoutePlanModel:
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")
    route.solver_status = solver_manager.get_solver_status(problem_id)
    return plan_to_model(route)

@app.post("/route-plans")
async def solve_route(plan_model: VehicleRoutePlanModel) -> str:
    job_id = str(uuid4())
    # Convert to domain model for solver
    domain_plan = model_to_plan(plan_model)
    data_sets[job_id] = domain_plan
    solver_manager.solve_and_listen(
        job_id,
        domain_plan,
        lambda solution: data_sets.update({job_id: solution})
    )
    return job_id

@app.put("/route-plans/analyze")
async def analyze_route(plan_model: VehicleRoutePlanModel) -> dict:
    domain_plan = model_to_plan(plan_model)
    analysis = solution_manager.analyze(domain_plan)
    constraints = []
    for constraint in getattr(analysis, 'constraint_analyses', []) or []:
        matches = [
            MatchAnalysisDTO(
                name=str(getattr(getattr(match, 'constraint_ref', None), 'constraint_name', "")),
                score=str(getattr(match, 'score', "0hard/0soft")),
                justification=str(getattr(match, 'justification', ""))
            )
            for match in getattr(constraint, 'matches', []) or []
        ]
        constraints.append(ConstraintAnalysisDTO(
            name=str(getattr(constraint, 'constraint_name', "")),
            weight=str(getattr(constraint, 'weight', "0hard/0soft")),
            score=str(getattr(constraint, 'score', "0hard/0soft")),
            matches=matches
        ))
    return {"constraints": [asdict(constraint) for constraint in constraints]}

@app.get("/route-plans")
async def list_route_plans() -> List[str]:
    """List the job IDs of all submitted route plans."""
    return list(data_sets.keys())


@app.get("/route-plans/{problem_id}/status")
async def get_route_status(problem_id: str) -> dict:
    """Get the route plan status and score for a given job ID."""
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")
    solver_status = solver_manager.get_solver_status(problem_id)
    return {
        "name": route.name,
        "score": str(route.score) if route.score else None,
        "solverStatus": solver_status.name if solver_status else None,
    }


@app.delete("/route-plans/{problem_id}")
async def stop_solving(problem_id: str) -> VehicleRoutePlanModel:
    """Terminate solving for a given job ID. Returns the best solution so far."""
    solver_manager.terminate_early(problem_id)
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")
    route.solver_status = solver_manager.get_solver_status(problem_id)
    return plan_to_model(route)


@app.post("/route-plans/recommendation")
async def recommend_assignment(request: RecommendationRequest) -> List[RecommendedAssignmentResponse]:
    """
    Request recommendations for assigning a visit to vehicles.

    Returns a list of recommended assignments sorted by score impact.
    """
    domain_plan = model_to_plan(request.solution)

    # Find the visit by ID
    visit = None
    for v in domain_plan.visits:
        if v.id == request.visit_id:
            visit = v
            break

    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit {request.visit_id} not found")

    # Get recommendations using solution_manager
    try:
        recommendations = solution_manager.recommend_assignment(
            domain_plan,
            visit,
            lambda v: VehicleRecommendation(vehicle_id=v.vehicle.id, index=v.vehicle.visits.index(v))
        )

        # Convert to response format (limit to top 5)
        result = []
        for rec in recommendations[:5]:
            result.append(RecommendedAssignmentResponse(
                proposition=rec.proposition,
                score_diff=str(rec.score_diff) if hasattr(rec, 'score_diff') else "0hard/0soft"
            ))
        return result
    except Exception:
        # If recommend_assignment is not available, return empty list
        return []


@app.post("/route-plans/recommendation/apply")
async def apply_recommendation(request: ApplyRecommendationRequest) -> VehicleRoutePlanModel:
    """
    Apply a recommendation to assign a visit to a vehicle at a specific index.

    Returns the updated solution.
    """
    domain_plan = model_to_plan(request.solution)

    # Find the vehicle by ID
    vehicle = None
    for v in domain_plan.vehicles:
        if v.id == request.vehicle_id:
            vehicle = v
            break

    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle {request.vehicle_id} not found")

    # Find the visit by ID
    visit = None
    for v in domain_plan.visits:
        if v.id == request.visit_id:
            visit = v
            break

    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit {request.visit_id} not found")

    # Insert visit at the specified index
    vehicle.visits.insert(request.index, visit)

    # Update the solution to recalculate shadow variables
    solution_manager.update(domain_plan)

    return plan_to_model(domain_plan)


class RouteGeometryResponse(BaseModel):
    """Response containing encoded polyline geometries for all vehicle routes."""
    geometries: Dict[str, List[Optional[str]]]


@app.get("/route-plans/{problem_id}/geometry", response_model=RouteGeometryResponse)
async def get_route_geometry(problem_id: str) -> RouteGeometryResponse:
    """
    Get route geometries for all vehicle routes in a problem.

    Returns encoded polylines (Google polyline format) for each route segment.
    Each vehicle's route is represented as a list of encoded polylines:
    - First segment: depot -> first visit
    - Middle segments: visit -> visit
    - Last segment: last visit -> depot

    These can be decoded on the frontend to display actual road routes
    instead of straight lines.
    """
    route = data_sets.get(problem_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route plan not found")

    distance_matrix = Location.get_distance_matrix()
    if distance_matrix is None:
        # No distance matrix available - return empty geometries
        return RouteGeometryResponse(geometries={})

    geometries: Dict[str, List[Optional[str]]] = {}

    for vehicle in route.vehicles:
        segments: List[Optional[str]] = []

        if not vehicle.visits:
            # No visits assigned to this vehicle
            geometries[vehicle.id] = segments
            continue

        # Segment from depot to first visit
        prev_location = vehicle.home_location
        for visit in vehicle.visits:
            geometry = distance_matrix.get_geometry(prev_location, visit.location)
            segments.append(geometry)
            prev_location = visit.location

        # Segment from last visit back to depot
        geometry = distance_matrix.get_geometry(prev_location, vehicle.home_location)
        segments.append(geometry)

        geometries[vehicle.id] = segments

    return RouteGeometryResponse(geometries=geometries)


@app.get("/healthz")
async def healthz():
    return {"status": "UP"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
