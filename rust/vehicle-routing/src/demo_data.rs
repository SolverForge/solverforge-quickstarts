//! Demo data generation for vehicle routing.

use chrono::{NaiveDateTime, NaiveTime, TimeDelta};
use rand::prelude::*;
use std::str::FromStr;

use crate::domain::{Vehicle, VehicleRoutePlan, Visit};

const VEHICLE_NAMES: &[&str] = &[
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet",
];

/// Customer types with time windows and demand patterns.
#[derive(Clone, Copy)]
pub enum CustomerType {
    Residential,
    Business,
    Restaurant,
}

impl CustomerType {
    fn window_start(&self) -> NaiveTime {
        match self {
            CustomerType::Residential => NaiveTime::from_hms_opt(17, 0, 0).unwrap(),
            CustomerType::Business => NaiveTime::from_hms_opt(9, 0, 0).unwrap(),
            CustomerType::Restaurant => NaiveTime::from_hms_opt(6, 0, 0).unwrap(),
        }
    }

    fn window_end(&self) -> NaiveTime {
        match self {
            CustomerType::Residential => NaiveTime::from_hms_opt(20, 0, 0).unwrap(),
            CustomerType::Business => NaiveTime::from_hms_opt(17, 0, 0).unwrap(),
            CustomerType::Restaurant => NaiveTime::from_hms_opt(10, 0, 0).unwrap(),
        }
    }

    fn demand_range(&self) -> (i32, i32) {
        match self {
            CustomerType::Residential => (1, 2),
            CustomerType::Business => (3, 6),
            CustomerType::Restaurant => (5, 10),
        }
    }

    fn service_minutes_range(&self) -> (i64, i64) {
        match self {
            CustomerType::Residential => (5, 10),
            CustomerType::Business => (15, 30),
            CustomerType::Restaurant => (20, 40),
        }
    }
}

/// Demo data configuration.
#[derive(Clone, Copy)]
pub struct DemoDataConfig {
    pub seed: u64,
    pub visit_count: usize,
    pub vehicle_count: usize,
    pub vehicle_start_time: NaiveTime,
    pub min_vehicle_capacity: i32,
    pub max_vehicle_capacity: i32,
    pub south_west: (f64, f64),
    pub north_east: (f64, f64),
}

/// Available demo datasets.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DemoData {
    Philadelphia,
    Hartford,
    Firenze,
}

impl FromStr for DemoData {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "PHILADELPHIA" => Ok(DemoData::Philadelphia),
            "HARTFORT" | "HARTFORD" => Ok(DemoData::Hartford),
            "FIRENZE" | "FLORENCE" => Ok(DemoData::Firenze),
            _ => Err(format!("Unknown demo data: {}", s)),
        }
    }
}

impl DemoData {
    pub fn config(&self) -> DemoDataConfig {
        let start_time = NaiveTime::from_hms_opt(6, 0, 0).unwrap();

        match self {
            DemoData::Philadelphia => DemoDataConfig {
                seed: 0,
                visit_count: 55,
                vehicle_count: 10,
                vehicle_start_time: start_time,
                min_vehicle_capacity: 15,
                max_vehicle_capacity: 30,
                south_west: (39.92, -75.23),
                north_east: (40.00, -75.11),
            },
            DemoData::Hartford => DemoDataConfig {
                seed: 1,
                visit_count: 50,
                vehicle_count: 6,
                vehicle_start_time: start_time,
                min_vehicle_capacity: 20,
                max_vehicle_capacity: 30,
                south_west: (41.69, -72.75),
                north_east: (41.79, -72.60),
            },
            DemoData::Firenze => DemoDataConfig {
                seed: 2,
                visit_count: 77,
                vehicle_count: 6,
                vehicle_start_time: start_time,
                min_vehicle_capacity: 20,
                max_vehicle_capacity: 40,
                south_west: (43.73, 11.17),
                north_east: (43.81, 11.32),
            },
        }
    }

