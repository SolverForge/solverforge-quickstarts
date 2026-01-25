//! DTOs for REST API requests/responses.

use std::collections::HashMap;

use chrono::NaiveDateTime;
use serde::{Deserialize, Serialize};
use solverforge_maps::Coord;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VisitDto {
    pub id: String,
    pub name: String,
    pub location: Coord,
    pub location_idx: usize,
    pub demand: i32,
    pub min_start_time: NaiveDateTime,
    pub max_end_time: NaiveDateTime,
    pub service_duration: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vehicle: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arrival_time: Option<NaiveDateTime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_service_time: Option<NaiveDateTime>,
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
    pub home_location: Coord,
    pub home_location_idx: usize,
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
    /// Raw geometries indexed by "fromIdx-toIdx" for frontend lookup.
    /// Server-generated only - ignored on deserialize to prevent bloated requests.
    #[serde(default, skip_deserializing, skip_serializing_if = "Option::is_none")]
    pub geometries: Option<HashMap<String, Vec<Coord>>>,
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
