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

