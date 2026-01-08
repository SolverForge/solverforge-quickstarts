//! Domain model for Vehicle Routing Problem.
//!
//! # Overview
//!
//! Models a vehicle routing problem with:
//! - Geographic [`Location`]s with haversine distance calculation
//! - Customer [`Visit`]s with time windows, demand, and service duration
//! - [`Vehicle`]s with capacity constraints and routes
//! - [`VehicleRoutePlan`] as the complete planning solution
//!
//! # Design
//!
//! All scoring uses direct access to the plan's travel time matrix.
//! No global state or RwLock overhead.

use serde::{Deserialize, Serialize};
use solverforge::prelude::*;
use solverforge::ListPositionDistanceMeter;
use std::collections::HashMap;

/// Average driving speed in km/h for travel time estimation.
pub const AVERAGE_SPEED_KMPH: f64 = 50.0;

/// Earth radius in meters for haversine calculation.
const EARTH_RADIUS_M: f64 = 6_371_000.0;

/// A geographic location with latitude and longitude.
///
/// Supports haversine distance calculation for travel time estimation.
///
/// # Examples
///
/// ```
/// use vehicle_routing::domain::Location;
///
/// let philadelphia = Location::new(0, 39.9526, -75.1652);
/// let new_york = Location::new(1, 40.7128, -74.0060);
///
/// // Distance is approximately 130 km
/// let distance = philadelphia.distance_meters(&new_york);
/// assert!(distance > 120_000.0 && distance < 140_000.0);
///
/// // Travel time at 50 km/h is approximately 2.6 hours
/// let travel_secs = philadelphia.travel_time_seconds(&new_york);
/// assert!(travel_secs > 8000 && travel_secs < 10000);
/// ```
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Location {
    /// Index in `VehicleRoutePlan.locations`.
    pub index: usize,
    /// Latitude in degrees (-90 to 90).
    pub latitude: f64,
    /// Longitude in degrees (-180 to 180).
    pub longitude: f64,
}

impl PartialEq for Location {
    fn eq(&self, other: &Self) -> bool {
        self.index == other.index
    }
}

impl Eq for Location {}

impl std::hash::Hash for Location {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.index.hash(state);
    }
}

impl Location {
    /// Creates a new location.
    pub fn new(index: usize, latitude: f64, longitude: f64) -> Self {
        Self {
            index,
            latitude,
            longitude,
        }
    }

    /// Calculates the great-circle distance in meters using the haversine formula.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::Location;
    ///
    /// let a = Location::new(0, 0.0, 0.0);
    /// let b = Location::new(1, 0.0, 1.0);
    ///
    /// // 1 degree of longitude at equator is about 111 km
    /// let dist = a.distance_meters(&b);
    /// assert!(dist > 110_000.0 && dist < 112_000.0);
    /// ```
    pub fn distance_meters(&self, other: &Location) -> f64 {
        if self.latitude == other.latitude && self.longitude == other.longitude {
            return 0.0;
        }

        let lat1 = self.latitude.to_radians();
        let lat2 = other.latitude.to_radians();
        let lon1 = self.longitude.to_radians();
        let lon2 = other.longitude.to_radians();

        // Haversine formula
        let dlat = lat2 - lat1;
        let dlon = lon2 - lon1;
        let a = (dlat / 2.0).sin().powi(2) + lat1.cos() * lat2.cos() * (dlon / 2.0).sin().powi(2);
        let c = 2.0 * a.sqrt().asin();

        EARTH_RADIUS_M * c
    }

    /// Calculates travel time in seconds assuming average driving speed.
    ///
    /// Uses [`AVERAGE_SPEED_KMPH`] (50 km/h) for conversion.
    pub fn travel_time_seconds(&self, other: &Location) -> i64 {
        let meters = self.distance_meters(other);
        // seconds = meters / (km/h * 1000 / 3600) = meters * 3.6 / km/h
        (meters * 3.6 / AVERAGE_SPEED_KMPH).round() as i64
    }

}

