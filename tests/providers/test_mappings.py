from datetime import date

import pytest

from blunder_the_weather.geo.grids import GridPoint
from blunder_the_weather.providers.open_meteo.mappings import (
    assert_point_alignment,
    parse_actuals,
    parse_historical_forecast_range,
    parse_live_forecast,
)

NYC_POINT = GridPoint(point_id="nyc_1_1", city_id="nyc", lat=40.7128, lon=-74.0060)
SF_POINT = GridPoint(point_id="sf_1_1", city_id="sf", lat=37.7749, lon=-122.4194)


def test_parse_actuals_maps_fields_and_dates() -> None:
    daily = {
        "time": ["2024-06-01", "2024-06-02"],
        "temperature_2m_max": [28.2, 27.3],
        "temperature_2m_min": [13.2, 14.3],
        "cloud_cover_mean": [17, 93],
        "relative_humidity_2m_mean": [45, 56],
        "precipitation_sum": [0.0, 0.2],
    }
    observations = parse_actuals(daily, NYC_POINT)
    assert len(observations) == 2
    assert observations[0].point_id == "nyc_1_1"
    assert observations[0].date == date(2024, 6, 1)
    assert observations[0].temp_max == 28.2
    assert observations[1].precip_sum == 0.2


def test_parse_live_forecast_computes_lead_days() -> None:
    daily = {
        "time": ["2026-08-09", "2026-08-10", "2026-08-11"],
        "temperature_2m_max": [31.1, 34.5, 33.7],
        "temperature_2m_min": [22.1, 23.3, 21.9],
        "cloud_cover_mean": [33, 40, 40],
        "relative_humidity_2m_mean": [81, 69, 76],
        "precipitation_probability_max": [30, 2, 29],
    }
    issued_date = date(2026, 8, 9)
    records = parse_live_forecast(daily, NYC_POINT, issued_date)
    assert [r.lead_days for r in records] == [0, 1, 2]
    assert records[1].valid_date == date(2026, 8, 10)
    assert records[1].precip_chance == 2
    assert all(r.source == "live_daily" for r in records)


def test_parse_historical_forecast_range_aggregates_hourly_to_daily() -> None:
    # Two days worth of hourly data (24h each) for a single lead of 1.
    hourly = {
        "time": [f"2024-06-01T{h:02d}:00" for h in range(24)] + [f"2024-06-02T{h:02d}:00" for h in range(24)],
        "temperature_2m_previous_day1": [10.0 + h for h in range(24)] + [5.0 + h for h in range(24)],
        "cloud_cover_previous_day1": [50.0] * 24 + [20.0] * 24,
        "relative_humidity_2m_previous_day1": [60.0] * 24 + [70.0] * 24,
        "precipitation_probability_previous_day1": [10.0] * 12 + [None] * 12 + [None] * 24,
    }
    records = parse_historical_forecast_range(hourly, NYC_POINT, date(2024, 6, 1), date(2024, 6, 2), lead_days=[1])

    assert len(records) == 2  # 2 days x 1 lead
    day1, day2 = records
    assert day1.valid_date == date(2024, 6, 1)
    assert day1.issued_date == date(2024, 5, 31)  # valid_date - 1 lead day
    assert day1.temp_max == pytest.approx(33.0)  # 10.0 + 23
    assert day1.temp_min == pytest.approx(10.0)
    assert day1.cloud_cover_mean == pytest.approx(50.0)
    assert day1.humidity_mean == pytest.approx(60.0)
    assert day1.precip_chance == pytest.approx(10.0)  # only non-null values considered

    # Day 2 has no non-null precip_chance values at all -- must come through as None,
    # not a fabricated 0, since that's a real "no data" case per the Phase 0 spike finding.
    assert day2.precip_chance is None


def test_parse_historical_forecast_range_multiple_leads_per_day() -> None:
    hourly = {
        "time": [f"2024-06-01T{h:02d}:00" for h in range(24)],
        "temperature_2m_previous_day1": [10.0] * 24,
        "cloud_cover_previous_day1": [50.0] * 24,
        "relative_humidity_2m_previous_day1": [60.0] * 24,
        "precipitation_probability_previous_day1": [10.0] * 24,
        "temperature_2m_previous_day3": [20.0] * 24,
        "cloud_cover_previous_day3": [80.0] * 24,
        "relative_humidity_2m_previous_day3": [40.0] * 24,
        "precipitation_probability_previous_day3": [5.0] * 24,
    }
    records = parse_historical_forecast_range(hourly, NYC_POINT, date(2024, 6, 1), date(2024, 6, 1), lead_days=[1, 3])

    assert len(records) == 2
    lead1, lead3 = records
    assert lead1.lead_days == 1
    assert lead1.issued_date == date(2024, 5, 31)
    assert lead3.lead_days == 3
    assert lead3.issued_date == date(2024, 5, 29)
    assert lead3.temp_max == pytest.approx(20.0)


def test_assert_point_alignment_passes_for_matching_order() -> None:
    entries = [{"latitude": 40.71, "longitude": -74.0}, {"latitude": 37.77, "longitude": -122.42}]
    assert_point_alignment(entries, [NYC_POINT, SF_POINT])  # should not raise


def test_assert_point_alignment_raises_for_swapped_order() -> None:
    entries = [{"latitude": 37.77, "longitude": -122.42}, {"latitude": 40.71, "longitude": -74.0}]
    with pytest.raises(ValueError):
        assert_point_alignment(entries, [NYC_POINT, SF_POINT])


def test_assert_point_alignment_raises_for_wrong_count() -> None:
    entries = [{"latitude": 40.71, "longitude": -74.0}]
    with pytest.raises(ValueError):
        assert_point_alignment(entries, [NYC_POINT, SF_POINT])
