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

use crate::domain::{Vehicle, VehicleRoutePlan};

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
        .penalize_hard_with(|v: &Vehicle| HardSoftScore::of_hard(v.excess_demand() as i64))
        .as_constraint("vehicleCapacity");

    // HARD: Time windows - penalize late arrivals using cached aggregate
    let time_window = factory
        .clone()
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .filter(|v: &Vehicle| v.late_minutes() > 0)
        .penalize_hard_with(|v: &Vehicle| HardSoftScore::of_hard(v.late_minutes()))
        .as_constraint("serviceFinishedAfterMaxEndTime");

    // SOFT: Minimize travel time
    let minimize_travel = factory
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .penalize_with(|v: &Vehicle| HardSoftScore::of_soft(v.driving_time_minutes()))
        .as_constraint("minimizeTravelTime");

    (vehicle_capacity, time_window, minimize_travel)
}

/// Calculates the score for a vehicle routing solution.
///
/// Updates shadow variables and evaluates constraints using O(1) field access.
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
/// let score = calculate_score(&mut plan);
/// assert!(score.is_feasible());
/// ```
pub fn calculate_score(plan: &mut VehicleRoutePlan) -> HardSoftScore {
    plan.update_shadows();
    define_constraints().evaluate_all(plan)
}

/// Calculates total late minutes for a vehicle's route.
///
/// Uses shadow variable `arrival_time` on visits for O(1) per-visit evaluation.
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
/// plan.update_shadows();
///
/// let late = calculate_late_minutes(&plan, &vehicle);
/// assert!(late > 100);
/// ```
#[inline]
pub fn calculate_late_minutes(plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i64 {
    vehicle
        .visits
        .iter()
        .filter_map(|&idx| plan.visits.get(idx))
        .map(|visit| visit.late_minutes())
        .sum()
}

/// Calculates excess demand for a vehicle (0 if under capacity).
///
/// Uses cached aggregate `cached_total_demand` for O(1) evaluation.
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
/// let mut plan = VehicleRoutePlan::new("test", locations, visits, vec![vehicle]);
/// plan.finalize();
/// plan.update_shadows();
///
/// // Access vehicle from plan after update_shadows
/// assert_eq!(calculate_excess_capacity(&plan, &plan.vehicles[0]), 10);
/// ```
#[inline]
pub fn calculate_excess_capacity(_plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i32 {
    vehicle.excess_demand()
}
