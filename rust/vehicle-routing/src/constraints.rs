//! Score calculator for Vehicle Routing Problem.
//!
//! # Constraints
//!
//! - **Vehicle capacity** (hard): Total demand must not exceed vehicle capacity
//! - **Time windows** (hard): Service must complete before max end time
//! - **Minimize travel time** (soft): Reduce total driving time
//!
//! # Design
//!
//! Uses a simple score calculator function with full solution access.
//! No global state or RwLock overhead - direct array indexing into the plan's
//! travel time matrix and visits.

use solverforge::prelude::*;

use crate::domain::{Vehicle, VehicleRoutePlan};

/// Calculates the score for a vehicle routing solution.
///
/// # Hard constraints
/// - Vehicle capacity: penalize excess demand
/// - Time windows: penalize late arrivals
///
/// # Soft constraints
/// - Minimize total travel time (in minutes)
///
/// # Examples
///
/// ```
/// use vehicle_routing::constraints::calculate_score;
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
/// use solverforge::prelude::Score;  // For is_feasible()
///
/// let depot = Location::new(0, 0.0, 0.0);
/// let locations = vec![depot.clone()];
/// let visits = vec![Visit::new(0, "A", depot.clone()).with_demand(5)];
/// let mut vehicle = Vehicle::new(0, "V1", 10, depot);
/// vehicle.visits = vec![0];
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle]);
/// plan.finalize();
///
/// let score = calculate_score(&plan);
/// assert!(score.is_feasible()); // Demand 5 <= capacity 10
/// ```
pub fn calculate_score(plan: &VehicleRoutePlan) -> HardSoftScore {
    let mut hard = 0i64;
    let mut soft = 0i64;

    for vehicle in &plan.vehicles {
        // =====================================================================
        // HARD: Vehicle Capacity
        // =====================================================================
        let total_demand: i32 = vehicle
            .visits
            .iter()
            .filter_map(|&idx| plan.visits.get(idx))
            .map(|v| v.demand)
            .sum();

        if total_demand > vehicle.capacity {
            hard -= (total_demand - vehicle.capacity) as i64;
        }

        // =====================================================================
        // HARD: Time Windows
        // =====================================================================
        let late_minutes = calculate_late_minutes_for_vehicle(plan, vehicle);
        if late_minutes > 0 {
            hard -= late_minutes;
        }

        // =====================================================================
        // SOFT: Minimize Travel Time
        // =====================================================================
        let driving_seconds = plan.total_driving_time(vehicle);
        soft -= driving_seconds / 60; // Convert to minutes
    }

    HardSoftScore::of(hard, soft)
}

/// Calculates total late minutes for a vehicle's route.
///
/// A visit is late if service finishes after `max_end_time`.
fn calculate_late_minutes_for_vehicle(plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i64 {
    if vehicle.visits.is_empty() {
        return 0;
    }

    let mut total_late = 0i64;
    let mut current_time = vehicle.departure_time;
    let mut current_loc_idx = vehicle.home_location.index;

    for &visit_idx in &vehicle.visits {
        let Some(visit) = plan.visits.get(visit_idx) else {
            continue;
        };

        // Travel to this visit
        let travel = plan.travel_time(current_loc_idx, visit.location.index);
        let arrival = current_time + travel;

        // Service starts at max(arrival, min_start_time)
        let service_start = arrival.max(visit.min_start_time);
        let service_end = service_start + visit.service_duration;

        // Check if late (service finishes after max_end_time)
        if service_end > visit.max_end_time {
            let late_seconds = service_end - visit.max_end_time;
            // Round up to minutes
            total_late += (late_seconds + 59) / 60;
        }

        current_time = service_end;
        current_loc_idx = visit.location.index;
    }

    total_late
}

// ============================================================================
// Helper functions (for analyze endpoint)
// ============================================================================

/// Calculates total late minutes for a vehicle's route (public API).
///
/// # Examples
///
/// ```
/// use vehicle_routing::constraints::calculate_late_minutes;
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
///
/// let depot = Location::new(0, 0.0, 0.0);
/// let customer = Location::new(1, 0.0, 1.0);  // ~111 km away, ~2.2 hours at 50 km/h
///
/// let locations = vec![depot.clone(), customer.clone()];
/// let visits = vec![
///     Visit::new(0, "A", customer)
///         .with_time_window(0, 8 * 3600 + 30 * 60)  // Must finish by 8:30am
///         .with_service_duration(300),  // 5 min service
/// ];
/// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
/// vehicle.departure_time = 8 * 3600;  // Depart at 8am
/// vehicle.visits = vec![0];
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle.clone()]);
/// plan.finalize();
///
/// // Vehicle departs 8am, travels ~2.2 hours, arrives ~10:13am
/// // Service ends ~10:18am, but max_end is 8:30am
/// // Late by ~108 minutes
/// let late = calculate_late_minutes(&plan, &vehicle);
/// assert!(late > 100);
/// ```
#[inline]
pub fn calculate_late_minutes(plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i64 {
    calculate_late_minutes_for_vehicle(plan, vehicle)
}

/// Calculates excess demand for a vehicle (0 if under capacity).
///
/// # Examples
///
/// ```
/// use vehicle_routing::constraints::calculate_excess_capacity;
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
///
/// let depot = Location::new(0, 0.0, 0.0);
/// let locations = vec![depot.clone()];
/// let visits = vec![
///     Visit::new(0, "A", depot.clone()).with_demand(60),
///     Visit::new(1, "B", depot.clone()).with_demand(50),
/// ];
/// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
/// vehicle.visits = vec![0, 1]; // Total demand = 110
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle.clone()]);
/// plan.finalize();
///
/// // Excess = 110 - 100 = 10
/// assert_eq!(calculate_excess_capacity(&plan, &vehicle), 10);
/// ```
#[inline]
pub fn calculate_excess_capacity(plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i32 {
    let total_demand: i32 = vehicle
        .visits
        .iter()
        .filter_map(|&idx| plan.visits.get(idx))
        .map(|v| v.demand)
        .sum();

    (total_demand - vehicle.capacity).max(0)
}
