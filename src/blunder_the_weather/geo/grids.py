"""City and grid-point definitions, and a simple lat/lon grid generator.

Each city is represented by an odd-sized (default 3x3) grid of points spaced evenly
around its center, rather than a single point -- this preserves real geographic signal
for the model and sets up the future map-based dashboard view.
"""

import math

from pydantic import BaseModel


class City(BaseModel):
    city_id: str
    name: str
    center_lat: float
    center_lon: float


class GridPoint(BaseModel):
    point_id: str
    city_id: str
    lat: float
    lon: float


_KM_PER_DEGREE_LAT = 111.0


def make_grid(city: City, size: int = 3, spacing_km: float = 15.0) -> list[GridPoint]:
    """Generate a size x size grid of GridPoints centered on the city, spaced spacing_km
    apart in both directions. size must be odd so the grid has a point exactly at the
    city's center coordinate."""
    if size % 2 == 0:
        raise ValueError(f"grid size must be odd (got {size}) so the grid has a center point")

    half = size // 2
    lat_deg_per_km = 1 / _KM_PER_DEGREE_LAT
    lon_deg_per_km = 1 / (_KM_PER_DEGREE_LAT * math.cos(math.radians(city.center_lat)))

    points: list[GridPoint] = []
    for row in range(-half, half + 1):
        for col in range(-half, half + 1):
            lat = city.center_lat + row * spacing_km * lat_deg_per_km
            lon = city.center_lon + col * spacing_km * lon_deg_per_km
            point_id = f"{city.city_id}_{row + half}_{col + half}"
            points.append(GridPoint(point_id=point_id, city_id=city.city_id, lat=round(lat, 5), lon=round(lon, 5)))
    return points