    pub fn depot_locations(&self) -> Vec<(&'static str, f64, f64)> {
        match self {
            DemoData::Philadelphia => vec![
                ("Central Depot - City Hall", 39.9526, -75.1652),
                ("South Philly Depot", 39.9256, -75.1697),
                ("University City Depot", 39.9522, -75.1932),
                ("North Philly Depot", 39.9907, -75.1556),
                ("Fishtown Depot", 39.9712, -75.1340),
                ("West Philly Depot", 39.9601, -75.2175),
            ],
            DemoData::Hartford => vec![
                ("Downtown Hartford Depot", 41.7658, -72.6734),
                ("Asylum Hill Depot", 41.7700, -72.6900),
                ("South End Depot", 41.7400, -72.6750),
                ("West End Depot", 41.7680, -72.7100),
                ("Barry Square Depot", 41.7450, -72.6800),
                ("Clay Arsenal Depot", 41.7750, -72.6850),
            ],
            DemoData::Firenze => vec![
                ("Centro Storico Depot", 43.7696, 11.2558),
                ("Santa Maria Novella Depot", 43.7745, 11.2487),
                ("Campo di Marte Depot", 43.7820, 11.2820),
                ("Rifredi Depot", 43.7950, 11.2410),
                ("Novoli Depot", 43.7880, 11.2220),
                ("Gavinana Depot", 43.7520, 11.2680),
            ],
        }
    }

    pub fn visit_locations(&self) -> Vec<(&'static str, f64, f64, CustomerType)> {
        match self {
            DemoData::Philadelphia => philadelphia_visits(),
            DemoData::Hartford => hartford_visits(),
            DemoData::Firenze => firenze_visits(),
        }
    }
}

pub fn list_demo_data() -> Vec<&'static str> {
    vec!["PHILADELPHIA", "HARTFORT", "FIRENZE"]
}

pub fn generate(demo: DemoData) -> VehicleRoutePlan {
    let config = demo.config();
    let mut rng = StdRng::seed_from_u64(config.seed);

    let tomorrow = chrono::Local::now().date_naive() + TimeDelta::days(1);

    // Build coordinates
    let mut coordinates = Vec::new();
    let depots = demo.depot_locations();
    let visit_locs = demo.visit_locations();

    // Add depot coordinates
    for (_, lat, lng) in depots.iter().take(config.vehicle_count) {
        coordinates.push((*lat, *lng));
    }

    // Add visit coordinates (shuffled)
    let mut visit_indices: Vec<usize> = (0..visit_locs.len()).collect();
    visit_indices.shuffle(&mut rng);

    let depot_count = config.vehicle_count.min(depots.len());
    for &visit_idx in visit_indices.iter().take(config.visit_count) {
        let (_, lat, lng, _) = visit_locs[visit_idx];
        coordinates.push((lat, lng));
    }

    // Build vehicles
    let vehicles: Vec<Vehicle> = (0..config.vehicle_count)
        .map(|i| {
            let capacity = rng.gen_range(config.min_vehicle_capacity..=config.max_vehicle_capacity);
            Vehicle::new(
                i,
                i.to_string(),
                VEHICLE_NAMES[i % VEHICLE_NAMES.len()],
                capacity,
                i, // home_location_idx
                NaiveDateTime::new(tomorrow, config.vehicle_start_time),
            )
        })
        .collect();

    // Build visits
    let selected_visit_indices: Vec<usize> =
        visit_indices.into_iter().take(config.visit_count).collect();
    let visits: Vec<Visit> = (0..selected_visit_indices.len())
        .map(|i| {
            let visit_idx = selected_visit_indices[i];
            let (name, _, _, ctype) = visit_locs[visit_idx];
            let (min_demand, max_demand) = ctype.demand_range();
            let (min_service, max_service) = ctype.service_minutes_range();

            Visit::new(
                i.to_string(),
                name,
                depot_count + i, // location_idx
                rng.gen_range(min_demand..=max_demand),
                NaiveDateTime::new(tomorrow, ctype.window_start()),
                NaiveDateTime::new(tomorrow, ctype.window_end()),
                rng.gen_range(min_service..=max_service) * 60, // Convert to seconds
            )
        })
        .collect();

    VehicleRoutePlan::new(
        "demo",
        coordinates,
        vehicles,
        visits,
        config.south_west,
        config.north_east,
    )
}