/// A customer visit with time window and demand constraints.
///
/// # Time Window
///
/// - `min_start_time`: Earliest time service can begin (vehicle may wait)
/// - `max_end_time`: Latest time service must finish (hard constraint)
/// - `service_duration`: Time required to complete the visit
///
/// All times are in seconds from midnight.
///
/// # Examples
///
/// ```
/// use vehicle_routing::domain::{Visit, Location};
///
/// let location = Location::new(0, 39.95, -75.17);
///
/// // A restaurant delivery: 6am-10am window, 5-minute service
/// let visit = Visit::new(0, "Restaurant A", location)
///     .with_demand(8)
///     .with_time_window(6 * 3600, 10 * 3600)
///     .with_service_duration(300);
///
/// assert_eq!(visit.demand, 8);
/// assert_eq!(visit.min_start_time, 21600); // 6 * 3600
/// ```
#[planning_entity]
#[derive(Serialize, Deserialize)]
pub struct Visit {
    /// Index in `VehicleRoutePlan.visits`.
    #[planning_id]
    pub index: usize,
    /// Customer name.
    pub name: String,
    /// The geographic location of this visit.
    pub location: Location,
    /// Quantity demanded (must fit in vehicle capacity).
    pub demand: i32,
    /// Earliest service start time (seconds from midnight).
    #[serde(rename = "minStartTime")]
    pub min_start_time: i64,
    /// Latest service end time (seconds from midnight).
    #[serde(rename = "maxEndTime")]
    pub max_end_time: i64,
    /// Service duration in seconds.
    #[serde(rename = "serviceDuration")]
    pub service_duration: i64,

    // =========================================================================
    // Shadow Variables (auto-maintained by ShadowVariableSupport)
    // =========================================================================

    /// Index of the vehicle this visit is assigned to (shadow variable).
    /// Updated by `update_shadows()` when visits list changes.
    #[serde(skip)]
    pub vehicle_idx: Option<usize>,

    /// Index of the previous visit in the route (shadow variable).
    /// `None` if this is the first visit or unassigned.
    #[serde(skip)]
    pub previous_visit_idx: Option<usize>,

    /// Computed arrival time at this visit in seconds from midnight (shadow variable).
    /// Cascading update: depends on previous_visit_idx and vehicle departure.
    #[serde(skip)]
    pub arrival_time: Option<i64>,
}

impl Visit {
    /// Creates a new visit with default time window (all day).
    pub fn new(index: usize, name: impl Into<String>, location: Location) -> Self {
        Self {
            index,
            name: name.into(),
            location,
            demand: 1,
            min_start_time: 0,
            max_end_time: 24 * 3600,
            service_duration: 0,
            vehicle_idx: None,
            previous_visit_idx: None,
            arrival_time: None,
        }
    }

    /// Sets the demand.
    pub fn with_demand(mut self, demand: i32) -> Self {
        self.demand = demand;
        self
    }

    /// Sets the time window (min_start_time, max_end_time) in seconds from midnight.
    pub fn with_time_window(mut self, min_start: i64, max_end: i64) -> Self {
        self.min_start_time = min_start;
        self.max_end_time = max_end;
        self
    }

    /// Sets the service duration in seconds.
    pub fn with_service_duration(mut self, duration: i64) -> Self {
        self.service_duration = duration;
        self
    }

    /// Returns true if service finishes after max_end_time.
    ///
    /// Uses the arrival_time shadow variable for O(1) evaluation.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Visit, Location};
    ///
    /// let loc = Location::new(0, 0.0, 0.0);
    /// let mut visit = Visit::new(0, "A", loc)
    ///     .with_time_window(8 * 3600, 9 * 3600)  // 8am-9am window
    ///     .with_service_duration(1800);          // 30 min service
    ///
    /// // Arrives at 8:45am, service ends at 9:15am (late by 15 min)
    /// visit.arrival_time = Some(8 * 3600 + 45 * 60);
    /// assert!(visit.is_late());
    ///
    /// // Arrives at 8:00am, service ends at 8:30am (on time)
    /// visit.arrival_time = Some(8 * 3600);
    /// assert!(!visit.is_late());
    /// ```
    #[inline]
    pub fn is_late(&self) -> bool {
        self.arrival_time.map_or(false, |arrival| {
            let service_start = arrival.max(self.min_start_time);
            let service_end = service_start + self.service_duration;
            service_end > self.max_end_time
        })
    }

