//! DTOs for REST API requests/responses.

use chrono::NaiveDateTime;
use serde::{Deserialize, Serialize};

use crate::domain::{Vehicle, VehicleRoutePlan, Visit};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VisitDto {
    pub id: String,
    pub name: String,
    pub location: [f64; 2],
    pub demand: i32,
    pub min_start_time: NaiveDateTime,
    pub max_end_time: NaiveDateTime,
    pub service_duration: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vehicle: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arrival_time: Option<NaiveDateTime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub departure_time: Option<NaiveDateTime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub driving_time_seconds_from_previous_standstill: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VehicleDto {
    pub id: String,
    pub name: String,
    pub capacity: i32,
    pub home_location: [f64; 2],
    pub departure_time: NaiveDateTime,
    pub visits: Vec<String>,
    #[serde(default)]
    pub total_demand: i32,
    #[serde(default)]
    pub total_driving_time_seconds: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arrival_time: Option<NaiveDateTime>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VehicleRoutePlanDto {
    pub name: String,
    pub south_west_corner: [f64; 2],
    pub north_east_corner: [f64; 2],
    pub vehicles: Vec<VehicleDto>,
    pub visits: Vec<VisitDto>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub score: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub solver_status: Option<String>,
    #[serde(default)]
    pub total_driving_time_seconds: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_date_time: Option<NaiveDateTime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub end_date_time: Option<NaiveDateTime>,
}

impl VehicleRoutePlanDto {
    pub fn from_plan(plan: &VehicleRoutePlan, solver_status: Option<String>) -> Self {
        // Build vehicle visit assignments
        let mut vehicle_visits: Vec<Vec<&Visit>> = vec![Vec::new(); plan.vehicles.len()];
        for visit in &plan.visits {
            if let Some(v_idx) = visit.vehicle_idx {
                if v_idx < vehicle_visits.len() {
                    vehicle_visits[v_idx].push(visit);
                }
            }
        }

        // Compute arrival times for visits
        let mut visit_arrival_times: std::collections::HashMap<String, NaiveDateTime> =
            std::collections::HashMap::new();
        let mut visit_departure_times: std::collections::HashMap<String, NaiveDateTime> =
            std::collections::HashMap::new();
        let mut visit_driving_times: std::collections::HashMap<String, i64> =
            std::collections::HashMap::new();

        for (v_idx, vehicle) in plan.vehicles.iter().enumerate() {
            let visits = &vehicle_visits[v_idx];
            let mut current_time = vehicle.departure_time;
            let mut prev_loc_idx = vehicle.home_location_idx;

            for visit in visits {
                let travel_time = plan.travel_time(prev_loc_idx, visit.location_idx);
                visit_driving_times.insert(visit.id.clone(), travel_time);

                let arrival = current_time + chrono::TimeDelta::seconds(travel_time);
                visit_arrival_times.insert(visit.id.clone(), arrival);

                let service_start = arrival.max(visit.min_start_time);
                let departure =
                    service_start + chrono::TimeDelta::seconds(visit.service_duration_seconds);
                visit_departure_times.insert(visit.id.clone(), departure);

                current_time = departure;
                prev_loc_idx = visit.location_idx;
            }
        }

        // Build vehicle DTOs
        let vehicles: Vec<VehicleDto> = plan
            .vehicles
            .iter()
            .enumerate()
            .map(|(v_idx, v)| {
                let visits = &vehicle_visits[v_idx];
                let home_coords = plan
                    .get_coordinates(v.home_location_idx)
                    .unwrap_or((0.0, 0.0));

                let total_demand: i32 = visits.iter().map(|vis| vis.demand).sum();

                // Calculate total driving time and arrival time
                let mut total_driving = 0i64;
                let mut prev_loc_idx = v.home_location_idx;
                for visit in visits {
                    total_driving += plan.travel_time(prev_loc_idx, visit.location_idx);
                    prev_loc_idx = visit.location_idx;
                }
                if !visits.is_empty() {
                    total_driving += plan.travel_time(prev_loc_idx, v.home_location_idx);
                }

                let arrival_time = if visits.is_empty() {
                    Some(v.departure_time)
                } else {
                    let last_visit = visits.last().unwrap();
                    visit_departure_times.get(&last_visit.id).map(|&dep| {
                        dep + chrono::TimeDelta::seconds(
                            plan.travel_time(last_visit.location_idx, v.home_location_idx),
                        )
                    })
                };

                VehicleDto {
                    id: v.id.clone(),
                    name: v.name.clone(),
                    capacity: v.capacity,
                    home_location: [home_coords.0, home_coords.1],
                    departure_time: v.departure_time,
                    visits: visits.iter().map(|vis| vis.id.clone()).collect(),
                    total_demand,
                    total_driving_time_seconds: total_driving,
                    arrival_time,
                }
            })
            .collect();

        // Build visit DTOs
        let visits: Vec<VisitDto> = plan
            .visits
            .iter()
            .map(|v| {
                let coords = plan.get_coordinates(v.location_idx).unwrap_or((0.0, 0.0));
                VisitDto {
                    id: v.id.clone(),
                    name: v.name.clone(),
                    location: [coords.0, coords.1],
                    demand: v.demand,
                    min_start_time: v.min_start_time,
                    max_end_time: v.max_end_time,
                    service_duration: v.service_duration_seconds,
                    vehicle: v
                        .vehicle_idx
                        .and_then(|idx| plan.vehicles.get(idx))
                        .map(|veh| veh.id.clone()),
                    arrival_time: visit_arrival_times.get(&v.id).copied(),
                    departure_time: visit_departure_times.get(&v.id).copied(),
                    driving_time_seconds_from_previous_standstill: visit_driving_times
                        .get(&v.id)
                        .copied(),
                }
            })
            .collect();

        // Compute totals
        let total_driving: i64 = vehicles.iter().map(|v| v.total_driving_time_seconds).sum();
        let start_date_time = plan.vehicles.iter().map(|v| v.departure_time).min();
        let end_date_time = vehicles.iter().filter_map(|v| v.arrival_time).max();

        Self {
            name: plan.name.clone(),
            south_west_corner: [plan.south_west_corner.0, plan.south_west_corner.1],
            north_east_corner: [plan.north_east_corner.0, plan.north_east_corner.1],
            vehicles,
            visits,
            score: plan.score.map(|s| format!("{}", s)),
            solver_status,
            total_driving_time_seconds: total_driving,
            start_date_time,
            end_date_time,
        }
    }

    pub fn to_domain(&self) -> VehicleRoutePlan {
        // Build coordinate list from all unique coordinates
        let mut coords: Vec<(f64, f64)> = Vec::new();
        let mut coord_to_idx: std::collections::HashMap<(i64, i64), usize> =
            std::collections::HashMap::new();

        let coord_key = |lat: f64, lng: f64| -> (i64, i64) {
            ((lat * 1e7).round() as i64, (lng * 1e7).round() as i64)
        };

        let mut get_or_add_location = |lat: f64, lng: f64| -> usize {
            let key = coord_key(lat, lng);
            if let Some(&idx) = coord_to_idx.get(&key) {
                idx
            } else {
                let idx = coords.len();
                coords.push((lat, lng));
                coord_to_idx.insert(key, idx);
                idx
            }
        };

        // Add vehicle home locations
        let vehicle_home_idxs: Vec<usize> = self
            .vehicles
            .iter()
            .map(|v| get_or_add_location(v.home_location[0], v.home_location[1]))
            .collect();

        // Add visit locations
        let visit_loc_idxs: Vec<usize> = self
            .visits
            .iter()
            .map(|v| get_or_add_location(v.location[0], v.location[1]))
            .collect();

        // Build vehicles
        let vehicles: Vec<Vehicle> = self
            .vehicles
            .iter()
            .enumerate()
            .map(|(i, v)| {
                Vehicle::new(
                    i,
                    v.id.clone(),
                    v.name.clone(),
                    v.capacity,
                    vehicle_home_idxs[i],
                    v.departure_time,
                )
            })
            .collect();

        // Build vehicle ID to index map
        let vehicle_id_to_idx: std::collections::HashMap<&str, usize> = vehicles
            .iter()
            .map(|v| (v.id.as_str(), v.index))
            .collect();

        // Build visits
        let visits: Vec<Visit> = self
            .visits
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let mut visit = Visit::new(
                    v.id.clone(),
                    v.name.clone(),
                    visit_loc_idxs[i],
                    v.demand,
                    v.min_start_time,
                    v.max_end_time,
                    v.service_duration,
                );
                visit.vehicle_idx = v
                    .vehicle
                    .as_ref()
                    .and_then(|vid| vehicle_id_to_idx.get(vid.as_str()).copied());
                visit
            })
            .collect();

        VehicleRoutePlan::new(
            self.name.clone(),
            coords,
            vehicles,
            visits,
            (self.south_west_corner[0], self.south_west_corner[1]),
            (self.north_east_corner[0], self.north_east_corner[1]),
        )
    }
}

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InfoResponse {
    pub name: &'static str,
    pub version: &'static str,
    pub solver_engine: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StatusResponse {
    pub score: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConstraintAnalysisDto {
    pub name: String,
    #[serde(rename = "type")]
    pub constraint_type: String,
    pub weight: String,
    pub score: String,
    pub matches: Vec<ConstraintMatchDto>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConstraintMatchDto {
    pub score: String,
    pub justification: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AnalyzeResponse {
    pub score: String,
    pub constraints: Vec<ConstraintAnalysisDto>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RouteSegmentDto {
    pub vehicle_id: String,
    pub vehicle_name: String,
    pub polyline: String,
    pub point_count: usize,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GeometryResponse {
    pub segments: Vec<RouteSegmentDto>,
}
