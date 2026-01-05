from typing import Generator, TypeVar, Sequence, Optional
from datetime import date, datetime, time, timedelta
from enum import Enum
from random import Random
from dataclasses import dataclass, field

from .domain import Location, Vehicle, VehicleRoutePlan, Visit


FIRST_NAMES = ("Amy", "Beth", "Carl", "Dan", "Elsa", "Flo", "Gus", "Hugo", "Ivy", "Jay")
LAST_NAMES = ("Cole", "Fox", "Green", "Jones", "King", "Li", "Poe", "Rye", "Smith", "Watt")


# Real Philadelphia street addresses for demo data
# These are actual locations on the road network for realistic routing
PHILADELPHIA_REAL_LOCATIONS = {
    "depots": [
        {"name": "Central Depot - City Hall", "lat": 39.9526, "lng": -75.1652},
        {"name": "South Philly Depot", "lat": 39.9256, "lng": -75.1697},
        {"name": "University City Depot", "lat": 39.9522, "lng": -75.1932},
        {"name": "North Philly Depot", "lat": 39.9907, "lng": -75.1556},
        {"name": "Fishtown Depot", "lat": 39.9712, "lng": -75.1340},
        {"name": "West Philly Depot", "lat": 39.9601, "lng": -75.2175},
    ],
    "visits": [
        # Restaurants (for early morning deliveries)
        {"name": "Reading Terminal Market", "lat": 39.9535, "lng": -75.1589, "type": "RESTAURANT"},
        {"name": "Parc Restaurant", "lat": 39.9493, "lng": -75.1727, "type": "RESTAURANT"},
        {"name": "Zahav", "lat": 39.9430, "lng": -75.1474, "type": "RESTAURANT"},
        {"name": "Vetri Cucina", "lat": 39.9499, "lng": -75.1659, "type": "RESTAURANT"},
        {"name": "Talula's Garden", "lat": 39.9470, "lng": -75.1709, "type": "RESTAURANT"},
        {"name": "Fork", "lat": 39.9493, "lng": -75.1539, "type": "RESTAURANT"},
        {"name": "Morimoto", "lat": 39.9488, "lng": -75.1559, "type": "RESTAURANT"},
        {"name": "Vernick Food & Drink", "lat": 39.9508, "lng": -75.1718, "type": "RESTAURANT"},
        {"name": "Friday Saturday Sunday", "lat": 39.9492, "lng": -75.1715, "type": "RESTAURANT"},
        {"name": "Royal Izakaya", "lat": 39.9410, "lng": -75.1509, "type": "RESTAURANT"},
        {"name": "Laurel", "lat": 39.9392, "lng": -75.1538, "type": "RESTAURANT"},
        {"name": "Marigold Kitchen", "lat": 39.9533, "lng": -75.1920, "type": "RESTAURANT"},

        # Businesses (for business hours deliveries)
        {"name": "Comcast Center", "lat": 39.9543, "lng": -75.1690, "type": "BUSINESS"},
        {"name": "Liberty Place", "lat": 39.9520, "lng": -75.1685, "type": "BUSINESS"},
        {"name": "BNY Mellon Center", "lat": 39.9505, "lng": -75.1660, "type": "BUSINESS"},
        {"name": "One Liberty Place", "lat": 39.9520, "lng": -75.1685, "type": "BUSINESS"},
        {"name": "Aramark Tower", "lat": 39.9550, "lng": -75.1705, "type": "BUSINESS"},
        {"name": "PSFS Building", "lat": 39.9510, "lng": -75.1618, "type": "BUSINESS"},
        {"name": "Three Logan Square", "lat": 39.9567, "lng": -75.1720, "type": "BUSINESS"},
        {"name": "Two Commerce Square", "lat": 39.9551, "lng": -75.1675, "type": "BUSINESS"},
        {"name": "Penn Medicine", "lat": 39.9495, "lng": -75.1935, "type": "BUSINESS"},
        {"name": "Children's Hospital", "lat": 39.9482, "lng": -75.1950, "type": "BUSINESS"},
        {"name": "Drexel University", "lat": 39.9566, "lng": -75.1899, "type": "BUSINESS"},
        {"name": "Temple University", "lat": 39.9812, "lng": -75.1554, "type": "BUSINESS"},
        {"name": "Jefferson Hospital", "lat": 39.9487, "lng": -75.1577, "type": "BUSINESS"},
        {"name": "Pennsylvania Hospital", "lat": 39.9445, "lng": -75.1545, "type": "BUSINESS"},
        {"name": "FMC Tower", "lat": 39.9499, "lng": -75.1780, "type": "BUSINESS"},
        {"name": "Cira Centre", "lat": 39.9560, "lng": -75.1822, "type": "BUSINESS"},

        # Residential areas (for evening deliveries)
        {"name": "Rittenhouse Square", "lat": 39.9496, "lng": -75.1718, "type": "RESIDENTIAL"},
        {"name": "Washington Square West", "lat": 39.9468, "lng": -75.1545, "type": "RESIDENTIAL"},
        {"name": "Society Hill", "lat": 39.9425, "lng": -75.1478, "type": "RESIDENTIAL"},
        {"name": "Old City", "lat": 39.9510, "lng": -75.1450, "type": "RESIDENTIAL"},
        {"name": "Northern Liberties", "lat": 39.9650, "lng": -75.1420, "type": "RESIDENTIAL"},
        {"name": "Fishtown", "lat": 39.9712, "lng": -75.1340, "type": "RESIDENTIAL"},
        {"name": "Queen Village", "lat": 39.9380, "lng": -75.1520, "type": "RESIDENTIAL"},
        {"name": "Bella Vista", "lat": 39.9395, "lng": -75.1598, "type": "RESIDENTIAL"},
        {"name": "Graduate Hospital", "lat": 39.9425, "lng": -75.1768, "type": "RESIDENTIAL"},
        {"name": "Fairmount", "lat": 39.9680, "lng": -75.1750, "type": "RESIDENTIAL"},
        {"name": "Spring Garden", "lat": 39.9620, "lng": -75.1620, "type": "RESIDENTIAL"},
        {"name": "Art Museum Area", "lat": 39.9656, "lng": -75.1810, "type": "RESIDENTIAL"},
        {"name": "Brewerytown", "lat": 39.9750, "lng": -75.1850, "type": "RESIDENTIAL"},
        {"name": "East Passyunk", "lat": 39.9310, "lng": -75.1605, "type": "RESIDENTIAL"},
        {"name": "Point Breeze", "lat": 39.9285, "lng": -75.1780, "type": "RESIDENTIAL"},
        {"name": "Pennsport", "lat": 39.9320, "lng": -75.1450, "type": "RESIDENTIAL"},
        {"name": "Powelton Village", "lat": 39.9610, "lng": -75.1950, "type": "RESIDENTIAL"},
        {"name": "Spruce Hill", "lat": 39.9530, "lng": -75.2100, "type": "RESIDENTIAL"},
        {"name": "Cedar Park", "lat": 39.9490, "lng": -75.2200, "type": "RESIDENTIAL"},
        {"name": "Kensington", "lat": 39.9850, "lng": -75.1280, "type": "RESIDENTIAL"},
        {"name": "Port Richmond", "lat": 39.9870, "lng": -75.1120, "type": "RESIDENTIAL"},
        # Note: Removed distant locations (Manayunk, Roxborough, Chestnut Hill, Mount Airy, Germantown)
        # to keep the bounding box compact for faster OSMnx downloads
    ],
}