fn philadelphia_visits() -> Vec<(&'static str, f64, f64, CustomerType)> {
    vec![
        // Restaurants
        (
            "Reading Terminal Market",
            39.9535,
            -75.1589,
            CustomerType::Restaurant,
        ),
        (
            "Parc Restaurant",
            39.9493,
            -75.1727,
            CustomerType::Restaurant,
        ),
        ("Zahav", 39.9430, -75.1474, CustomerType::Restaurant),
        ("Vetri Cucina", 39.9499, -75.1659, CustomerType::Restaurant),
        (
            "Talula's Garden",
            39.9470,
            -75.1709,
            CustomerType::Restaurant,
        ),
        ("Fork", 39.9493, -75.1539, CustomerType::Restaurant),
        ("Morimoto", 39.9488, -75.1559, CustomerType::Restaurant),
        (
            "Vernick Food & Drink",
            39.9508,
            -75.1718,
            CustomerType::Restaurant,
        ),
        (
            "Friday Saturday Sunday",
            39.9492,
            -75.1715,
            CustomerType::Restaurant,
        ),
        ("Royal Izakaya", 39.9410, -75.1509, CustomerType::Restaurant),
        ("Laurel", 39.9392, -75.1538, CustomerType::Restaurant),
        (
            "Marigold Kitchen",
            39.9533,
            -75.1920,
            CustomerType::Restaurant,
        ),
        // Businesses
        ("Comcast Center", 39.9543, -75.1690, CustomerType::Business),
        ("Liberty Place", 39.9520, -75.1685, CustomerType::Business),
        (
            "BNY Mellon Center",
            39.9505,
            -75.1660,
            CustomerType::Business,
        ),
        (
            "One Liberty Place",
            39.9520,
            -75.1685,
            CustomerType::Business,
        ),
        ("Aramark Tower", 39.9550, -75.1705, CustomerType::Business),
        ("PSFS Building", 39.9510, -75.1618, CustomerType::Business),
        (
            "Three Logan Square",
            39.9567,
            -75.1720,
            CustomerType::Business,
        ),
        (
            "Two Commerce Square",
            39.9551,
            -75.1675,
            CustomerType::Business,
        ),
        ("Penn Medicine", 39.9495, -75.1935, CustomerType::Business),
        (
            "Children's Hospital",
            39.9482,
            -75.1950,
            CustomerType::Business,
        ),
        (
            "Drexel University",
            39.9566,
            -75.1899,
            CustomerType::Business,
        ),
        (
            "Temple University",
            39.9812,
            -75.1554,
            CustomerType::Business,
        ),
        (
            "Jefferson Hospital",
            39.9487,
            -75.1577,
            CustomerType::Business,
        ),
        (
            "Pennsylvania Hospital",
            39.9445,
            -75.1545,
            CustomerType::Business,
        ),
        ("FMC Tower", 39.9499, -75.1780, CustomerType::Business),
        ("Cira Centre", 39.9560, -75.1822, CustomerType::Business),
        // Residential
        (
            "Rittenhouse Square",
            39.9496,
            -75.1718,
            CustomerType::Residential,
        ),
        (
            "Washington Square West",
            39.9468,
            -75.1545,
            CustomerType::Residential,
        ),
        ("Society Hill", 39.9425, -75.1478, CustomerType::Residential),
        ("Old City", 39.9510, -75.1450, CustomerType::Residential),
        (
            "Northern Liberties",
            39.9650,
            -75.1420,
            CustomerType::Residential,
        ),
        ("Fishtown", 39.9712, -75.1340, CustomerType::Residential),
        (
            "Queen Village",
            39.9380,
            -75.1520,
            CustomerType::Residential,
        ),
        ("Bella Vista", 39.9395, -75.1598, CustomerType::Residential),
        (
            "Graduate Hospital",
            39.9425,
            -75.1768,
            CustomerType::Residential,
        ),
        ("Fairmount", 39.9680, -75.1750, CustomerType::Residential),
        (
            "Spring Garden",
            39.9620,
            -75.1620,
            CustomerType::Residential,
        ),
        (
            "Art Museum Area",
            39.9656,
            -75.1810,
            CustomerType::Residential,
        ),
        ("Brewerytown", 39.9750, -75.1850, CustomerType::Residential),
        (
            "East Passyunk",
            39.9310,
            -75.1605,
            CustomerType::Residential,
        ),
        ("Point Breeze", 39.9285, -75.1780, CustomerType::Residential),
        ("Pennsport", 39.9320, -75.1450, CustomerType::Residential),
        (
            "Powelton Village",
            39.9610,
            -75.1950,
            CustomerType::Residential,
        ),
        ("Spruce Hill", 39.9530, -75.2100, CustomerType::Residential),
        ("Cedar Park", 39.9490, -75.2200, CustomerType::Residential),
        ("Kensington", 39.9850, -75.1280, CustomerType::Residential),
        (
            "Port Richmond",
            39.9870,
            -75.1120,
            CustomerType::Residential,
        ),
    ]
}

