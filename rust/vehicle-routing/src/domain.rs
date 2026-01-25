//! Domain model for Vehicle Routing Problem using list variables.
//!
//! Matches the Python legacy implementation exactly:
//! - Vehicle has `visits: Vec<Visit>` as planning list variable
//! - Visit has shadow variables for vehicle, previous_visit, next_visit, arrival_time

use std::collections::HashMap;

use chrono::{NaiveDateTime, TimeDelta};
use serde::{Deserialize, Serialize};
use solverforge::prelude::*;
use solverforge_maps::{Coord, TravelTimeMatrix, UNREACHABLE};

/// A customer visit that needs to be serviced.
///
/// This is a planning entity with shadow variables that track:
/// - Which vehicle it's assigned to (inverse relation)
/// - Previous/next visit in the route (element shadows)
/// - Computed arrival time (cascading update)
#[planning_entity]
#[derive(Serialize, Deserialize)]
pub struct Visit {
    #[planning_id]
    pub id: String,
    pub name: String,
    pub location_idx: usize,
    pub demand: i32,
    #[serde(rename = "minStartTime")]
    pub min_start_time: NaiveDateTime,
    #[serde(rename = "maxEndTime")]
    pub max_end_time: NaiveDateTime,
    #[serde(rename = "serviceDuration")]
    pub service_duration_seconds: i64,

    #[inverse_relation_shadow_variable(source_variable_name = "visits")]
    #[serde(skip)]
    pub vehicle_idx: Option<usize>,

    #[previous_element_shadow_variable(source_variable_name = "visits")]
    #[serde(skip)]
    pub previous_visit_idx: Option<usize>,

    #[next_element_shadow_variable(source_variable_name = "visits")]
    #[serde(skip)]
    pub next_visit_idx: Option<usize>,

    #[cascading_update_shadow_variable]
    #[serde(skip)]
    pub arrival_time: Option<NaiveDateTime>,
}

impl Visit {
    pub fn new(
        id: impl Into<String>,
        name: impl Into<String>,
        location_idx: usize,
        demand: i32,
        min_start_time: NaiveDateTime,
        max_end_time: NaiveDateTime,
        service_duration_seconds: i64,
    ) -> Self {
        Self {
            id: id.into(),
            name: name.into(),
            location_idx,
            demand,
            min_start_time,
            max_end_time,
            service_duration_seconds,
            vehicle_idx: None,
            previous_visit_idx: None,
            next_visit_idx: None,
            arrival_time: None,
        }
    }

    pub fn departure_time(&self) -> Option<NaiveDateTime> {
        self.arrival_time.map(|arrival| {
            let service_start = arrival.max(self.min_start_time);
            service_start + TimeDelta::seconds(self.service_duration_seconds)
        })
    }

    pub fn is_service_finished_after_max_end_time(&self) -> bool {
        self.departure_time()
            .is_some_and(|dep| dep > self.max_end_time)
    }

    pub fn service_finished_delay_in_minutes(&self) -> i64 {
        match self.departure_time() {
            Some(dep) if dep > self.max_end_time => {
                let delay = dep - self.max_end_time;
                (delay.num_seconds() + 59) / 60 // Round up to next minute
            }
            _ => 0,
        }
    }
}

#[planning_entity]
#[derive(Serialize, Deserialize)]
pub struct Vehicle {
    #[planning_id]
    pub index: usize,
    pub id: String,
    pub name: String,
    pub capacity: i32,
    #[serde(rename = "homeLocationIdx")]
    pub home_location_idx: usize,
    #[serde(rename = "departureTime")]
    pub departure_time: NaiveDateTime,

    #[planning_list_variable]
    #[serde(skip)]
    pub visits: Vec<usize>,

    /// Shadow aggregate: total demand of all visits assigned to this vehicle.
    /// Auto-updated by solver when visits list changes.
    #[serde(skip)]
    pub total_demand: i32,

    /// Shadow computed: total driving time in seconds for this vehicle's route.
    /// Auto-updated by solver when visits list changes.
    #[serde(skip)]
    pub total_driving_time_seconds: i64,
}

impl Vehicle {
    pub fn new(
        index: usize,
        id: impl Into<String>,
        name: impl Into<String>,
        capacity: i32,
        home_location_idx: usize,
        departure_time: NaiveDateTime,
    ) -> Self {
        Self {
            index,
            id: id.into(),
            name: name.into(),
            capacity,
            home_location_idx,
            departure_time,
            visits: Vec::new(),
            total_demand: 0,
            total_driving_time_seconds: 0,
        }
    }
}

