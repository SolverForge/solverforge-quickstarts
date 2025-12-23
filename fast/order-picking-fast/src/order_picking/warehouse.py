from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from .domain import Trolley


class Side(Enum):
    """Available shelving sides where products can be located."""
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class Column(Enum):
    """Defines the warehouse columns."""
    COL_A = 'A'
    COL_B = 'B'
    COL_C = 'C'
    COL_D = 'D'
    COL_E = 'E'


class Row(Enum):
    """Defines the warehouse rows."""
    ROW_1 = 1
    ROW_2 = 2
    ROW_3 = 3


@dataclass
class Shelving:
    """
    Represents a products container. Each shelving has two sides where
    products can be stored, and a number of rows.
    """
    id: str
    x: int  # Absolute x position of shelving's left bottom corner
    y: int  # Absolute y position of shelving's left bottom corner

    ROWS_SIZE: ClassVar[int] = 10


@dataclass
class WarehouseLocation:
    """
    Represents a location in the warehouse where a product can be stored.
    """
    shelving_id: str
    side: Side
    row: int

    def __str__(self) -> str:
        return f"WarehouseLocation(shelving={self.shelving_id}, side={self.side.name}, row={self.row})"


def new_shelving_id(column: Column, row: Row) -> str:
    """Create a shelving ID from column and row."""
    return f"({column.value},{row.value})"


# Warehouse constants
SHELVING_WIDTH = 2   # meters
SHELVING_HEIGHT = 10  # meters
SHELVING_PADDING = 3  # spacing between shelvings in meters

# Initialize static shelving map
SHELVING_MAP: dict[str, Shelving] = {}

def _init_shelving_map():
    """Initialize the warehouse shelving grid."""
    shelving_x = 0
    for col in Column:
        shelving_y = 0
        for row in Row:
            shelving_id = new_shelving_id(col, row)
            SHELVING_MAP[shelving_id] = Shelving(
                id=shelving_id,
                x=shelving_x,
                y=shelving_y
            )
            shelving_y += SHELVING_HEIGHT + SHELVING_PADDING
        shelving_x += SHELVING_WIDTH + SHELVING_PADDING

_init_shelving_map()


def get_absolute_x(shelving: Shelving, location: WarehouseLocation) -> int:
    """Calculate absolute X position of a location."""
    if location.side == Side.LEFT:
        return shelving.x
    else:
        return shelving.x + SHELVING_WIDTH


def get_absolute_y(shelving: Shelving, location: WarehouseLocation) -> int:
    """Calculate absolute Y position of a location."""
    return shelving.y + location.row


def calculate_best_y_distance_in_shelving_row(start_row: int, end_row: int) -> int:
    """Calculate the best Y distance when crossing a shelving."""
    north_direction = start_row + end_row
    south_direction = (SHELVING_HEIGHT - start_row) + (SHELVING_HEIGHT - end_row)
    return min(north_direction, south_direction)


def calculate_distance(start: WarehouseLocation, end: WarehouseLocation) -> int:
    """
    Calculate distance in meters between two locations considering warehouse structure.
    """
    start_shelving = SHELVING_MAP.get(start.shelving_id)
    if start_shelving is None:
        raise IndexError(f"Shelving: {start.shelving_id} was not found in current Warehouse structure.")

    end_shelving = SHELVING_MAP.get(end.shelving_id)
    if end_shelving is None:
        raise IndexError(f"Shelving: {end.shelving_id} was not found in current Warehouse structure.")

    delta_x = 0

    start_x = get_absolute_x(start_shelving, start)
    start_y = get_absolute_y(start_shelving, start)
    end_x = get_absolute_x(end_shelving, end)
    end_y = get_absolute_y(end_shelving, end)

    if start_shelving == end_shelving:
        # Same shelving
        if start.side == end.side:
            # Same side - just vertical distance
            delta_y = abs(start_y - end_y)
        else:
            # Different side - calculate shortest walk around
            delta_x = SHELVING_WIDTH
            delta_y = calculate_best_y_distance_in_shelving_row(start.row, end.row)
    elif start_shelving.y == end_shelving.y:
        # Different shelvings but on same warehouse row
        if abs(start_x - end_x) == SHELVING_PADDING:
            # Neighbor shelvings with contiguous sides
            delta_x = SHELVING_PADDING
            delta_y = abs(start_y - end_y)
        else:
            # Other combinations in same warehouse row
            delta_x = abs(start_x - end_x)
            delta_y = calculate_best_y_distance_in_shelving_row(start.row, end.row)
    else:
        # Shelvings on different warehouse rows
        delta_x = abs(start_x - end_x)
        delta_y = abs(start_y - end_y)

    return delta_x + delta_y


def calculate_distance_to_travel(trolley: "Trolley") -> int:
    """Calculate total distance a trolley needs to travel through its steps."""
    distance = 0
    previous_location = trolley.location

    for step in trolley.steps:
        distance += calculate_distance(previous_location, step.location)
        previous_location = step.location

    # Return trip to origin
    distance += calculate_distance(previous_location, trolley.location)
    return distance
