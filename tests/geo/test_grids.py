import pytest

from blunder_the_weather.geo.grids import City, make_grid

NYC = City(city_id="nyc", name="New York City", center_lat=40.7128, center_lon=-74.0060)


def test_make_grid_returns_size_squared_points() -> None:
    points = make_grid(NYC, size=3, spacing_km=15.0)
    assert len(points) == 9


def test_make_grid_point_ids_are_unique() -> None:
    points = make_grid(NYC, size=3, spacing_km=15.0)
    assert len({p.point_id for p in points}) == len(points)


def test_make_grid_center_point_matches_city_center() -> None:
    points = make_grid(NYC, size=3, spacing_km=15.0)
    center = next(p for p in points if p.point_id == "nyc_1_1")
    assert center.lat == pytest.approx(NYC.center_lat)
    assert center.lon == pytest.approx(NYC.center_lon)


def test_make_grid_points_carry_city_id() -> None:
    points = make_grid(NYC, size=3, spacing_km=15.0)
    assert all(p.city_id == "nyc" for p in points)


def test_make_grid_rejects_even_size() -> None:
    with pytest.raises(ValueError):
        make_grid(NYC, size=4)


def test_make_grid_spacing_scales_extent() -> None:
    tight = make_grid(NYC, size=3, spacing_km=5.0)
    wide = make_grid(NYC, size=3, spacing_km=50.0)
    tight_lat_span = max(p.lat for p in tight) - min(p.lat for p in tight)
    wide_lat_span = max(p.lat for p in wide) - min(p.lat for p in wide)
    assert wide_lat_span > tight_lat_span
