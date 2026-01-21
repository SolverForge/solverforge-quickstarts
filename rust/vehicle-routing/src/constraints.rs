//! Constraints for Vehicle Routing Problem.
//!
//! Uses shadow variables on Vehicle (total_demand, total_driving_time_seconds)
//! so constraints can use entity-only closures without solution access.

use solverforge::prelude::*;

use crate::domain::{Vehicle, VehicleRoutePlan, Visit};

pub fn define_constraints() -> impl ConstraintSet<VehicleRoutePlan, HardSoftScore> {
    let factory = ConstraintFactory::<VehicleRoutePlan, HardSoftScore>::new();

    // Hard: vehicle capacity - uses shadow total_demand field
    let vehicle_capacity = factory
        .clone()
        .for_each(|s: &VehicleRoutePlan| s.vehicles.as_slice())
        .filter(|v: &Vehicle| v.total_demand > v.capacity)
        .penalize_hard_with(|v: &Vehicle| {
            HardSoftScore::of_hard((v.total_demand - v.capacity) as i64)
        })
        .as_constraint("vehicleCapacity");

    // Hard: service finished after max end time - uses Visit.arrival_time shadow
    // NOTE: Uses descriptor_index=1 because visits is the second entity collection
    let service_finished_after_max_end_time = factory
        .clone()
        .for_each(|s: &VehicleRoutePlan| s.visits.as_slice())
        .filter(|visit: &Visit| visit.is_service_finished_after_max_end_time())
        .penalize_hard_with(|visit: &Visit| {
            HardSoftScore::of_hard(visit.service_finished_delay_in_minutes())
        })
        .as_constraint_for_descriptor("serviceFinishedAfterMaxEndTime", 1);

    // Soft: minimize travel time - uses shadow total_driving_time_seconds field
    let minimize_travel_time = factory
        .for_each(|s: &VehicleRoutePlan| s.vehicles.as_slice())
        .penalize_with(|v: &Vehicle| HardSoftScore::of_soft(v.total_driving_time_seconds))
        .as_constraint("minimizeTravelTime");

    (
        vehicle_capacity,
        service_finished_after_max_end_time,
        minimize_travel_time,
    )
}
