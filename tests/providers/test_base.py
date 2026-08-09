from datetime import date

import pytest
from pydantic import ValidationError

from blunder_the_weather.providers.base import ActualObservation, ForecastRecord


def test_actual_observation_accepts_valid_data() -> None:
    obs = ActualObservation(
        point_id="nyc_1_1",
        date=date(2024, 6, 1),
        temp_max=28.2,
        temp_min=13.2,
        cloud_cover_mean=17.0,
        humidity_mean=45.0,
        precip_sum=0.0,
    )
    assert obs.point_id == "nyc_1_1"


def test_actual_observation_rejects_missing_field() -> None:
    with pytest.raises(ValidationError):
        ActualObservation(
            point_id="nyc_1_1",
            date=date(2024, 6, 1),
            temp_max=28.2,
            temp_min=13.2,
            cloud_cover_mean=17.0,
            humidity_mean=45.0,
        )  # missing precip_sum


def test_forecast_record_accepts_valid_data() -> None:
    record = ForecastRecord(
        point_id="nyc_1_1",
        valid_date=date(2024, 6, 5),
        lead_days=4,
        issued_date=date(2024, 6, 1),
        temp_max=27.0,
        temp_min=14.0,
        cloud_cover_mean=40.0,
        humidity_mean=55.0,
        precip_chance=20.0,
        source="previous_runs_backfill",
    )
    assert record.lead_days == 4


def test_forecast_record_rejects_invalid_source() -> None:
    with pytest.raises(ValidationError):
        ForecastRecord(
            point_id="nyc_1_1",
            valid_date=date(2024, 6, 5),
            lead_days=4,
            issued_date=date(2024, 6, 1),
            temp_max=27.0,
            temp_min=14.0,
            cloud_cover_mean=40.0,
            humidity_mean=55.0,
            precip_chance=20.0,
            source="not_a_real_source",
        )