    /// Returns delay in minutes if service finishes late, 0 otherwise.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Visit, Location};
    ///
    /// let loc = Location::new(0, 0.0, 0.0);
    /// let mut visit = Visit::new(0, "A", loc)
    ///     .with_time_window(8 * 3600, 9 * 3600)  // 8am-9am window
    ///     .with_service_duration(1800);          // 30 min service
    ///
    /// // Arrives at 8:45am, service ends at 9:15am (late by 15 min)
    /// visit.arrival_time = Some(8 * 3600 + 45 * 60);
    /// assert_eq!(visit.late_minutes(), 15);
    ///
    /// // Arrives at 8:00am, on time
    /// visit.arrival_time = Some(8 * 3600);
    /// assert_eq!(visit.late_minutes(), 0);
    /// ```
    #[inline]
    pub fn late_minutes(&self) -> i64 {
        self.arrival_time.map_or(0, |arrival| {
            let service_start = arrival.max(self.min_start_time);
            let service_end = service_start + self.service_duration;
            let delay_seconds = (service_end - self.max_end_time).max(0);
            (delay_seconds + 59) / 60  // Round up to minutes
        })
    }
}

/// A delivery vehicle with capacity and assigned route.
///
/// The route is stored as a list of visit indices in order.
///
/// # Examples
///
/// ```
/// use vehicle_routing::domain::{Vehicle, Location};
///
/// let depot = Location::new(0, 39.95, -75.17);
/// let vehicle = Vehicle::new(0, "Truck 1", 100, depot)
///     .with_departure_time(8 * 3600);  // Departs at 8am
///
/// assert_eq!(vehicle.capacity, 100);
/// assert!(vehicle.visits.is_empty());
/// ```
#[planning_entity]
#[derive(Serialize, Deserialize)]
pub struct Vehicle {
    /// Unique vehicle ID.
    #[planning_id]
    pub id: usize,
    /// Vehicle name for display.
    pub name: String,
    /// Maximum capacity (sum of visit demands must not exceed).
    pub capacity: i32,
    /// Home depot location.
    #[serde(rename = "homeLocation")]
    pub home_location: Location,
    /// Departure time from depot (seconds from midnight).
    #[serde(rename = "departureTime")]
    pub departure_time: i64,
    /// Ordered list of visit indices (the route).
    #[planning_list_variable]
    #[serde(default)]
    pub visits: Vec<usize>,

    // =========================================================================
    // Cached Aggregates (updated by ShadowVariableSupport)
    // =========================================================================

    /// Cached sum of demands for all visits in route.
    #[serde(skip)]
    pub cached_total_demand: i32,

    /// Cached total driving time in seconds.
    #[serde(skip)]
    pub cached_driving_time: i64,

    /// Cached total late minutes for all visits in route.
    #[serde(skip)]
    pub cached_late_minutes: i64,
}

impl Vehicle {
    /// Creates a new vehicle with empty route.
    pub fn new(id: usize, name: impl Into<String>, capacity: i32, home_location: Location) -> Self {
        Self {
            id,
            name: name.into(),
            capacity,
            home_location,
            departure_time: 8 * 3600, // Default 8am
            visits: Vec::new(),
            cached_total_demand: 0,
            cached_driving_time: 0,
            cached_late_minutes: 0,
        }
    }

    /// Sets the departure time in seconds from midnight.
    pub fn with_departure_time(mut self, time: i64) -> Self {
        self.departure_time = time;
        self
    }

    /// Returns cached total demand for all visits in route.
    ///
    /// O(1) access to pre-computed value.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Vehicle, Location};
    ///
    /// let depot = Location::new(0, 0.0, 0.0);
    /// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
    /// vehicle.cached_total_demand = 75;
    ///
    /// assert_eq!(vehicle.total_demand(), 75);
    /// ```
    #[inline]
    pub fn total_demand(&self) -> i32 {
        self.cached_total_demand
    }

    /// Returns excess demand (amount over capacity), 0 if under capacity.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Vehicle, Location};
    ///
    /// let depot = Location::new(0, 0.0, 0.0);
    /// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
    ///
    /// // Under capacity
    /// vehicle.cached_total_demand = 80;
    /// assert_eq!(vehicle.excess_demand(), 0);
    ///
    /// // Over capacity
    /// vehicle.cached_total_demand = 120;
    /// assert_eq!(vehicle.excess_demand(), 20);
    /// ```
    #[inline]
    pub fn excess_demand(&self) -> i32 {
        (self.cached_total_demand - self.capacity).max(0)
    }

    /// Returns cached driving time in minutes.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Vehicle, Location};
    ///
    /// let depot = Location::new(0, 0.0, 0.0);
    /// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
    /// vehicle.cached_driving_time = 7200; // 2 hours in seconds
    ///
    /// assert_eq!(vehicle.driving_time_minutes(), 120);
    /// ```
    #[inline]
    pub fn driving_time_minutes(&self) -> i64 {
        self.cached_driving_time / 60
    }

