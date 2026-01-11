//! Constraints for Vehicle Routing Problem.
//!
//! Uses the fluent constraint stream API.

use solverforge::prelude::*;

use crate::domain::{Vehicle, VehicleRoutePlan};

/// Defines all VRP constraints using the fluent API.
pub fn define_constraints() -> impl ConstraintSet<VehicleRoutePlan, HardSoftScore> {
    let factory = ConstraintFactory::<VehicleRoutePlan, HardSoftScore>::new();

    // HARD: Vehicle capacity - penalize excess demand
    let vehicle_capacity = factory
        .clone()
        .for_each(|s: &VehicleRoutePlan| s.vehicles.as_slice())
        .filter_with_solution(|vehicle: &Vehicle, plan: &VehicleRoutePlan| {
            let total_demand: i32 = vehicle
                .visits
                .iter()
                .filter_map(|&idx| plan.visits.get(idx))
                .map(|v| v.demand)
                .sum();
            total_demand > vehicle.capacity
        })
        .penalize_with_solution(|vehicle: &Vehicle, plan: &VehicleRoutePlan| {
            let total_demand: i32 = vehicle
                .visits
                .iter()
                .filter_map(|&idx| plan.visits.get(idx))
                .map(|v| v.demand)
                .sum();
            let excess = (total_demand - vehicle.capacity).max(0) as i64;
            HardSoftScore::of_hard(-excess)
        })
        .as_constraint("Vehicle capacity");

    // HARD: Time windows - penalize late arrivals
    let time_windows = factory
        .clone()
        .for_each(|s: &VehicleRoutePlan| s.vehicles.as_slice())
        .filter_with_solution(|vehicle: &Vehicle, plan: &VehicleRoutePlan| {
            calculate_late_minutes(plan, vehicle) > 0
        })
        .penalize_with_solution(|vehicle: &Vehicle, plan: &VehicleRoutePlan| {
            let late = calculate_late_minutes(plan, vehicle);
            HardSoftScore::of_hard(-late)
        })
        .as_constraint("Time windows");

    // SOFT: Minimize travel time
    let minimize_travel = factory
        .for_each(|s: &VehicleRoutePlan| s.vehicles.as_slice())
        .filter(|vehicle: &Vehicle| !vehicle.visits.is_empty())
        .penalize_with_solution(|vehicle: &Vehicle, plan: &VehicleRoutePlan| {
            let driving_seconds = plan.total_driving_time(vehicle);
            HardSoftScore::of_soft(-driving_seconds / 60)
        })
        .as_constraint("Minimize travel time");

    (vehicle_capacity, time_windows, minimize_travel)
}

/// Calculates total late minutes for a vehicle's route.
pub fn calculate_late_minutes(plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i64 {
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

/// Calculates excess demand for a vehicle (0 if under capacity).
pub fn calculate_excess_capacity(plan: &VehicleRoutePlan, vehicle: &Vehicle) -> i32 {
    let total_demand: i32 = vehicle
        .visits
        .iter()
        .filter_map(|&idx| plan.visits.get(idx))
        .map(|v| v.demand)
        .sum();

    (total_demand - vehicle.capacity).max(0)
}
