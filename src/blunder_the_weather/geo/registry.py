"""Registry of cities in scope, loaded from config/cities.yaml. Adding a city is one
entry in that file -- everything downstream (grid generation, providers, storage)
picks it up automatically."""

from pathlib import Path

import yaml

from blunder_the_weather.config import REPO_ROOT
from blunder_the_weather.geo.grids import City, GridPoint, make_grid

CITIES_CONFIG_PATH = REPO_ROOT / "config" / "cities.yaml"


def _load_raw(path: Path = CITIES_CONFIG_PATH) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


_raw = _load_raw()
CITIES: list[City] = [City.model_validate(entry) for entry in _raw["cities"]]
_GRID_SIZE: int = _raw["grid"]["size"]
_GRID_SPACING_KM: float = _raw["grid"]["spacing_km"]


def all_cities() -> list[City]:
    return CITIES


def get_city(city_id: str) -> City:
    for city in CITIES:
        if city.city_id == city_id:
            return city
    raise KeyError(f"Unknown city_id: {city_id}")


def all_grid_points() -> list[GridPoint]:
    return [point for city in CITIES for point in make_grid(city, size=_GRID_SIZE, spacing_km=_GRID_SPACING_KM)]