# Hartford real locations
HARTFORD_REAL_LOCATIONS = {
    "depots": [
        {"name": "Downtown Hartford Depot", "lat": 41.7658, "lng": -72.6734},
        {"name": "Asylum Hill Depot", "lat": 41.7700, "lng": -72.6900},
        {"name": "South End Depot", "lat": 41.7400, "lng": -72.6750},
        {"name": "West End Depot", "lat": 41.7680, "lng": -72.7100},
        {"name": "Barry Square Depot", "lat": 41.7450, "lng": -72.6800},
        {"name": "Clay Arsenal Depot", "lat": 41.7750, "lng": -72.6850},
    ],
    "visits": [
        # Restaurants
        {"name": "Max Downtown", "lat": 41.7670, "lng": -72.6730, "type": "RESTAURANT"},
        {"name": "Trumbull Kitchen", "lat": 41.7650, "lng": -72.6750, "type": "RESTAURANT"},
        {"name": "Salute", "lat": 41.7630, "lng": -72.6740, "type": "RESTAURANT"},
        {"name": "Peppercorns Grill", "lat": 41.7690, "lng": -72.6680, "type": "RESTAURANT"},
        {"name": "Feng Asian Bistro", "lat": 41.7640, "lng": -72.6725, "type": "RESTAURANT"},
        {"name": "On20", "lat": 41.7655, "lng": -72.6728, "type": "RESTAURANT"},
        {"name": "First and Last Tavern", "lat": 41.7620, "lng": -72.7050, "type": "RESTAURANT"},
        {"name": "Agave Grill", "lat": 41.7580, "lng": -72.6820, "type": "RESTAURANT"},
        {"name": "Bear's Smokehouse", "lat": 41.7550, "lng": -72.6780, "type": "RESTAURANT"},
        {"name": "City Steam Brewery", "lat": 41.7630, "lng": -72.6750, "type": "RESTAURANT"},

        # Businesses
        {"name": "Travelers Tower", "lat": 41.7658, "lng": -72.6734, "type": "BUSINESS"},
        {"name": "Hartford Steam Boiler", "lat": 41.7680, "lng": -72.6700, "type": "BUSINESS"},
        {"name": "Aetna Building", "lat": 41.7700, "lng": -72.6900, "type": "BUSINESS"},
        {"name": "Connecticut Convention Center", "lat": 41.7615, "lng": -72.6820, "type": "BUSINESS"},
        {"name": "Hartford Hospital", "lat": 41.7547, "lng": -72.6858, "type": "BUSINESS"},
        {"name": "Connecticut Children's", "lat": 41.7560, "lng": -72.6850, "type": "BUSINESS"},
        {"name": "Trinity College", "lat": 41.7474, "lng": -72.6909, "type": "BUSINESS"},
        {"name": "Connecticut Science Center", "lat": 41.7650, "lng": -72.6695, "type": "BUSINESS"},

        # Residential
        {"name": "West End Hartford", "lat": 41.7680, "lng": -72.7000, "type": "RESIDENTIAL"},
        {"name": "Asylum Hill", "lat": 41.7720, "lng": -72.6850, "type": "RESIDENTIAL"},
        {"name": "Frog Hollow", "lat": 41.7580, "lng": -72.6900, "type": "RESIDENTIAL"},
        {"name": "Barry Square", "lat": 41.7450, "lng": -72.6800, "type": "RESIDENTIAL"},
        {"name": "South End", "lat": 41.7400, "lng": -72.6750, "type": "RESIDENTIAL"},
        {"name": "Blue Hills", "lat": 41.7850, "lng": -72.7050, "type": "RESIDENTIAL"},
        {"name": "Parkville", "lat": 41.7650, "lng": -72.7100, "type": "RESIDENTIAL"},
        {"name": "Behind the Rocks", "lat": 41.7550, "lng": -72.7050, "type": "RESIDENTIAL"},
        {"name": "Charter Oak", "lat": 41.7495, "lng": -72.6650, "type": "RESIDENTIAL"},
        {"name": "Sheldon Charter Oak", "lat": 41.7510, "lng": -72.6700, "type": "RESIDENTIAL"},
        {"name": "Clay Arsenal", "lat": 41.7750, "lng": -72.6850, "type": "RESIDENTIAL"},
        {"name": "Upper Albany", "lat": 41.7780, "lng": -72.6950, "type": "RESIDENTIAL"},
    ],
}

