"""HistoricalForecastProvider backed by Open-Meteo's Previous Runs API.

Confirmed via the Phase 0 spike: `{var}_previous_dayN` lead-time reconstruction only
works on hourly variables, not daily aggregates -- so this provider fetches hourly data
and mappings.parse_historical_forecast_range() rolls it up to daily per lead.
"""

from datetime import date

import requests

from blunder_the_weather.geo.grids import GridPoint
from blunder_the_weather.providers.base import DEFAULT_LEAD_DAYS, ForecastRecord
from blunder_the_weather.providers.open_meteo.client import DEFAULT_TIMEOUT_SECONDS, build_session
from blunder_the_weather.providers.open_meteo.mappings import assert_point_alignment, parse_historical_forecast_range

_BASE_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
_BASE_HOURLY_VARS = ["temperature_2m", "cloud_cover", "relative_humidity_2m", "precipitation_probability"]


class OpenMeteoHistoricalForecastProvider:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or build_session()

    def fetch_raw(
        self, points: list[GridPoint], start_date: date, end_date: date, lead_days: list[int]
    ) -> list[dict]:
        """Raw per-point hourly response entries from the Previous Runs API, aligned with `points`."""
        hourly_vars = ",".join(f"{var}_previous_day{lead}" for var in _BASE_HOURLY_VARS for lead in lead_days)
        response = self._session.get(
            _BASE_URL,
            params={
                "latitude": ",".join(str(p.lat) for p in points),
                "longitude": ",".join(str(p.lon) for p in points),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "hourly": hourly_vars,
                "timezone": "UTC",
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    def get_historical_forecasts(
        self,
        points: list[GridPoint],
        start_date: date,
        end_date: date,
        lead_days: list[int] = DEFAULT_LEAD_DAYS,
    ) -> list[ForecastRecord]:
        raw_entries = self.fetch_raw(points, start_date, end_date, lead_days)
        assert_point_alignment(raw_entries, points)
        return [
            record
            for point, entry in zip(points, raw_entries)
            for record in parse_historical_forecast_range(entry["hourly"], point, start_date, end_date, lead_days)
        ]
