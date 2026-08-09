"""Registry of cities in scope, loaded from config/cities.yaml. Adding a city is one
entry in that file -- everything downstream (grid generation, providers, storage)
picks it up automatically."""

from pathlib import Path

import yaml

from blunder_the_weather.config import REPO_ROOT
from blunder_the_weather.geo.grids import City, GridPoint, make_grid

CITIES_CONFIG_PATH = REPO_ROOT / "config" / "cities.yaml"


def _load_cities(path: Path = CITIES_CONFIG_PATH) -> list[City]:
    with path.open() as f:
        raw = yaml.safe_load(f)
    return [City.model_validate(entry) for entry in raw["cities"]]


CITIES: list[City] = _load_cities()


def all_cities() -> list[City]:
    return CITIES


def get_city(city_id: str) -> City:
    for city in CITIES:
        if city.city_id == city_id:
            return city
    raise KeyError(f"Unknown city_id: {city_id}")


def all_grid_points() -> list[GridPoint]:
    return [point for city in CITIES for point in make_grid(city)]
