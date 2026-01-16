//! Constraints for Vehicle Routing Problem.

use solverforge::prelude::*;
use solverforge::stream::joiner::equal_bi;

use crate::domain::{Vehicle, VehicleRoutePlan, Visit};

pub fn define_constraints() -> impl ConstraintSet<VehicleRoutePlan, HardSoftScore> {
    let factory = ConstraintFactory::<VehicleRoutePlan, HardSoftScore>::new();

    let vehicle_capacity = factory
        .clone()
        .for_each(|s: &VehicleRoutePlan| s.visits.as_slice())
        .join(
            |s: &VehicleRoutePlan| s.vehicles.as_slice(),
            equal_bi(
                |visit: &Visit| visit.vehicle_idx,
                |vehicle: &Vehicle| Some(vehicle.index),
            ),
        )
        .filter(|visit: &Visit, vehicle: &Vehicle| visit.demand > vehicle.capacity)
        .penalize_hard_with(|visit: &Visit, vehicle: &Vehicle| {
            HardSoftScore::of_hard((visit.demand - vehicle.capacity) as i64)
        })
        .as_constraint("vehicleCapacity");

    let minimize_travel = factory
        .for_each(|s: &VehicleRoutePlan| s.visits.as_slice())
        .filter(|visit: &Visit| visit.vehicle_idx.is_some())
        .penalize_with(|_visit: &Visit| HardSoftScore::of_soft(1))
        .as_constraint("minimizeTravelTime");

    (vehicle_capacity, minimize_travel)
}
