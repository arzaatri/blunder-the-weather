"""Translates each Open-Meteo endpoint's raw response shape and variable-name spelling
into the canonical ActualObservation/ForecastRecord schemas. This is the one place that
absorbs the fact that the three endpoints don't share one naming convention (daily
aggregates for two of them, `{var}_previous_dayN` hourly series for the third), so an
upstream API change surfaces here first.
"""

from datetime import date, timedelta
from statistics import mean

from blunder_the_weather.geo.grids import GridPoint
from blunder_the_weather.providers.base import ActualObservation, ForecastRecord

# Above observed grid-snap noise (~0.1 deg worst case), below our ~25km point spacing.
_POINT_ALIGNMENT_TOLERANCE_DEGREES = 0.15


def assert_point_alignment(raw_entries: list[dict], points: list[GridPoint]) -> None:
    """Guard against a multi-location response silently coming back in a different
    order than requested -- mixing up which row belongs to which point would corrupt
    everything downstream without ever raising an obvious error."""
    if len(raw_entries) != len(points):
        raise ValueError(f"Expected {len(points)} response entries, got {len(raw_entries)}")
    for point, entry in zip(points, raw_entries):
        lat_diff = abs(entry["latitude"] - point.lat)
        lon_diff = abs(entry["longitude"] - point.lon)
        if lat_diff > _POINT_ALIGNMENT_TOLERANCE_DEGREES or lon_diff > _POINT_ALIGNMENT_TOLERANCE_DEGREES:
            raise ValueError(
                f"Response entry ({entry['latitude']}, {entry['longitude']}) does not match "
                f"expected point {point.point_id} ({point.lat}, {point.lon}) -- possible ordering bug"
            )


def parse_actuals(daily: dict, point: GridPoint) -> list[ActualObservation]:
    """daily: the "daily" dict from one Historical Weather API response entry."""
    return [
        ActualObservation(
            point_id=point.point_id,
            date=date.fromisoformat(day),
            temp_max=daily["temperature_2m_max"][i],
            temp_min=daily["temperature_2m_min"][i],
            cloud_cover_mean=daily["cloud_cover_mean"][i],
            humidity_mean=daily["relative_humidity_2m_mean"][i],
            precip_sum=daily["precipitation_sum"][i],
        )
        for i, day in enumerate(daily["time"])
    ]


def parse_live_forecast(daily: dict, point: GridPoint, issued_date: date) -> list[ForecastRecord]:
    """daily: the "daily" dict from one live Forecast API response entry."""
    records = []
    for i, day in enumerate(daily["time"]):
        valid_date = date.fromisoformat(day)
        records.append(
            ForecastRecord(
                point_id=point.point_id,
                valid_date=valid_date,
                lead_days=(valid_date - issued_date).days,
                issued_date=issued_date,
                temp_max=daily["temperature_2m_max"][i],
                temp_min=daily["temperature_2m_min"][i],
                cloud_cover_mean=daily["cloud_cover_mean"][i],
                humidity_mean=daily["relative_humidity_2m_mean"][i],
                precip_chance=daily["precipitation_probability_max"][i],
                source="live_daily",
            )
        )
    return records


def parse_historical_forecast_range(
    hourly: dict, point: GridPoint, start_date: date, end_date: date, lead_days: list[int]
) -> list[ForecastRecord]:
    """hourly: the "hourly" dict from one Previous Runs API response entry, spanning
    start_date..end_date at hourly resolution with `{var}_previous_day{N}` columns for
    each requested lead. Aggregates each day's 24 hours down to the canonical daily
    fields (max for temp-max/precip-chance, min for temp-min, mean for cloud/humidity)."""
    num_days = (end_date - start_date).days + 1
    records = []
    for day_offset in range(num_days):
        valid_date = start_date + timedelta(days=day_offset)
        hours = slice(day_offset * 24, (day_offset + 1) * 24)
        for lead in lead_days:
            precip_values = [v for v in hourly[f"precipitation_probability_previous_day{lead}"][hours] if v is not None]
            records.append(
                ForecastRecord(
                    point_id=point.point_id,
                    valid_date=valid_date,
                    lead_days=lead,
                    issued_date=valid_date - timedelta(days=lead),
                    temp_max=max(hourly[f"temperature_2m_previous_day{lead}"][hours]),
                    temp_min=min(hourly[f"temperature_2m_previous_day{lead}"][hours]),
                    cloud_cover_mean=mean(hourly[f"cloud_cover_previous_day{lead}"][hours]),
                    humidity_mean=mean(hourly[f"relative_humidity_2m_previous_day{lead}"][hours]),
                    precip_chance=(max(precip_values) if precip_values else None),
                    source="previous_runs_backfill",
                )
            )
    return records