#[planning_solution]
#[solverforge_constraints_path = "crate::constraints::define_constraints"]
#[shadow_variable_updates(
    list_owner = "vehicles",
    list_field = "visits",
    element_collection = "visits",
    element_type = "usize",
    inverse_field = "vehicle_idx",
    previous_field = "previous_visit_idx",
    next_field = "next_visit_idx",
    cascading_listener = "update_arrival_time",
    entity_aggregate = "total_demand:sum:demand",
    entity_compute = "total_driving_time_seconds:compute_vehicle_driving_time"
)]
#[derive(Serialize, Deserialize)]
pub struct VehicleRoutePlan {
    pub name: String,
    #[serde(skip)]
    pub coordinates: Vec<Coord>,
    #[planning_entity_collection]
    pub vehicles: Vec<Vehicle>,
    #[planning_entity_collection]
    pub visits: Vec<Visit>,
    #[planning_score]
    pub score: Option<HardSoftScore>,
    #[serde(rename = "solverStatus", skip_serializing_if = "Option::is_none")]
    pub solver_status: Option<String>,
    #[serde(skip)]
    pub travel_times: TravelTimeMatrix,
    #[serde(skip)]
    pub geometries: HashMap<(usize, usize), Vec<Coord>>,
}

impl VehicleRoutePlan {
    pub fn new(
        name: impl Into<String>,
        coordinates: Vec<Coord>,
        vehicles: Vec<Vehicle>,
        visits: Vec<Visit>,
    ) -> Self {
        Self {
            name: name.into(),
            coordinates,
            vehicles,
            visits,
            score: None,
            solver_status: None,
            travel_times: TravelTimeMatrix::default(),
            geometries: HashMap::new(),
        }
    }

    #[inline]
    pub fn travel_time(&self, from_idx: usize, to_idx: usize) -> i64 {
        self.travel_times
            .get(from_idx, to_idx)
            .unwrap_or(UNREACHABLE)
    }

    #[inline]
    pub fn get_coordinates(&self, idx: usize) -> Option<Coord> {
        self.coordinates.get(idx).copied()
    }

    #[inline]
    pub fn visit(&self, visit_idx: usize) -> &Visit {
        &self.visits[visit_idx]
    }

    pub fn vehicle_total_demand(&self, vehicle: &Vehicle) -> i32 {
        vehicle
            .visits
            .iter()
            .map(|&idx| self.visits[idx].demand)
            .sum()
    }

    pub fn vehicle_total_driving_time_seconds(&self, vehicle: &Vehicle) -> i64 {
        if vehicle.visits.is_empty() {
            return 0;
        }

        let mut total = 0i64;
        let mut prev_loc = vehicle.home_location_idx;

        for &visit_idx in &vehicle.visits {
            let visit_loc = self.visits[visit_idx].location_idx;
            total += self.travel_time(prev_loc, visit_loc);
            prev_loc = visit_loc;
        }

        // Return to home
        total += self.travel_time(prev_loc, vehicle.home_location_idx);
        total
    }

    /// Shadow variable computation: calculate total driving time for a vehicle entity.
    /// Called by solver when vehicle's visits list changes.
    pub fn compute_vehicle_driving_time(&self, entity_idx: usize) -> i64 {
        let vehicle = &self.vehicles[entity_idx];
        let time = self.vehicle_total_driving_time_seconds(vehicle);
        eprintln!(
            "compute_vehicle_driving_time(entity={}) visits={} time={}",
            entity_idx,
            vehicle.visits.len(),
            time
        );
        time
    }

    /// Cascading shadow variable listener: update arrival_time for a visit.
    /// Called by solver when previous visit or vehicle assignment changes.
    pub fn update_arrival_time(&mut self, visit_idx: usize) {
        let visit = &self.visits[visit_idx];

        // Get vehicle and previous visit info
        let vehicle_idx = match visit.vehicle_idx {
            Some(idx) => idx,
            None => {
                // Not assigned to any vehicle
                self.visits[visit_idx].arrival_time = None;
                return;
            }
        };

        let vehicle = &self.vehicles[vehicle_idx];

        // Determine departure location and time
        let (prev_loc, departure_time) = match visit.previous_visit_idx {
            Some(prev_idx) => {
                let prev_visit = &self.visits[prev_idx];
                let dep_time = prev_visit
                    .departure_time()
                    .unwrap_or(vehicle.departure_time);
                (prev_visit.location_idx, dep_time)
            }
            None => {
                // First visit in route - depart from vehicle home
                (vehicle.home_location_idx, vehicle.departure_time)
            }
        };

        // Calculate arrival time
        let travel_seconds = self.travel_time(prev_loc, self.visits[visit_idx].location_idx);
        let arrival = departure_time + TimeDelta::seconds(travel_seconds);
        self.visits[visit_idx].arrival_time = Some(arrival);
    }
}
