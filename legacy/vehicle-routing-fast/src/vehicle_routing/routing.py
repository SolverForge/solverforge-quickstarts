"""
Real-world routing service using OSMnx for road network data.

This module provides:
- OSMnxRoutingService: Downloads OSM network, caches locally, computes routes
- DistanceMatrix: Precomputes all pairwise routes with times and geometries
- Haversine fallback when OSMnx is unavailable
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import polyline

if TYPE_CHECKING:
    from .domain import Location

logger = logging.getLogger(__name__)

# Cache directory for OSM network data
CACHE_DIR = Path(__file__).parent.parent.parent / ".osm_cache"


@dataclass
class RouteResult:
    """Result from a routing query."""

    duration_seconds: int
    distance_meters: int
    geometry: Optional[str] = None  # Encoded polyline


@dataclass
class DistanceMatrix:
    """
    Precomputed distance/time matrix for all location pairs.

    Stores RouteResult for each (origin, destination) pair,
    enabling O(1) lookup during solver execution.
    """

    _matrix: dict[tuple[tuple[float, float], tuple[float, float]], RouteResult] = field(
        default_factory=dict
    )

    def _key(
        self, origin: "Location", destination: "Location"
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Create hashable key from two locations."""
        return (
            (origin.latitude, origin.longitude),
            (destination.latitude, destination.longitude),
        )

    def set_route(
        self, origin: "Location", destination: "Location", result: RouteResult
    ) -> None:
        """Store a route result in the matrix."""
        self._matrix[self._key(origin, destination)] = result

    def get_route(
        self, origin: "Location", destination: "Location"
    ) -> Optional[RouteResult]:
        """Get a route result from the matrix."""
        return self._matrix.get(self._key(origin, destination))

    def get_driving_time(self, origin: "Location", destination: "Location") -> int:
        """Get driving time in seconds between two locations."""
        result = self.get_route(origin, destination)
        if result is None:
            # Fallback to haversine if not in matrix
            return _haversine_driving_time(origin, destination)
        return result.duration_seconds

    def get_geometry(
        self, origin: "Location", destination: "Location"
    ) -> Optional[str]:
        """Get encoded polyline geometry for a route segment."""
        result = self.get_route(origin, destination)
        return result.geometry if result else None


def _haversine_driving_time(origin: "Location", destination: "Location") -> int:
    """
    Calculate driving time using haversine formula (fallback).

    Uses 50 km/h average speed assumption.
    """
    if (
        origin.latitude == destination.latitude
        and origin.longitude == destination.longitude
    ):
        return 0

    EARTH_RADIUS_M = 6371000
    AVERAGE_SPEED_KMPH = 50

    lat1 = math.radians(origin.latitude)
    lon1 = math.radians(origin.longitude)
    lat2 = math.radians(destination.latitude)
    lon2 = math.radians(destination.longitude)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    distance_meters = EARTH_RADIUS_M * c

    # Convert to driving time
    return round(distance_meters / AVERAGE_SPEED_KMPH * 3.6)