# Florence real locations
FIRENZE_REAL_LOCATIONS = {
    "depots": [
        {"name": "Centro Storico Depot", "lat": 43.7696, "lng": 11.2558},
        {"name": "Santa Maria Novella Depot", "lat": 43.7745, "lng": 11.2487},
        {"name": "Campo di Marte Depot", "lat": 43.7820, "lng": 11.2820},
        {"name": "Rifredi Depot", "lat": 43.7950, "lng": 11.2410},
        {"name": "Novoli Depot", "lat": 43.7880, "lng": 11.2220},
        {"name": "Gavinana Depot", "lat": 43.7520, "lng": 11.2680},
    ],
    "visits": [
        # Restaurants
        {"name": "Trattoria Mario", "lat": 43.7750, "lng": 11.2530, "type": "RESTAURANT"},
        {"name": "Buca Mario", "lat": 43.7698, "lng": 11.2505, "type": "RESTAURANT"},
        {"name": "Il Latini", "lat": 43.7705, "lng": 11.2495, "type": "RESTAURANT"},
        {"name": "Osteria dell'Enoteca", "lat": 43.7680, "lng": 11.2545, "type": "RESTAURANT"},
        {"name": "Trattoria Sostanza", "lat": 43.7735, "lng": 11.2470, "type": "RESTAURANT"},
        {"name": "All'Antico Vinaio", "lat": 43.7690, "lng": 11.2570, "type": "RESTAURANT"},
        {"name": "Mercato Centrale", "lat": 43.7762, "lng": 11.2540, "type": "RESTAURANT"},
        {"name": "Cibreo", "lat": 43.7702, "lng": 11.2670, "type": "RESTAURANT"},
        {"name": "Ora d'Aria", "lat": 43.7710, "lng": 11.2610, "type": "RESTAURANT"},
        {"name": "Buca Lapi", "lat": 43.7720, "lng": 11.2535, "type": "RESTAURANT"},
        {"name": "Il Palagio", "lat": 43.7680, "lng": 11.2550, "type": "RESTAURANT"},
        {"name": "Enoteca Pinchiorri", "lat": 43.7695, "lng": 11.2620, "type": "RESTAURANT"},
        {"name": "La Giostra", "lat": 43.7745, "lng": 11.2650, "type": "RESTAURANT"},
        {"name": "Fishing Lab", "lat": 43.7730, "lng": 11.2560, "type": "RESTAURANT"},
        {"name": "Trattoria Cammillo", "lat": 43.7665, "lng": 11.2520, "type": "RESTAURANT"},

        # Businesses
        {"name": "Palazzo Vecchio", "lat": 43.7693, "lng": 11.2563, "type": "BUSINESS"},
        {"name": "Uffizi Gallery", "lat": 43.7677, "lng": 11.2553, "type": "BUSINESS"},
        {"name": "Gucci Garden", "lat": 43.7692, "lng": 11.2556, "type": "BUSINESS"},
        {"name": "Ferragamo Museum", "lat": 43.7700, "lng": 11.2530, "type": "BUSINESS"},
        {"name": "Ospedale Santa Maria", "lat": 43.7830, "lng": 11.2690, "type": "BUSINESS"},
        {"name": "Universita degli Studi", "lat": 43.7765, "lng": 11.2555, "type": "BUSINESS"},
        {"name": "Palazzo Strozzi", "lat": 43.7706, "lng": 11.2515, "type": "BUSINESS"},
        {"name": "Biblioteca Nazionale", "lat": 43.7660, "lng": 11.2650, "type": "BUSINESS"},
        {"name": "Teatro del Maggio", "lat": 43.7780, "lng": 11.2470, "type": "BUSINESS"},
        {"name": "Palazzo Pitti", "lat": 43.7650, "lng": 11.2500, "type": "BUSINESS"},
        {"name": "Accademia Gallery", "lat": 43.7768, "lng": 11.2590, "type": "BUSINESS"},
        {"name": "Ospedale Meyer", "lat": 43.7910, "lng": 11.2520, "type": "BUSINESS"},
        {"name": "Polo Universitario", "lat": 43.7920, "lng": 11.2180, "type": "BUSINESS"},

        # Residential
        {"name": "Santo Spirito", "lat": 43.7665, "lng": 11.2470, "type": "RESIDENTIAL"},
        {"name": "San Frediano", "lat": 43.7680, "lng": 11.2420, "type": "RESIDENTIAL"},
        {"name": "Santa Croce", "lat": 43.7688, "lng": 11.2620, "type": "RESIDENTIAL"},
        {"name": "San Lorenzo", "lat": 43.7755, "lng": 11.2540, "type": "RESIDENTIAL"},
        {"name": "San Marco", "lat": 43.7780, "lng": 11.2585, "type": "RESIDENTIAL"},
        {"name": "Sant'Ambrogio", "lat": 43.7705, "lng": 11.2680, "type": "RESIDENTIAL"},
        {"name": "Campo di Marte", "lat": 43.7820, "lng": 11.2820, "type": "RESIDENTIAL"},
        {"name": "Novoli", "lat": 43.7880, "lng": 11.2220, "type": "RESIDENTIAL"},
        {"name": "Rifredi", "lat": 43.7950, "lng": 11.2410, "type": "RESIDENTIAL"},
        {"name": "Le Cure", "lat": 43.7890, "lng": 11.2580, "type": "RESIDENTIAL"},
        {"name": "Careggi", "lat": 43.8020, "lng": 11.2530, "type": "RESIDENTIAL"},
        {"name": "Peretola", "lat": 43.7960, "lng": 11.2050, "type": "RESIDENTIAL"},
        {"name": "Isolotto", "lat": 43.7620, "lng": 11.2200, "type": "RESIDENTIAL"},
        {"name": "Gavinana", "lat": 43.7520, "lng": 11.2680, "type": "RESIDENTIAL"},
        {"name": "Galluzzo", "lat": 43.7400, "lng": 11.2480, "type": "RESIDENTIAL"},
        {"name": "Porta Romana", "lat": 43.7610, "lng": 11.2560, "type": "RESIDENTIAL"},
        {"name": "Bellosguardo", "lat": 43.7650, "lng": 11.2350, "type": "RESIDENTIAL"},
        {"name": "Arcetri", "lat": 43.7500, "lng": 11.2530, "type": "RESIDENTIAL"},
        {"name": "Fiesole", "lat": 43.8055, "lng": 11.2935, "type": "RESIDENTIAL"},
        {"name": "Settignano", "lat": 43.7850, "lng": 11.3100, "type": "RESIDENTIAL"},
    ],
}