fn hartford_visits() -> Vec<(&'static str, f64, f64, CustomerType)> {
    vec![
        // Restaurants
        ("Max Downtown", 41.7670, -72.6730, CustomerType::Restaurant),
        (
            "Trumbull Kitchen",
            41.7650,
            -72.6750,
            CustomerType::Restaurant,
        ),
        ("Salute", 41.7630, -72.6740, CustomerType::Restaurant),
        (
            "Peppercorns Grill",
            41.7690,
            -72.6680,
            CustomerType::Restaurant,
        ),
        (
            "Feng Asian Bistro",
            41.7640,
            -72.6725,
            CustomerType::Restaurant,
        ),
        ("On20", 41.7655, -72.6728, CustomerType::Restaurant),
        (
            "First and Last Tavern",
            41.7620,
            -72.7050,
            CustomerType::Restaurant,
        ),
        ("Agave Grill", 41.7580, -72.6820, CustomerType::Restaurant),
        (
            "Bear's Smokehouse",
            41.7550,
            -72.6780,
            CustomerType::Restaurant,
        ),
        (
            "City Steam Brewery",
            41.7630,
            -72.6750,
            CustomerType::Restaurant,
        ),
        // Businesses
        ("Travelers Tower", 41.7658, -72.6734, CustomerType::Business),
        (
            "Hartford Steam Boiler",
            41.7680,
            -72.6700,
            CustomerType::Business,
        ),
        ("Aetna Building", 41.7700, -72.6900, CustomerType::Business),
        (
            "Connecticut Convention Center",
            41.7615,
            -72.6820,
            CustomerType::Business,
        ),
        (
            "Hartford Hospital",
            41.7547,
            -72.6858,
            CustomerType::Business,
        ),
        (
            "Connecticut Children's",
            41.7560,
            -72.6850,
            CustomerType::Business,
        ),
        ("Trinity College", 41.7474, -72.6909, CustomerType::Business),
        (
            "Connecticut Science Center",
            41.7650,
            -72.6695,
            CustomerType::Business,
        ),
        // Residential
        (
            "West End Hartford",
            41.7680,
            -72.7000,
            CustomerType::Residential,
        ),
        ("Asylum Hill", 41.7720, -72.6850, CustomerType::Residential),
        ("Frog Hollow", 41.7580, -72.6900, CustomerType::Residential),
        ("Barry Square", 41.7450, -72.6800, CustomerType::Residential),
        ("South End", 41.7400, -72.6750, CustomerType::Residential),
        ("Blue Hills", 41.7850, -72.7050, CustomerType::Residential),
        ("Parkville", 41.7650, -72.7100, CustomerType::Residential),
        (
            "Behind the Rocks",
            41.7550,
            -72.7050,
            CustomerType::Residential,
        ),
        ("Charter Oak", 41.7495, -72.6650, CustomerType::Residential),
        (
            "Sheldon Charter Oak",
            41.7510,
            -72.6700,
            CustomerType::Residential,
        ),
        ("Clay Arsenal", 41.7750, -72.6850, CustomerType::Residential),
        ("Upper Albany", 41.7780, -72.6950, CustomerType::Residential),
    ]
}

