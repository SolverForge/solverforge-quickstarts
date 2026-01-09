//! Constraint definitions for Vehicle Routing Problem.
//!
//! # Example
//!
//! ```
//! use vehicle_routing::demo_data::generate_philadelphia;
//!
//! let mut plan = generate_philadelphia();
//! plan.finalize();
//! let result = plan.solve();
//!
//! // All visits assigned
//! let total: usize = result.vehicles.iter().map(|v| v.visits.len()).sum();
//! assert_eq!(total, 49);
//!
//! // Has a score
//! assert!(result.score.is_some());
//! ```

use solverforge::prelude::*;
use solverforge::stream::ConstraintFactory;
use solverforge::ConstraintSet;

use crate::domain::{Vehicle, VehicleRoutePlan};

/// Creates the constraint set for vehicle routing.
pub fn define_constraints() -> impl ConstraintSet<VehicleRoutePlan, HardSoftScore> {
    let factory = ConstraintFactory::<VehicleRoutePlan, HardSoftScore>::new();

    let vehicle_capacity = factory
        .clone()
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .filter(|v: &Vehicle| v.excess_demand() > 0)
        .penalize_hard_with(|v: &Vehicle| HardSoftScore::of_hard(v.excess_demand() as i64))
        .as_constraint("vehicleCapacity");

    let time_window = factory
        .clone()
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .filter(|v: &Vehicle| v.late_minutes() > 0)
        .penalize_hard_with(|v: &Vehicle| HardSoftScore::of_hard(v.late_minutes()))
        .as_constraint("serviceFinishedAfterMaxEndTime");

    let minimize_travel = factory
        .for_each(|p: &VehicleRoutePlan| p.vehicles.as_slice())
        .penalize_with(|v: &Vehicle| HardSoftScore::of_soft(v.driving_time_minutes()))
        .as_constraint("minimizeTravelTime");

    (vehicle_capacity, time_window, minimize_travel)
}