# Map demo data enum names to their real location data
REAL_LOCATION_DATA = {
    "PHILADELPHIA": PHILADELPHIA_REAL_LOCATIONS,
    "HARTFORT": HARTFORD_REAL_LOCATIONS,
    "FIRENZE": FIRENZE_REAL_LOCATIONS,
}

# Vehicle names using phonetic alphabet for clear identification
VEHICLE_NAMES = ("Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet")


class CustomerType(Enum):
    """
    Customer types with realistic time windows, demand patterns, and service durations.

    Each customer type reflects real-world delivery scenarios:
    - RESIDENTIAL: Evening deliveries when people are home from work (5-10 min unload)
    - BUSINESS: Standard business hours with larger orders (15-30 min unload, paperwork)
    - RESTAURANT: Early morning before lunch prep rush (20-40 min for bulk unload, inspection)
    """
    # (label, window_start, window_end, min_demand, max_demand, min_service_min, max_service_min)
    RESIDENTIAL = ("residential", time(17, 0), time(20, 0), 1, 2, 5, 10)
    BUSINESS = ("business", time(9, 0), time(17, 0), 3, 6, 15, 30)
    RESTAURANT = ("restaurant", time(6, 0), time(10, 0), 5, 10, 20, 40)

    def __init__(self, label: str, window_start: time, window_end: time,
                 min_demand: int, max_demand: int, min_service_minutes: int, max_service_minutes: int):
        self.label = label
        self.window_start = window_start
        self.window_end = window_end
        self.min_demand = min_demand
        self.max_demand = max_demand
        self.min_service_minutes = min_service_minutes
        self.max_service_minutes = max_service_minutes