    /// Returns cached total late minutes for all visits in this vehicle's route.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Vehicle, Location};
    ///
    /// let depot = Location::new(0, 0.0, 0.0);
    /// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
    /// vehicle.cached_late_minutes = 45;
    ///
    /// assert_eq!(vehicle.late_minutes(), 45);
    /// ```
    #[inline]
    pub fn late_minutes(&self) -> i64 {
        self.cached_late_minutes
    }
}

/// Arrival and departure times for a visit in a route.
#[derive(Debug, Clone, Copy)]
pub struct VisitTiming {
    /// Visit index.
    pub visit_idx: usize,
    /// Arrival time at the visit (seconds from midnight).
    pub arrival: i64,
    /// Departure time from the visit (seconds from midnight).
    pub departure: i64,
}

/// The complete vehicle routing solution.
///
/// Contains all problem facts (locations, visits) and planning entities (vehicles).
/// Call `finalize()` after construction to populate the travel time matrix.
///
/// # Examples
///
/// ```
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
///
/// let depot = Location::new(0, 39.95, -75.17);  // Philadelphia
/// let customer_loc = Location::new(1, 40.00, -75.10);
///
/// let locations = vec![depot.clone(), customer_loc.clone()];
/// let visits = vec![
///     Visit::new(0, "Customer 1", customer_loc).with_demand(5),
/// ];
/// let vehicles = vec![
///     Vehicle::new(0, "Truck 1", 100, depot),
/// ];
///
/// let mut plan = VehicleRoutePlan::new("Philadelphia", locations, visits, vehicles);
/// plan.finalize();
///
/// // Travel time matrix is now populated
/// assert!(plan.travel_time(0, 1) > 0);
/// ```
#[planning_solution]
#[shadow_variable_updates(
    list_owner = "vehicles",
    list_field = "visits",
    element_collection = "visits",
    element_type = "usize",
    inverse_field = "vehicle_idx",
    previous_field = "previous_visit_idx",
    cascading_listener = "update_visit_arrival_time",
    post_update_listener = "update_vehicle_caches"
)]
#[derive(Serialize, Deserialize)]
pub struct VehicleRoutePlan {
    /// Problem name.
    pub name: String,
    /// South-west corner of bounding box (for map display).
    #[serde(rename = "southWestCorner")]
    pub south_west_corner: [f64; 2],
    /// North-east corner of bounding box (for map display).
    #[serde(rename = "northEastCorner")]
    pub north_east_corner: [f64; 2],
    /// All locations (depot and customer locations).
    #[problem_fact_collection]
    pub locations: Vec<Location>,
    /// All customer visits.
    #[planning_entity_collection]
    pub visits: Vec<Visit>,
    /// All vehicles.
    #[planning_entity_collection]
    pub vehicles: Vec<Vehicle>,
    /// Current score.
    #[planning_score]
    pub score: Option<HardSoftScore>,
    /// Solver status for REST API.
    #[serde(rename = "solverStatus", skip_serializing_if = "Option::is_none")]
    pub solver_status: Option<String>,
    /// Precomputed travel times: `travel_time_matrix[from][to]` in seconds.
    #[serde(skip)]
    pub travel_time_matrix: Vec<Vec<i64>>,
    /// Route geometries: `(from_loc, to_loc)` -> list of (lat, lng) waypoints.
    #[serde(skip)]
    pub route_geometries: HashMap<(usize, usize), Vec<(f64, f64)>>,
}

impl VehicleRoutePlan {
    /// Creates a new vehicle route plan.
    pub fn new(
        name: impl Into<String>,
        locations: Vec<Location>,
        visits: Vec<Visit>,
        vehicles: Vec<Vehicle>,
    ) -> Self {
        // Compute bounding box from locations
        let (sw, ne) = Self::compute_bounds(&locations);

        Self {
            name: name.into(),
            south_west_corner: sw,
            north_east_corner: ne,
            locations,
            visits,
            vehicles,
            score: None,
            solver_status: None,
            travel_time_matrix: Vec::new(),
            route_geometries: HashMap::new(),
        }
    }

