import pytest

from blunder_the_weather.geo.registry import all_cities, all_grid_points, get_city


def test_all_cities_loads_expected_cities() -> None:
    city_ids = {c.city_id for c in all_cities()}
    assert city_ids == {"nyc", "sf", "chi"}


def test_all_grid_points_covers_every_city() -> None:
    points = all_grid_points()
    assert len(points) == 27  # 3 cities x default 3x3 grid
    assert {p.city_id for p in points} == {"nyc", "sf", "chi"}


def test_get_city_returns_matching_city() -> None:
    city = get_city("sf")
    assert city.name == "San Francisco"


def test_get_city_raises_for_unknown_id() -> None:
    with pytest.raises(KeyError):
        get_city("not_a_real_city")