# Weighted distribution: 50% residential, 30% business, 20% restaurant
CUSTOMER_TYPE_WEIGHTS = [
    (CustomerType.RESIDENTIAL, 50),
    (CustomerType.BUSINESS, 30),
    (CustomerType.RESTAURANT, 20),
]


def random_customer_type(random: Random) -> CustomerType:
    """Weighted random selection of customer type."""
    total = sum(w for _, w in CUSTOMER_TYPE_WEIGHTS)
    r = random.randint(1, total)
    cumulative = 0
    for ctype, weight in CUSTOMER_TYPE_WEIGHTS:
        cumulative += weight
        if r <= cumulative:
            return ctype
    return CustomerType.RESIDENTIAL  # fallback


@dataclass
class _DemoDataProperties:
    seed: int
    visit_count: int
    vehicle_count: int
    vehicle_start_time: time
    min_vehicle_capacity: int
    max_vehicle_capacity: int
    south_west_corner: Location
    north_east_corner: Location

    def __post_init__(self):
        if self.min_vehicle_capacity < 1:
            raise ValueError(f"Number of minVehicleCapacity ({self.min_vehicle_capacity}) must be greater than zero.")
        if self.max_vehicle_capacity < 1:
            raise ValueError(f"Number of maxVehicleCapacity ({self.max_vehicle_capacity}) must be greater than zero.")
        if self.min_vehicle_capacity >= self.max_vehicle_capacity:
            raise ValueError(f"maxVehicleCapacity ({self.max_vehicle_capacity}) must be greater than "
                             f"minVehicleCapacity ({self.min_vehicle_capacity}).")
        if self.visit_count < 1:
            raise ValueError(f"Number of visitCount ({self.visit_count}) must be greater than zero.")
        if self.vehicle_count < 1:
            raise ValueError(f"Number of vehicleCount ({self.vehicle_count}) must be greater than zero.")
        if self.north_east_corner.latitude <= self.south_west_corner.latitude:
            raise ValueError(f"northEastCorner.getLatitude ({self.north_east_corner.latitude}) must be greater than "
                             f"southWestCorner.getLatitude({self.south_west_corner.latitude}).")
        if self.north_east_corner.longitude <= self.south_west_corner.longitude:
            raise ValueError(f"northEastCorner.getLongitude ({self.north_east_corner.longitude}) must be greater than "
                             f"southWestCorner.getLongitude({self.south_west_corner.longitude}).")