    /// Computes bounding box from locations.
    fn compute_bounds(locations: &[Location]) -> ([f64; 2], [f64; 2]) {
        if locations.is_empty() {
            return ([0.0, 0.0], [0.0, 0.0]);
        }

        let mut min_lat = f64::MAX;
        let mut max_lat = f64::MIN;
        let mut min_lon = f64::MAX;
        let mut max_lon = f64::MIN;

        for loc in locations {
            min_lat = min_lat.min(loc.latitude);
            max_lat = max_lat.max(loc.latitude);
            min_lon = min_lon.min(loc.longitude);
            max_lon = max_lon.max(loc.longitude);
        }

        // No padding here - init_routing() adds expansion
        ([min_lat, min_lon], [max_lat, max_lon])
    }

    /// Populates travel time matrix using haversine distances.
    ///
    /// Must be called after construction and before solving.
    /// For real road routing, use `init_routing()` instead.
    pub fn finalize(&mut self) {
        let n = self.locations.len();
        self.travel_time_matrix = vec![vec![0; n]; n];

        for i in 0..n {
            for j in 0..n {
                if i != j {
                    self.travel_time_matrix[i][j] =
                        self.locations[i].travel_time_seconds(&self.locations[j]);
                }
            }
        }
    }

    /// Initializes with real road routing from OSM data.
    ///
    /// Downloads road network via Overpass API (cached), builds graph,
    /// and computes travel times using Dijkstra shortest paths.
    /// Also stores route geometries for visualization.
    pub async fn init_routing(&mut self) -> Result<(), crate::routing::RoutingError> {
        use crate::routing::{BoundingBox, RoadNetwork};

        // Build bounding box from plan bounds (with expansion)
        let bbox = BoundingBox::new(
            self.south_west_corner[0],
            self.south_west_corner[1],
            self.north_east_corner[0],
            self.north_east_corner[1],
        )
        .expand(0.05); // 5% expansion to catch nearby roads

        // Load or fetch road network
        let network = RoadNetwork::load_or_fetch(&bbox).await?;

        // Extract coordinates
        let coords: Vec<(f64, f64)> = self
            .locations
            .iter()
            .map(|l| (l.latitude, l.longitude))
            .collect();

        // Compute travel time matrix
        self.travel_time_matrix = network.compute_matrix(&coords);

        // Compute route geometries for visualization
        self.route_geometries = network.compute_all_geometries(&coords);

        Ok(())
    }

    /// Returns the bounding box for this plan.
    pub fn bounding_box(&self) -> crate::routing::BoundingBox {
        crate::routing::BoundingBox::new(
            self.south_west_corner[0],
            self.south_west_corner[1],
            self.north_east_corner[0],
            self.north_east_corner[1],
        )
    }

    /// Gets travel time between two locations in seconds.
    ///
    /// Returns 0 if indices are out of bounds or matrix not initialized.
    #[inline]
    pub fn travel_time(&self, from_idx: usize, to_idx: usize) -> i64 {
        self.travel_time_matrix
            .get(from_idx)
            .and_then(|row| row.get(to_idx))
            .copied()
            .unwrap_or(0)
    }

    /// Gets route geometry between two locations.
    ///
    /// Returns the waypoints if real road routing was initialized,
    /// or `None` if using haversine fallback.
    #[inline]
    pub fn route_geometry(&self, from_idx: usize, to_idx: usize) -> Option<&[(f64, f64)]> {
        self.route_geometries.get(&(from_idx, to_idx)).map(|v| v.as_slice())
    }

    /// Gets a location by index.
    #[inline]
    pub fn get_location(&self, idx: usize) -> Option<&Location> {
        self.locations.get(idx)
    }

    /// Gets a visit by index.
    #[inline]
    pub fn get_visit(&self, idx: usize) -> Option<&Visit> {
        self.visits.get(idx)
    }

