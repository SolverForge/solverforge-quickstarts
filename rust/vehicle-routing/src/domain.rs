//! Domain model for Vehicle Routing Problem.

use chrono::NaiveDateTime;
use serde::{Deserialize, Serialize};
use solverforge::prelude::*;

/// A customer visit that needs to be serviced.
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
    #[planning_variable(allows_unassigned = true)]
    #[serde(rename = "vehicleIdx")]
    pub vehicle_idx: Option<usize>,
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
        }
    }
}

/// A vehicle that can service visits.
#[problem_fact]
#[derive(Serialize, Deserialize, Hash)]
pub struct Vehicle {
    pub index: usize,
    pub id: String,
    pub name: String,
    pub capacity: i32,
    #[serde(rename = "homeLocationIdx")]
    pub home_location_idx: usize,
    #[serde(rename = "departureTime")]
    pub departure_time: NaiveDateTime,
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
        }
    }
}

/// The vehicle routing solution.
#[planning_solution]
#[basic_variable_config(
    entity_collection = "visits",
    variable_field = "vehicle_idx",
    variable_type = "usize",
    value_range = "vehicles"
)]
#[solverforge_constraints_path = "crate::constraints::define_constraints"]
#[derive(Serialize, Deserialize)]
pub struct VehicleRoutePlan {
    pub name: String,
    #[serde(skip)]
    pub coordinates: Vec<(f64, f64)>,
    #[problem_fact_collection]
    pub vehicles: Vec<Vehicle>,
    #[planning_entity_collection]
    pub visits: Vec<Visit>,
    #[serde(rename = "southWestCorner")]
    pub south_west_corner: (f64, f64),
    #[serde(rename = "northEastCorner")]
    pub north_east_corner: (f64, f64),
    #[planning_score]
    pub score: Option<HardSoftScore>,
    #[serde(rename = "solverStatus", skip_serializing_if = "Option::is_none")]
    pub solver_status: Option<String>,
    #[serde(skip)]
    pub travel_times: Vec<Vec<i64>>,
}

impl VehicleRoutePlan {
    pub fn new(
        name: impl Into<String>,
        coordinates: Vec<(f64, f64)>,
        vehicles: Vec<Vehicle>,
        visits: Vec<Visit>,
        south_west_corner: (f64, f64),
        north_east_corner: (f64, f64),
    ) -> Self {
        Self {
            name: name.into(),
            coordinates,
            vehicles,
            visits,
            south_west_corner,
            north_east_corner,
            score: None,
            solver_status: None,
            travel_times: Vec::new(),
        }
    }

    #[inline]
    pub fn travel_time(&self, from_idx: usize, to_idx: usize) -> i64 {
        if self.travel_times.is_empty() {
            let (from_lat, from_lng) = self.coordinates[from_idx];
            let (to_lat, to_lng) = self.coordinates[to_idx];
            let dist = solverforge_maps::haversine_distance(from_lat, from_lng, to_lat, to_lng);
            (dist / 13.89).round() as i64
        } else {
            self.travel_times[from_idx][to_idx]
        }
    }

    #[inline]
    pub fn get_coordinates(&self, idx: usize) -> Option<(f64, f64)> {
        self.coordinates.get(idx).copied()
    }
}
