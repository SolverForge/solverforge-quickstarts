//! Constraint definitions for Vehicle Routing Problem.
//!
//! Uses fluent constraint API with shadow variables for O(1) evaluation.
//!
//! # Constraints
//!
//! - **Vehicle capacity** (hard): Total demand must not exceed vehicle capacity
//! - **Time windows** (hard): Service must complete before max end time
//! - **Minimize travel time** (soft): Reduce total driving time

use solverforge::prelude::*;
use solverforge::stream::ConstraintFactory;
use solverforge::ConstraintSet;

use crate::domain::{Vehicle, VehicleRoutePlan, Visit};

/// Creates the constraint set for vehicle routing.
///
/// All constraints use O(1) field access via shadow variables and cached
/// aggregates. Call `plan.update_shadows()` before scoring.
///
/// # Examples
///
/// ```
/// use vehicle_routing::constraints::define_constraints;
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
/// use solverforge::ConstraintSet;
/// use solverforge::prelude::Score;
///
/// let depot = Location::new(0, 0.0, 0.0);
/// let loc1 = Location::new(1, 0.0, 0.01);
///
/// let locations = vec![depot.clone(), loc1.clone()];
/// let visits = vec![Visit::new(0, "A", loc1).with_demand(5)];
/// let mut vehicle = Vehicle::new(0, "V1", 10, depot);
/// vehicle.visits = vec![0];
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle]);
/// plan.finalize();
/// plan.update_shadows();
///
/// let constraints = define_constraints();
/// let score = constraints.evaluate_all(&plan);
/// assert!(score.is_feasible());  // Demand 5 <= capacity 10
/// ```
pub fn define_constraints() -> impl ConstraintSet<VehicleRoutePlan, HardSoftScore> {
    let factory = ConstraintFactory::<VehicleRoutePlan, HardSoftScore>::new();

    // HARD: Vehicle capacity - penalize excess demand
    let vehicle_capacity = factory
        .clone()
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .filter(|v: &Vehicle| v.excess_demand() > 0)
        .penalize_hard_with(|v: &Vehicle| HardSoftScore::of_hard(-(v.excess_demand() as i64)))
        .as_constraint("vehicleCapacity");

    // HARD: Time windows - penalize late arrivals using shadow variable
    let time_window = factory
        .clone()
        .for_each(|p: &VehicleRoutePlan| p.visits.as_slice())
        .filter(|v: &Visit| v.is_late())
        .penalize_hard_with(|v: &Visit| HardSoftScore::of_hard(-v.late_minutes()))
        .as_constraint("serviceFinishedAfterMaxEndTime");

    // SOFT: Minimize travel time
    let minimize_travel = factory
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .penalize_with(|v: &Vehicle| HardSoftScore::of_soft(-v.driving_time_minutes()))
        .as_constraint("minimizeTravelTime");

    (vehicle_capacity, time_window, minimize_travel)
}

// ============================================================================
// Legacy function-based score calculator (for backward compatibility)
// ============================================================================

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
/// use solverforge::prelude::Score;
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
/// assert!(score.is_feasible());
/// ```
pub fn calculate_score(plan: &VehicleRoutePlan) -> HardSoftScore {
    let mut hard = 0i64;
    let mut soft = 0i64;

    for vehicle in &plan.vehicles {
        // HARD: Vehicle Capacity
        let total_demand: i32 = vehicle
            .visits
            .iter()
            .filter_map(|&idx| plan.visits.get(idx))
            .map(|v| v.demand)
            .sum();

        if total_demand > vehicle.capacity {
            hard -= (total_demand - vehicle.capacity) as i64;
        }

        // HARD: Time Windows
        let late_minutes = calculate_late_minutes_for_vehicle(plan, vehicle);
        if late_minutes > 0 {
            hard -= late_minutes;
        }

        // SOFT: Minimize Travel Time
        let driving_seconds = plan.total_driving_time(vehicle);
        soft -= driving_seconds / 60;
    }

    HardSoftScore::of(hard, soft)
}

/// Calculates total late minutes for a vehicle's route.
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

        let travel = plan.travel_time(current_loc_idx, visit.location.index);
        let arrival = current_time + travel;
        let service_start = arrival.max(visit.min_start_time);
        let service_end = service_start + visit.service_duration;

        if service_end > visit.max_end_time {
            let late_seconds = service_end - visit.max_end_time;
            total_late += (late_seconds + 59) / 60;
        }

        current_time = service_end;
        current_loc_idx = visit.location.index;
    }

    total_late
}

/// Calculates total late minutes for a vehicle's route (public API).
///
/// # Examples
///
/// ```
/// use vehicle_routing::constraints::calculate_late_minutes;
/// use vehicle_routing::domain::{Location, Visit, Vehicle, VehicleRoutePlan};
///
/// let depot = Location::new(0, 0.0, 0.0);
/// let customer = Location::new(1, 0.0, 1.0);
///
/// let locations = vec![depot.clone(), customer.clone()];
/// let visits = vec![
///     Visit::new(0, "A", customer)
///         .with_time_window(0, 8 * 3600 + 30 * 60)
///         .with_service_duration(300),
/// ];
/// let mut vehicle = Vehicle::new(0, "V1", 100, depot);
/// vehicle.departure_time = 8 * 3600;
/// vehicle.visits = vec![0];
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle.clone()]);
/// plan.finalize();
///
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
/// vehicle.visits = vec![0, 1];
///
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle.clone()]);
/// plan.finalize();
///
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