    /// Calculates arrival and departure times for each visit in a vehicle's route.
    ///
    /// Returns a vector of [`VisitTiming`] in route order.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
    ///
    /// let depot = Location::new(0, 0.0, 0.0);
    /// let customer_loc = Location::new(1, 0.0, 0.01); // ~1.1 km away
    ///
    /// let locations = vec![depot.clone(), customer_loc.clone()];
    /// let visits = vec![
    ///     Visit::new(0, "A", customer_loc)
    ///         .with_service_duration(300)
    ///         .with_time_window(0, 86400),
    /// ];
    /// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
    /// vehicle.departure_time = 8 * 3600; // 8am
    /// vehicle.visits = vec![0];
    ///
    /// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle]);
    /// plan.finalize();
    ///
    /// let timings = plan.calculate_route_times(&plan.vehicles[0]);
    /// assert_eq!(timings.len(), 1);
    /// assert!(timings[0].arrival > 8 * 3600); // Arrives after departure
    /// assert_eq!(timings[0].departure, timings[0].arrival + 300); // Service takes 5 min
    /// ```
    pub fn calculate_route_times(&self, vehicle: &Vehicle) -> Vec<VisitTiming> {
        let mut timings = Vec::with_capacity(vehicle.visits.len());
        let mut current_time = vehicle.departure_time;
        let mut current_loc = vehicle.home_location.index;

        for &visit_idx in &vehicle.visits {
            let Some(visit) = self.visits.get(visit_idx) else {
                continue;
            };

            // Travel to this visit
            let travel = self.travel_time(current_loc, visit.location.index);
            let arrival = current_time + travel;

            // Service starts at max(arrival, min_start_time)
            let service_start = arrival.max(visit.min_start_time);
            let departure = service_start + visit.service_duration;

            timings.push(VisitTiming {
                visit_idx,
                arrival,
                departure,
            });

            current_time = departure;
            current_loc = visit.location.index;
        }

        timings
    }

    /// Calculates total driving time for a vehicle's route in seconds.
    ///
    /// Includes travel from depot, between visits, and back to depot.
    pub fn total_driving_time(&self, vehicle: &Vehicle) -> i64 {
        if vehicle.visits.is_empty() {
            return 0;
        }

        let mut total = 0i64;
        let mut current_loc = vehicle.home_location.index;

        for &visit_idx in &vehicle.visits {
            if let Some(visit) = self.visits.get(visit_idx) {
                total += self.travel_time(current_loc, visit.location.index);
                current_loc = visit.location.index;
            }
        }

        // Return to depot
        total += self.travel_time(current_loc, vehicle.home_location.index);
        total
    }

    /// Calculates total driving time across all vehicles.
    pub fn total_driving_time_all(&self) -> i64 {
        self.vehicles.iter().map(|v| self.total_driving_time(v)).sum()
    }

    /// Updates all shadow variables and cached aggregates.
    ///
    /// Call this after modifying vehicle routes to maintain consistency.
    /// Updates: vehicle_idx, previous_visit_idx, arrival_time on visits;
    /// cached_total_demand, cached_driving_time on vehicles.
    ///
    /// # Examples
    ///
    /// ```
    /// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
    ///
    /// let depot = Location::new(0, 0.0, 0.0);
    /// let loc1 = Location::new(1, 0.0, 0.01);
    /// let loc2 = Location::new(2, 0.0, 0.02);
    ///
    /// let locations = vec![depot.clone(), loc1.clone(), loc2.clone()];
    /// let visits = vec![
    ///     Visit::new(0, "A", loc1).with_demand(10),
    ///     Visit::new(1, "B", loc2).with_demand(20),
    /// ];
    /// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
    /// vehicle.departure_time = 8 * 3600;
    /// vehicle.visits = vec![0, 1];  // A -> B
    ///
    /// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle]);
    /// plan.finalize();
    /// plan.update_shadows();
    ///
    /// // Check shadow variables on visits
    /// assert_eq!(plan.visits[0].vehicle_idx, Some(0));
    /// assert_eq!(plan.visits[0].previous_visit_idx, None);  // First in route
    /// assert!(plan.visits[0].arrival_time.is_some());
    ///
    /// assert_eq!(plan.visits[1].vehicle_idx, Some(0));
    /// assert_eq!(plan.visits[1].previous_visit_idx, Some(0));  // After visit 0
    ///
    /// // Check cached aggregates on vehicle
    /// assert_eq!(plan.vehicles[0].cached_total_demand, 30);  // 10 + 20
    /// assert!(plan.vehicles[0].cached_driving_time > 0);
    /// ```
    pub fn update_shadows(&mut self) {
        // Phase 1: Clear all shadow variables
        for visit in &mut self.visits {
            visit.vehicle_idx = None;
            visit.previous_visit_idx = None;
            visit.arrival_time = None;
        }

        // Phase 2: Update each vehicle's route
        for vehicle_idx in 0..self.vehicles.len() {
            self.update_vehicle_shadows(vehicle_idx);
        }
    }