fn firenze_visits() -> Vec<(&'static str, f64, f64, CustomerType)> {
    vec![
        // Restaurants
        (
            "Trattoria Mario",
            43.7750,
            11.2530,
            CustomerType::Restaurant,
        ),
        ("Buca Mario", 43.7698, 11.2505, CustomerType::Restaurant),
        ("Il Latini", 43.7705, 11.2495, CustomerType::Restaurant),
        (
            "Osteria dell'Enoteca",
            43.7680,
            11.2545,
            CustomerType::Restaurant,
        ),
        (
            "Trattoria Sostanza",
            43.7735,
            11.2470,
            CustomerType::Restaurant,
        ),
        (
            "All'Antico Vinaio",
            43.7690,
            11.2570,
            CustomerType::Restaurant,
        ),
        (
            "Mercato Centrale",
            43.7762,
            11.2540,
            CustomerType::Restaurant,
        ),
        ("Cibreo", 43.7702, 11.2670, CustomerType::Restaurant),
        ("Ora d'Aria", 43.7710, 11.2610, CustomerType::Restaurant),
        ("Buca Lapi", 43.7720, 11.2535, CustomerType::Restaurant),
        ("Il Palagio", 43.7680, 11.2550, CustomerType::Restaurant),
        (
            "Enoteca Pinchiorri",
            43.7695,
            11.2620,
            CustomerType::Restaurant,
        ),
        ("La Giostra", 43.7745, 11.2650, CustomerType::Restaurant),
        ("Fishing Lab", 43.7730, 11.2560, CustomerType::Restaurant),
        (
            "Trattoria Cammillo",
            43.7665,
            11.2520,
            CustomerType::Restaurant,
        ),
        // Businesses
        ("Palazzo Vecchio", 43.7693, 11.2563, CustomerType::Business),
        ("Uffizi Gallery", 43.7677, 11.2553, CustomerType::Business),
        ("Gucci Garden", 43.7692, 11.2556, CustomerType::Business),
        ("Ferragamo Museum", 43.7700, 11.2530, CustomerType::Business),
        (
            "Ospedale Santa Maria",
            43.7830,
            11.2690,
            CustomerType::Business,
        ),
        (
            "Universita degli Studi",
            43.7765,
            11.2555,
            CustomerType::Business,
        ),
        ("Palazzo Strozzi", 43.7706, 11.2515, CustomerType::Business),
        (
            "Biblioteca Nazionale",
            43.7660,
            11.2650,
            CustomerType::Business,
        ),
        (
            "Teatro del Maggio",
            43.7780,
            11.2470,
            CustomerType::Business,
        ),
        ("Palazzo Pitti", 43.7650, 11.2500, CustomerType::Business),
        (
            "Accademia Gallery",
            43.7768,
            11.2590,
            CustomerType::Business,
        ),
        ("Ospedale Meyer", 43.7910, 11.2520, CustomerType::Business),
        (
            "Polo Universitario",
            43.7920,
            11.2180,
            CustomerType::Business,
        ),
        // Residential
        ("Santo Spirito", 43.7665, 11.2470, CustomerType::Residential),
        ("San Frediano", 43.7680, 11.2420, CustomerType::Residential),
        ("Santa Croce", 43.7688, 11.2620, CustomerType::Residential),
        ("San Lorenzo", 43.7755, 11.2540, CustomerType::Residential),
        ("San Marco", 43.7780, 11.2585, CustomerType::Residential),
        ("Sant'Ambrogio", 43.7705, 11.2680, CustomerType::Residential),
        (
            "Campo di Marte",
            43.7820,
            11.2820,
            CustomerType::Residential,
        ),
        ("Novoli", 43.7880, 11.2220, CustomerType::Residential),
        ("Rifredi", 43.7950, 11.2410, CustomerType::Residential),
        ("Le Cure", 43.7890, 11.2580, CustomerType::Residential),
        ("Careggi", 43.8020, 11.2530, CustomerType::Residential),
        ("Peretola", 43.7960, 11.2050, CustomerType::Residential),
        ("Isolotto", 43.7620, 11.2200, CustomerType::Residential),
        ("Gavinana", 43.7520, 11.2680, CustomerType::Residential),
        ("Galluzzo", 43.7400, 11.2480, CustomerType::Residential),
        ("Porta Romana", 43.7610, 11.2560, CustomerType::Residential),
        ("Bellosguardo", 43.7650, 11.2350, CustomerType::Residential),
        ("Arcetri", 43.7500, 11.2530, CustomerType::Residential),
        ("Fiesole", 43.8055, 11.2935, CustomerType::Residential),
        ("Settignano", 43.7850, 11.3100, CustomerType::Residential),
    ]
}