class DemoData(Enum):
    # Bounding boxes tightened to ~5x5 km around actual location data
    # for faster OSMnx network downloads (smaller area = faster download)

    # Philadelphia: Center City area (~39.92 to 39.99 lat, -75.22 to -75.11 lng)
    PHILADELPHIA = _DemoDataProperties(0, 55, 6, time(6, 0),
                                       15, 30,
                                       Location(latitude=39.92,
                                                longitude=-75.23),
                                       Location(latitude=40.00,
                                                longitude=-75.11))

    # Hartford: Downtown area (~41.69 to 41.79 lat, -72.75 to -72.60 lng)
    HARTFORT = _DemoDataProperties(1, 50, 6, time(6, 0),
                                   20, 30,
                                   Location(latitude=41.69,
                                            longitude=-72.75),
                                   Location(latitude=41.79,
                                            longitude=-72.60))

    # Firenze: Historic center area
    FIRENZE = _DemoDataProperties(2, 77, 6, time(6, 0),
                                  20, 40,
                                  Location(latitude=43.73,
                                           longitude=11.17),
                                  Location(latitude=43.81,
                                           longitude=11.32))


def doubles(random: Random, start: float, end: float) -> Generator[float, None, None]:
    while True:
        yield random.uniform(start, end)


def ints(random: Random, start: int, end: int) -> Generator[int, None, None]:
    while True:
        yield random.randrange(start, end)


T = TypeVar('T')


def values(random: Random, sequence: Sequence[T]) -> Generator[T, None, None]:
    start = 0
    end = len(sequence) - 1
    while True:
        yield sequence[random.randint(start, end)]


def generate_names(random: Random) -> Generator[str, None, None]:
    while True:
        yield f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'