    /// Cascading shadow variable update: calculates arrival time for a visit.
    ///
    /// Called by the macro-generated `update_entity_shadows` after inverse and
    /// previous element shadows are set. Uses the previous visit's departure time
    /// to calculate this visit's arrival time.
    ///
    /// This method is called in list order, so previous visits are already updated.
    pub fn update_visit_arrival_time(&mut self, visit_idx: usize) {
        if visit_idx >= self.visits.len() {
            return;
        }

        let vehicle_idx = match self.visits[visit_idx].vehicle_idx {
            Some(idx) => idx,
            None => return, // Not assigned
        };

        let prev_visit_idx = self.visits[visit_idx].previous_visit_idx;

        // Get departure location and time
        let (prev_loc_idx, prev_departure) = if let Some(prev_idx) = prev_visit_idx {
            let prev_visit = &self.visits[prev_idx];
            let arrival = prev_visit.arrival_time.unwrap_or(0);
            let service_start = arrival.max(prev_visit.min_start_time);
            let departure = service_start + prev_visit.service_duration;
            (prev_visit.location.index, departure)
        } else {
            // First visit - depart from depot
            let vehicle = &self.vehicles[vehicle_idx];
            (vehicle.home_location.index, vehicle.departure_time)
        };

        // Calculate arrival time
        let visit_loc_idx = self.visits[visit_idx].location.index;
        let travel = self.travel_time(prev_loc_idx, visit_loc_idx);
        let arrival = prev_departure + travel;

        self.visits[visit_idx].arrival_time = Some(arrival);
    }

    /// Post-update listener: updates vehicle cached aggregates after shadow variables.
    ///
    /// Called by the macro-generated `update_entity_shadows` after all element
    /// shadows are updated. Recomputes cached_total_demand, cached_driving_time,
    /// and cached_late_minutes.
    pub fn update_vehicle_caches(&mut self, vehicle_idx: usize) {
        if vehicle_idx >= self.vehicles.len() {
            return;
        }

        // Compute total demand
        let total_demand: i32 = self.vehicles[vehicle_idx]
            .visits
            .iter()
            .filter_map(|&idx| self.visits.get(idx))
            .map(|v| v.demand)
            .sum();

        // Compute total driving time
        let driving_time = self.total_driving_time(&self.vehicles[vehicle_idx]);

        // Compute total late minutes
        let late_minutes: i64 = self.vehicles[vehicle_idx]
            .visits
            .iter()
            .filter_map(|&idx| self.visits.get(idx))
            .map(|v| v.late_minutes())
            .sum();

        // Update cached values
        let vehicle = &mut self.vehicles[vehicle_idx];
        vehicle.cached_total_demand = total_demand;
        vehicle.cached_driving_time = driving_time;
        vehicle.cached_late_minutes = late_minutes;
    }

    /// Updates shadow variables for a single vehicle.
    ///
    /// Recomputes: vehicle_idx, previous_visit_idx, arrival_time for visits
    /// in this vehicle's route; cached_total_demand, cached_driving_time,
    /// cached_late_minutes.
    fn update_vehicle_shadows(&mut self, vehicle_idx: usize) {
        let vehicle = &self.vehicles[vehicle_idx];
        let visit_indices: Vec<usize> = vehicle.visits.iter().copied().collect();
        let departure_time = vehicle.departure_time;
        let depot_idx = vehicle.home_location.index;

        // Update shadow variables on visits
        let mut prev_departure = departure_time;
        let mut prev_loc_idx = depot_idx;
        let mut prev_visit_idx: Option<usize> = None;

        for &visit_idx in &visit_indices {
            if visit_idx >= self.visits.len() {
                continue;
            }

            // Compute arrival time
            let visit_loc_idx = self.visits[visit_idx].location.index;
            let travel = self.travel_time(prev_loc_idx, visit_loc_idx);
            let arrival = prev_departure + travel;

            // Update shadow variables
            let visit = &mut self.visits[visit_idx];
            visit.vehicle_idx = Some(vehicle_idx);
            visit.previous_visit_idx = prev_visit_idx;
            visit.arrival_time = Some(arrival);

            // Compute departure for next iteration
            let service_start = arrival.max(visit.min_start_time);
            prev_departure = service_start + visit.service_duration;
            prev_loc_idx = visit_loc_idx;
            prev_visit_idx = Some(visit_idx);
        }

        // Update cached aggregates on vehicle
        let total_demand: i32 = visit_indices
            .iter()
            .filter_map(|&idx| self.visits.get(idx))
            .map(|v| v.demand)
            .sum();

        let driving_time = self.total_driving_time(&self.vehicles[vehicle_idx]);

        let late_minutes: i64 = visit_indices
            .iter()
            .filter_map(|&idx| self.visits.get(idx))
            .map(|v| v.late_minutes())
            .sum();

        let vehicle = &mut self.vehicles[vehicle_idx];
        vehicle.cached_total_demand = total_demand;
        vehicle.cached_driving_time = driving_time;
        vehicle.cached_late_minutes = late_minutes;
    }
}