class OSMnxRoutingService:
    """
    Routing service using OSMnx for real road network data.

    Downloads the OSM network for a given bounding box, caches it locally,
    and computes shortest paths using NetworkX.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._graph = None
        self._graph_bbox = None

    def _get_cache_path(
        self, north: float, south: float, east: float, west: float
    ) -> Path:
        """Generate cache file path for a bounding box."""
        # Round to 2 decimal places for cache key
        key = f"osm_{north:.2f}_{south:.2f}_{east:.2f}_{west:.2f}.graphml"
        return self.cache_dir / key

    def load_network(
        self, north: float, south: float, east: float, west: float, padding: float = 0.01
    ) -> bool:
        """
        Load OSM road network for the given bounding box.

        Args:
            north, south, east, west: Bounding box coordinates
            padding: Extra padding around the bbox (in degrees)

        Returns:
            True if network loaded successfully, False otherwise
        """
        try:
            import osmnx as ox

            # Add padding to ensure we have roads outside the strict bbox
            north += padding
            south -= padding
            east += padding
            west -= padding

            cache_path = self._get_cache_path(north, south, east, west)

            if cache_path.exists() and cache_path.stat().st_size > 0:
                logger.info(f"Loading cached OSM network from {cache_path}")
                self._graph = ox.load_graphml(cache_path)

                # Check if the cached graph already has travel_time
                # (we now save enriched graphs)
                sample_edge = next(iter(self._graph.edges(data=True)), None)
                has_travel_time = sample_edge and "travel_time" in sample_edge[2]

                if not has_travel_time:
                    logger.info("Adding edge speeds and travel times to cached graph...")
                    self._graph = ox.add_edge_speeds(self._graph)
                    self._graph = ox.add_edge_travel_times(self._graph)
                    # Re-save with travel times included
                    ox.save_graphml(self._graph, cache_path)
                    logger.info("Updated cache with travel times")
            else:
                logger.info(
                    f"Downloading OSM network for bbox: N={north:.4f}, S={south:.4f}, E={east:.4f}, W={west:.4f}"
                )
                # OSMnx 2.x uses bbox as tuple: (left, bottom, right, top) = (west, south, east, north)
                bbox_tuple = (west, south, east, north)
                self._graph = ox.graph_from_bbox(
                    bbox=bbox_tuple,
                    network_type="drive",
                    simplify=True,
                )

                # Add edge speeds and travel times BEFORE caching
                logger.info("Computing edge speeds and travel times...")
                self._graph = ox.add_edge_speeds(self._graph)
                self._graph = ox.add_edge_travel_times(self._graph)

                # Save enriched graph to cache
                ox.save_graphml(self._graph, cache_path)
                logger.info(f"Saved enriched OSM network to cache: {cache_path}")

            self._graph_bbox = (north, south, east, west)
            logger.info(
                f"OSM network loaded: {self._graph.number_of_nodes()} nodes, "
                f"{self._graph.number_of_edges()} edges"
            )
            return True

        except ImportError:
            logger.warning("OSMnx not installed, falling back to haversine")
            return False
        except Exception as e:
            logger.warning(f"Failed to load OSM network: {e}, falling back to haversine")
            return False

    def get_nearest_node(self, location: "Location") -> Optional[int]:
        """Get the nearest graph node for a location."""
        if self._graph is None:
            return None
        try:
            import osmnx as ox
            return ox.nearest_nodes(self._graph, location.longitude, location.latitude)
        except Exception:
            return None

    def compute_all_routes(
        self,
        locations: list["Location"],
        progress_callback=None
    ) -> dict[tuple[int, int], RouteResult]:
        """
        Compute all pairwise routes efficiently using batch shortest paths.

        Returns a dict mapping (origin_idx, dest_idx) to RouteResult.
        """
        import networkx as nx

        if self._graph is None:
            return {}

        results = {}
        n = len(locations)

        # Map locations to nearest nodes (batch operation)
        if progress_callback:
            progress_callback("routes", "Finding nearest road nodes...", 30, f"{n} locations")

        nodes = []
        for loc in locations:
            node = self.get_nearest_node(loc)
            nodes.append(node)

        # Compute shortest paths from each origin to ALL destinations at once
        # This is MUCH faster than individual shortest_path calls
        total_origins = sum(1 for node in nodes if node is not None)
        processed = 0

        for i, origin_node in enumerate(nodes):
            if origin_node is None:
                continue

            # Compute shortest paths from this origin to all nodes at once
            # Using Dijkstra's algorithm with single-source
            try:
                lengths, paths = nx.single_source_dijkstra(
                    self._graph, origin_node, weight="travel_time"
                )
            except nx.NetworkXError:
                continue

            for j, dest_node in enumerate(nodes):
                if dest_node is None:
                    continue

                origin_loc = locations[i]
                dest_loc = locations[j]

                if i == j or origin_node == dest_node:
                    # Same location
                    results[(i, j)] = RouteResult(
                        duration_seconds=0,
                        distance_meters=0,
                        geometry=polyline.encode(
                            [(origin_loc.latitude, origin_loc.longitude)], precision=5
                        ),
                    )
                elif dest_node in paths:
                    path = paths[dest_node]
                    travel_time = lengths[dest_node]

                    # Calculate distance and extract geometry
                    total_distance = 0
                    coordinates = []

                    for k in range(len(path) - 1):
                        u, v = path[k], path[k + 1]
                        edge_data = self._graph.get_edge_data(u, v)
                        if edge_data:
                            edge = edge_data[0] if isinstance(edge_data, dict) else edge_data
                            total_distance += edge.get("length", 0)

                    for node in path:
                        node_data = self._graph.nodes[node]
                        coordinates.append((node_data["y"], node_data["x"]))

                    results[(i, j)] = RouteResult(
                        duration_seconds=round(travel_time),
                        distance_meters=round(total_distance),
                        geometry=polyline.encode(coordinates, precision=5),
                    )

            processed += 1
            if progress_callback and processed % max(1, total_origins // 10) == 0:
                percent = 30 + int((processed / total_origins) * 65)
                progress_callback(
                    "routes",
                    "Computing routes...",
                    percent,
                    f"{processed}/{total_origins} origins processed"
                )

        return results

    def get_route(
        self, origin: "Location", destination: "Location"
    ) -> Optional[RouteResult]:
        """
        Compute route between two locations.

        Returns:
            RouteResult with duration, distance, and geometry, or None if routing fails
        """
        if self._graph is None:
            return None

        try:
            import osmnx as ox

            # Find nearest nodes to origin and destination
            origin_node = ox.nearest_nodes(
                self._graph, origin.longitude, origin.latitude
            )
            dest_node = ox.nearest_nodes(
                self._graph, destination.longitude, destination.latitude
            )

            # Same node means same location (or very close)
            if origin_node == dest_node:
                return RouteResult(
                    duration_seconds=0,
                    distance_meters=0,
                    geometry=polyline.encode(
                        [(origin.latitude, origin.longitude)], precision=5
                    ),
                )

            # Compute shortest path by travel time
            route = ox.shortest_path(
                self._graph, origin_node, dest_node, weight="travel_time"
            )

            if route is None:
                logger.warning(
                    f"No route found between {origin} and {destination}"
                )
                return None

            # Extract route attributes
            total_time = 0
            total_distance = 0
            coordinates = []

            for i in range(len(route) - 1):
                u, v = route[i], route[i + 1]
                edge_data = self._graph.get_edge_data(u, v)
                if edge_data:
                    # Get the first edge if multiple exist
                    edge = edge_data[0] if isinstance(edge_data, dict) else edge_data
                    total_time += edge.get("travel_time", 0)
                    total_distance += edge.get("length", 0)

            # Get node coordinates for geometry
            for node in route:
                node_data = self._graph.nodes[node]
                coordinates.append((node_data["y"], node_data["x"]))

            # Encode geometry as polyline
            encoded_geometry = polyline.encode(coordinates, precision=5)

            return RouteResult(
                duration_seconds=round(total_time),
                distance_meters=round(total_distance),
                geometry=encoded_geometry,
            )

        except Exception as e:
            logger.warning(f"Routing failed: {e}")
            return None


def compute_distance_matrix(
    locations: list["Location"],
    routing_service: Optional[OSMnxRoutingService] = None,
    bbox: Optional[tuple[float, float, float, float]] = None,
) -> DistanceMatrix:
    """
    Compute distance matrix for all location pairs.

    Args:
        locations: List of Location objects
        routing_service: Optional pre-configured routing service
        bbox: Optional (north, south, east, west) tuple for network download

    Returns:
        DistanceMatrix with precomputed routes
    """
    return compute_distance_matrix_with_progress(
        locations, routing_service, bbox, use_osm=True, progress_callback=None
    )


def compute_distance_matrix_with_progress(
    locations: list["Location"],
    bbox: Optional[tuple[float, float, float, float]] = None,
    use_osm: bool = True,
    progress_callback=None,
    routing_service: Optional[OSMnxRoutingService] = None,
) -> DistanceMatrix:
    """
    Compute distance matrix for all location pairs with progress reporting.

    Args:
        locations: List of Location objects
        bbox: Optional (north, south, east, west) tuple for network download
        use_osm: If True, try to use OSMnx for real routing. If False, use haversine.
        progress_callback: Optional callback(phase, message, percent, detail) for progress updates
        routing_service: Optional pre-configured routing service

    Returns:
        DistanceMatrix with precomputed routes
    """
    matrix = DistanceMatrix()

    if not locations:
        return matrix

    def report_progress(phase: str, message: str, percent: int, detail: str = ""):
        if progress_callback:
            progress_callback(phase, message, percent, detail)
        logger.info(f"[{phase}] {message} ({percent}%) {detail}")

    # Compute bounding box from locations if not provided
    if bbox is None:
        lats = [loc.latitude for loc in locations]
        lons = [loc.longitude for loc in locations]
        bbox = (max(lats), min(lats), max(lons), min(lons))

    osm_loaded = False

    if use_osm:
        # Create routing service if not provided
        if routing_service is None:
            routing_service = OSMnxRoutingService()

        report_progress("network", "Checking for cached road network...", 5)

        # Check if cached
        north, south, east, west = bbox
        north += 0.01  # padding
        south -= 0.01
        east += 0.01
        west -= 0.01

        cache_path = routing_service._get_cache_path(north, south, east, west)
        is_cached = cache_path.exists()

        if is_cached:
            report_progress("network", "Loading cached road network...", 10, str(cache_path.name))
        else:
            report_progress(
                "network",
                "Downloading OpenStreetMap road network...",
                10,
                f"Area: {abs(north-south):.2f}° × {abs(east-west):.2f}°"
            )

        # Try to load OSM network
        osm_loaded = routing_service.load_network(
            north=bbox[0], south=bbox[1], east=bbox[2], west=bbox[3]
        )

        if osm_loaded:
            node_count = routing_service._graph.number_of_nodes()
            edge_count = routing_service._graph.number_of_edges()
            report_progress(
                "network",
                "Road network loaded",
                25,
                f"{node_count:,} nodes, {edge_count:,} edges"
            )
        else:
            report_progress("network", "OSMnx unavailable, using haversine", 25)
    else:
        report_progress("network", "Using fast haversine mode", 25)

    # Compute all pairwise routes
    total_pairs = len(locations) * len(locations)

    if osm_loaded and routing_service:
        # Use batch routing for OSMnx (MUCH faster than individual calls)
        report_progress(
            "routes",
            f"Computing {total_pairs:,} routes (batch mode)...",
            30,
            f"{len(locations)} locations"
        )

        batch_results = routing_service.compute_all_routes(
            locations,
            progress_callback=report_progress
        )

        # Transfer batch results to matrix, with haversine fallback for missing routes
        computed = 0
        for i, origin in enumerate(locations):
            for j, destination in enumerate(locations):
                if (i, j) in batch_results:
                    matrix.set_route(origin, destination, batch_results[(i, j)])
                else:
                    # Fallback to haversine for routes not found
                    matrix.set_route(
                        origin,
                        destination,
                        RouteResult(
                            duration_seconds=_haversine_driving_time(origin, destination),
                            distance_meters=_haversine_distance_meters(origin, destination),
                            geometry=_straight_line_geometry(origin, destination),
                        ),
                    )
                computed += 1

        report_progress("complete", "Distance matrix ready", 100, f"{computed:,} routes computed")
    else:
        # Use haversine fallback for all routes
        report_progress(
            "routes",
            f"Computing {total_pairs:,} route pairs...",
            30,
            f"{len(locations)} locations"
        )

        computed = 0
        for origin in locations:
            for destination in locations:
                if origin is destination:
                    matrix.set_route(
                        origin,
                        destination,
                        RouteResult(
                            duration_seconds=0,
                            distance_meters=0,
                            geometry=polyline.encode(
                                [(origin.latitude, origin.longitude)], precision=5
                            ),
                        ),
                    )
                else:
                    matrix.set_route(
                        origin,
                        destination,
                        RouteResult(
                            duration_seconds=_haversine_driving_time(origin, destination),
                            distance_meters=_haversine_distance_meters(origin, destination),
                            geometry=_straight_line_geometry(origin, destination),
                        ),
                    )
                computed += 1

                # Report progress every 5%
                if total_pairs > 0 and computed % max(1, total_pairs // 20) == 0:
                    percent_complete = int(30 + (computed / total_pairs) * 65)
                    report_progress(
                        "routes",
                        f"Computing routes...",
                        percent_complete,
                        f"{computed:,}/{total_pairs:,} pairs"
                    )

        report_progress("complete", "Distance matrix ready", 100, f"{computed:,} routes computed")

    return matrix


def _haversine_distance_meters(origin: "Location", destination: "Location") -> int:
    """Calculate haversine distance in meters."""
    if (
        origin.latitude == destination.latitude
        and origin.longitude == destination.longitude
    ):
        return 0

    EARTH_RADIUS_M = 6371000

    lat1 = math.radians(origin.latitude)
    lon1 = math.radians(origin.longitude)
    lat2 = math.radians(destination.latitude)
    lon2 = math.radians(destination.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return round(EARTH_RADIUS_M * c)


def _straight_line_geometry(origin: "Location", destination: "Location") -> str:
    """Generate a straight-line encoded polyline between two points."""
    return polyline.encode(
        [(origin.latitude, origin.longitude), (destination.latitude, destination.longitude)],
        precision=5,
    )
