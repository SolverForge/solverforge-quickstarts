//! Converters between domain models and DTOs.

use chrono::TimeDelta;
use std::collections::HashMap;

use crate::domain::{Vehicle, VehicleRoutePlan, Visit};
use crate::dto::{VehicleDto, VehicleRoutePlanDto, VisitDto};

impl VehicleRoutePlanDto {
    pub fn from_plan(plan: &VehicleRoutePlan, solver_status: Option<String>) -> Self {
        // Build vehicle visit assignments using the ordered visits list from each vehicle
        let vehicle_visits: Vec<Vec<&Visit>> = plan
            .vehicles
            .iter()
            .map(|v| {
                v.visits
                    .iter()
                    .filter_map(|&visit_idx| plan.visits.get(visit_idx))
                    .collect()
            })
            .collect();

        // Compute arrival times for visits
        let mut visit_arrival_times: HashMap<String, chrono::NaiveDateTime> = HashMap::new();
        let mut visit_departure_times: HashMap<String, chrono::NaiveDateTime> = HashMap::new();
        let mut visit_driving_times: HashMap<String, i64> = HashMap::new();

        for (v_idx, vehicle) in plan.vehicles.iter().enumerate() {
            let visits = &vehicle_visits[v_idx];
            let mut current_time = vehicle.departure_time;
            let mut prev_loc_idx = vehicle.home_location_idx;

            for visit in visits {
                let travel_time = plan.travel_time(prev_loc_idx, visit.location_idx);
                visit_driving_times.insert(visit.id.clone(), travel_time);

                let arrival = current_time + TimeDelta::seconds(travel_time);
                visit_arrival_times.insert(visit.id.clone(), arrival);

                let service_start = arrival.max(visit.min_start_time);
                let departure = service_start + TimeDelta::seconds(visit.service_duration_seconds);
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
                        dep + TimeDelta::seconds(
                            plan.travel_time(last_visit.location_idx, v.home_location_idx),
                        )
                    })
                };

                VehicleDto {
                    id: v.id.clone(),
                    name: v.name.clone(),
                    capacity: v.capacity,
                    home_location: [home_coords.0, home_coords.1],
                    home_location_idx: v.home_location_idx,
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
                    location_idx: v.location_idx,
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

        // Convert geometries to simple "fromIdx-toIdx" -> polyline map
        let geometries = if plan.geometries.is_empty() {
            None
        } else {
            let geo_map: HashMap<String, String> = plan
                .geometries
                .iter()
                .map(|((from, to), polyline)| (format!("{}-{}", from, to), polyline.clone()))
                .collect();
            Some(geo_map)
        };

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
            geometries,
        }
    }

    /// Convert plan to DTO with externally-provided geometries.
    /// Used during solving when geometries are stored separately from the solution.
    pub fn from_plan_with_geometries(
        plan: &VehicleRoutePlan,
        geometries: &HashMap<(usize, usize), String>,
        solver_status: Option<String>,
    ) -> Self {
        // Build vehicle visit assignments using the ordered visits list from each vehicle
        let vehicle_visits: Vec<Vec<&Visit>> = plan
            .vehicles
            .iter()
            .map(|v| {
                v.visits
                    .iter()
                    .filter_map(|&visit_idx| plan.visits.get(visit_idx))
                    .collect()
            })
            .collect();

        // Compute arrival times for visits
        let mut visit_arrival_times: HashMap<String, chrono::NaiveDateTime> = HashMap::new();
        let mut visit_departure_times: HashMap<String, chrono::NaiveDateTime> = HashMap::new();
        let mut visit_driving_times: HashMap<String, i64> = HashMap::new();

        for (v_idx, vehicle) in plan.vehicles.iter().enumerate() {
            let visits = &vehicle_visits[v_idx];
            let mut current_time = vehicle.departure_time;
            let mut prev_loc_idx = vehicle.home_location_idx;

            for visit in visits {
                let travel_time = plan.travel_time(prev_loc_idx, visit.location_idx);
                visit_driving_times.insert(visit.id.clone(), travel_time);

                let arrival = current_time + TimeDelta::seconds(travel_time);
                visit_arrival_times.insert(visit.id.clone(), arrival);

                let service_start = arrival.max(visit.min_start_time);
                let departure = service_start + TimeDelta::seconds(visit.service_duration_seconds);
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
                        dep + TimeDelta::seconds(
                            plan.travel_time(last_visit.location_idx, v.home_location_idx),
                        )
                    })
                };

                VehicleDto {
                    id: v.id.clone(),
                    name: v.name.clone(),
                    capacity: v.capacity,
                    home_location: [home_coords.0, home_coords.1],
                    home_location_idx: v.home_location_idx,
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
                    location_idx: v.location_idx,
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

        // Convert geometries to simple "fromIdx-toIdx" -> polyline map
        let geo_dto = if geometries.is_empty() {
            None
        } else {
            let geo_map: HashMap<String, String> = geometries
                .iter()
                .map(|((from, to), polyline)| (format!("{}-{}", from, to), polyline.clone()))
                .collect();
            Some(geo_map)
        };

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
            geometries: geo_dto,
        }
    }

    pub fn to_domain(&self) -> VehicleRoutePlan {
        // Build coordinate list preserving original indices from DTOs.
        // This ensures geometry keys ("fromIdx-toIdx") remain valid after round-trip.
        let max_vehicle_idx = self
            .vehicles
            .iter()
            .map(|v| v.home_location_idx)
            .max()
            .unwrap_or(0);
        let max_visit_idx = self
            .visits
            .iter()
            .map(|v| v.location_idx)
            .max()
            .unwrap_or(0);
        let coords_len = max_vehicle_idx.max(max_visit_idx) + 1;

        let mut coords: Vec<(f64, f64)> = vec![(0.0, 0.0); coords_len];

        // Place vehicle home locations at their original indices
        for v in &self.vehicles {
            coords[v.home_location_idx] = (v.home_location[0], v.home_location[1]);
        }

        // Place visit locations at their original indices
        for v in &self.visits {
            coords[v.location_idx] = (v.location[0], v.location[1]);
        }

        // Build visit ID to index map
        let visit_id_to_idx: HashMap<&str, usize> = self
            .visits
            .iter()
            .enumerate()
            .map(|(i, v)| (v.id.as_str(), i))
            .collect();

        // Build vehicles with their visit lists populated
        let vehicles: Vec<Vehicle> = self
            .vehicles
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let mut vehicle = Vehicle::new(
                    i,
                    v.id.clone(),
                    v.name.clone(),
                    v.capacity,
                    v.home_location_idx, // Preserve original index
                    v.departure_time,
                );
                // Populate the vehicle's visits list from DTO
                vehicle.visits = v
                    .visits
                    .iter()
                    .filter_map(|visit_id| visit_id_to_idx.get(visit_id.as_str()).copied())
                    .collect();
                vehicle
            })
            .collect();

        // Build vehicle ID to index map
        let vehicle_id_to_idx: HashMap<&str, usize> =
            vehicles.iter().map(|v| (v.id.as_str(), v.index)).collect();

        // Build visits
        let visits: Vec<Visit> = self
            .visits
            .iter()
            .map(|v| {
                let mut visit = Visit::new(
                    v.id.clone(),
                    v.name.clone(),
                    v.location_idx, // Preserve original index
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
