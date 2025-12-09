from typing import Generator, TypeVar, Sequence
from datetime import date, datetime, time, timedelta
from enum import Enum
from random import Random
from dataclasses import dataclass

from .domain import Location, Vehicle, VehicleRoutePlan, Visit


FIRST_NAMES = ("Amy", "Beth", "Carl", "Dan", "Elsa", "Flo", "Gus", "Hugo", "Ivy", "Jay")
LAST_NAMES = ("Cole", "Fox", "Green", "Jones", "King", "Li", "Poe", "Rye", "Smith", "Watt")

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
    PHILADELPHIA = _DemoDataProperties(0, 55, 6, time(6, 0),
                                       15, 30,
                                       Location(latitude=39.7656099067391,
                                                longitude=-76.83782328143754),
                                       Location(latitude=40.77636644354855,
                                                longitude=-74.9300739430771))

    HARTFORT = _DemoDataProperties(1, 50, 6, time(6, 0),
                                   20, 30,
                                   Location(latitude=41.48366520850297,
                                            longitude=-73.15901689943055),
                                   Location(latitude=41.99512052869307,
                                            longitude=-72.25114548877427))

    FIRENZE = _DemoDataProperties(2, 77, 6, time(6, 0),
                                  20, 40,
                                  Location(latitude=43.751466,
                                           longitude=11.177210),
                                  Location(latitude=43.809291,
                                           longitude=11.290195))


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
    Generate demo data for vehicle routing.

    Creates a realistic delivery scenario with three customer types:
    - Residential (50%): Evening windows (17:00-20:00), small orders (1-2 units)
    - Business (30%): Business hours (09:00-17:00), medium orders (3-6 units)
    - Restaurant (20%): Early morning (06:00-10:00), large orders (5-10 units)

    Args:
        demo_data_enum: The demo data configuration to use
    """
    name = "demo"
    demo_data = demo_data_enum.value
    random = Random(demo_data.seed)
    latitudes = doubles(random, demo_data.south_west_corner.latitude, demo_data.north_east_corner.latitude)
    longitudes = doubles(random, demo_data.south_west_corner.longitude, demo_data.north_east_corner.longitude)

    vehicle_capacities = ints(random, demo_data.min_vehicle_capacity,
                              demo_data.max_vehicle_capacity + 1)

    vehicles = [Vehicle(id=str(i),
                        name=VEHICLE_NAMES[i % len(VEHICLE_NAMES)],
                        capacity=next(vehicle_capacities),
                        home_location=Location(
                            latitude=next(latitudes),
                            longitude=next(longitudes)),
                        departure_time=datetime.combine(
                            date.today() + timedelta(days=1), demo_data.vehicle_start_time)
                        )
                for i in range(demo_data.vehicle_count)]

    names = generate_names(random)
    tomorrow = date.today() + timedelta(days=1)

    visits = []
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

    return VehicleRoutePlan(name=name,
                            south_west_corner=demo_data.south_west_corner,
                            north_east_corner=demo_data.north_east_corner,
                            vehicles=vehicles,
                            visits=visits)


def tomorrow_at(local_time: time) -> datetime:
    return datetime.combine(date.today(), local_time)