// ShadowVariableSupport is now auto-generated by #[shadow_variable_updates] macro
// List operations (list_len, list_remove, list_insert, sublist_remove, sublist_insert)
// are also auto-generated from the element_type parameter.

// =============================================================================
// Distance Meter for Nearby K-opt Selection
// =============================================================================

/// Distance meter for nearby k-opt selection in vehicle routing.
///
/// Measures distance between visits by their travel time, enabling
/// `NearbyKOptMoveSelector` to prune distant cut combinations.
///
/// # Examples
///
/// ```
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan, VrpDistanceMeter};
/// use solverforge::ListPositionDistanceMeter;
///
/// // Create a route: depot -> A -> B -> C
/// let depot = Location::new(0, 0.0, 0.0);
/// let loc_a = Location::new(1, 0.0, 0.01);   // ~1.1 km
/// let loc_b = Location::new(2, 0.0, 0.02);   // ~2.2 km from origin
/// let loc_c = Location::new(3, 0.0, 0.10);   // ~11 km from origin
///
/// let locations = vec![depot.clone(), loc_a.clone(), loc_b.clone(), loc_c.clone()];
/// let visits = vec![
///     Visit::new(0, "A", loc_a),
///     Visit::new(1, "B", loc_b),
///     Visit::new(2, "C", loc_c),
/// ];
/// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
/// vehicle.visits = vec![0, 1, 2];
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle]);
/// plan.finalize();
///
/// let meter = VrpDistanceMeter;
///
/// // Distance A to B (position 0 to 1) should be smaller than A to C (0 to 2)
/// let dist_ab = meter.distance(&plan, 0, 0, 1);
/// let dist_ac = meter.distance(&plan, 0, 0, 2);
/// assert!(dist_ab < dist_ac);
/// ```
#[derive(Debug, Clone, Copy)]
pub struct VrpDistanceMeter;

impl ListPositionDistanceMeter<VehicleRoutePlan> for VrpDistanceMeter {
    fn distance(&self, plan: &VehicleRoutePlan, entity_idx: usize, pos_a: usize, pos_b: usize) -> f64 {
        let visits = match plan.vehicles.get(entity_idx) {
            Some(v) => &v.visits,
            None => return f64::MAX,
        };

        let visit_a = match visits.get(pos_a) {
            Some(&idx) => idx,
            None => return f64::MAX,
        };
        let visit_b = match visits.get(pos_b) {
            Some(&idx) => idx,
            None => return f64::MAX,
        };

        let loc_a = match plan.visits.get(visit_a) {
            Some(v) => v.location.index,
            None => return f64::MAX,
        };
        let loc_b = match plan.visits.get(visit_b) {
            Some(v) => v.location.index,
            None => return f64::MAX,
        };

        plan.travel_time(loc_a, loc_b) as f64
    }
}

// =============================================================================
// Solution Descriptor
// =============================================================================

use solverforge::{EntityDescriptor, SolutionDescriptor, TypedEntityExtractor};
use std::any::TypeId;

/// Helper functions for typed entity extraction.
fn get_vehicles(plan: &VehicleRoutePlan) -> &Vec<Vehicle> {
    &plan.vehicles
}

fn get_vehicles_mut(plan: &mut VehicleRoutePlan) -> &mut Vec<Vehicle> {
    &mut plan.vehicles
}

/// Creates a solution descriptor for `VehicleRoutePlan`.
///
/// Used by `SimpleScoreDirector` and `ShadowAwareScoreDirector`.
///
/// # Examples
///
/// ```
/// use vehicle_routing::domain::create_solution_descriptor;
///
/// let descriptor = create_solution_descriptor();
/// assert_eq!(descriptor.entity_descriptor_count(), 1);
/// ```
pub fn create_solution_descriptor() -> SolutionDescriptor {
    let extractor = TypedEntityExtractor::new("Vehicle", "vehicles", get_vehicles, get_vehicles_mut);
    let entity_desc = EntityDescriptor::new("Vehicle", TypeId::of::<Vehicle>(), "vehicles")
        .with_extractor(Box::new(extractor));

    SolutionDescriptor::new("VehicleRoutePlan", TypeId::of::<VehicleRoutePlan>())
        .with_entity(entity_desc)
}