def generate_demo_data(demo_data_enum: DemoData) -> VehicleRoutePlan:
    """
    Generate demo data for vehicle routing using real street addresses.

    Uses actual locations on the road network for realistic routing:
    - Residential (50%): Evening windows (17:00-20:00), small orders (1-2 units)
    - Business (30%): Business hours (09:00-17:00), medium orders (3-6 units)
    - Restaurant (20%): Early morning (06:00-10:00), large orders (5-10 units)

    Args:
        demo_data_enum: The demo data configuration to use
    """
    name = "demo"
    demo_data = demo_data_enum.value
    random = Random(demo_data.seed)

    # Get real location data for this demo
    real_locations = REAL_LOCATION_DATA.get(demo_data_enum.name)

    vehicle_capacities = ints(random, demo_data.min_vehicle_capacity,
                              demo_data.max_vehicle_capacity + 1)

    if real_locations:
        # Use real depot locations
        depot_locations = real_locations["depots"]
        vehicles = []
        for i in range(demo_data.vehicle_count):
            depot = depot_locations[i % len(depot_locations)]
            vehicles.append(
                Vehicle(
                    id=str(i),
                    name=VEHICLE_NAMES[i % len(VEHICLE_NAMES)],
                    capacity=next(vehicle_capacities),
                    home_location=Location(latitude=depot["lat"], longitude=depot["lng"]),
                    departure_time=datetime.combine(
                        date.today() + timedelta(days=1), demo_data.vehicle_start_time
                    ),
                )
            )
    else:
        # Fallback to random locations within bounding box
        latitudes = doubles(random, demo_data.south_west_corner.latitude, demo_data.north_east_corner.latitude)
        longitudes = doubles(random, demo_data.south_west_corner.longitude, demo_data.north_east_corner.longitude)
        vehicles = [
            Vehicle(
                id=str(i),
                name=VEHICLE_NAMES[i % len(VEHICLE_NAMES)],
                capacity=next(vehicle_capacities),
                home_location=Location(latitude=next(latitudes), longitude=next(longitudes)),
                departure_time=datetime.combine(
                    date.today() + timedelta(days=1), demo_data.vehicle_start_time
                ),
            )
            for i in range(demo_data.vehicle_count)
        ]

    tomorrow = date.today() + timedelta(days=1)
    visits = []

    if real_locations:
        # Use real visit locations with their actual types
        visit_locations = real_locations["visits"]
        # Shuffle to get variety, but use seed for reproducibility
        shuffled_visits = list(visit_locations)
        random.shuffle(shuffled_visits)

        for i in range(min(demo_data.visit_count, len(shuffled_visits))):
            loc_data = shuffled_visits[i]
            # Get customer type from location data
            ctype_name = loc_data.get("type", "RESIDENTIAL")
            ctype = CustomerType[ctype_name]
            service_minutes = random.randint(ctype.min_service_minutes, ctype.max_service_minutes)

            visits.append(
                Visit(
                    id=str(i),
                    name=loc_data["name"],
                    location=Location(latitude=loc_data["lat"], longitude=loc_data["lng"]),
                    demand=random.randint(ctype.min_demand, ctype.max_demand),
                    min_start_time=datetime.combine(tomorrow, ctype.window_start),
                    max_end_time=datetime.combine(tomorrow, ctype.window_end),
                    service_duration=timedelta(minutes=service_minutes),
                )
            )

        # If we need more visits than we have real locations, generate additional random ones
        if demo_data.visit_count > len(shuffled_visits):
            names = generate_names(random)
            latitudes = doubles(random, demo_data.south_west_corner.latitude, demo_data.north_east_corner.latitude)
            longitudes = doubles(random, demo_data.south_west_corner.longitude, demo_data.north_east_corner.longitude)

            for i in range(len(shuffled_visits), demo_data.visit_count):
                ctype = random_customer_type(random)
                service_minutes = random.randint(ctype.min_service_minutes, ctype.max_service_minutes)
                visits.append(
                    Visit(
                        id=str(i),
                        name=next(names),
                        location=Location(latitude=next(latitudes), longitude=next(longitudes)),
                        demand=random.randint(ctype.min_demand, ctype.max_demand),
                        min_start_time=datetime.combine(tomorrow, ctype.window_start),
                        max_end_time=datetime.combine(tomorrow, ctype.window_end),
                        service_duration=timedelta(minutes=service_minutes),
                    )
                )
    else:
        # Fallback to fully random locations
        names = generate_names(random)
        latitudes = doubles(random, demo_data.south_west_corner.latitude, demo_data.north_east_corner.latitude)
        longitudes = doubles(random, demo_data.south_west_corner.longitude, demo_data.north_east_corner.longitude)

        for i in range(demo_data.visit_count):
            ctype = random_customer_type(random)
            service_minutes = random.randint(ctype.min_service_minutes, ctype.max_service_minutes)
            visits.append(
                Visit(
                    id=str(i),
                    name=next(names),
                    location=Location(latitude=next(latitudes), longitude=next(longitudes)),
                    demand=random.randint(ctype.min_demand, ctype.max_demand),
                    min_start_time=datetime.combine(tomorrow, ctype.window_start),
                    max_end_time=datetime.combine(tomorrow, ctype.window_end),
                    service_duration=timedelta(minutes=service_minutes),
                )
            )

    return VehicleRoutePlan(
        name=name,
        south_west_corner=demo_data.south_west_corner,
        north_east_corner=demo_data.north_east_corner,
        vehicles=vehicles,
        visits=visits,
    )


def tomorrow_at(local_time: time) -> datetime:
    return datetime.combine(date.today(), local_time)
