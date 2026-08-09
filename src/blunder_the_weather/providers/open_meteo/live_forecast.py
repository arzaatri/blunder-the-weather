"""LiveForecastProvider backed by Open-Meteo's operational Forecast API."""

from datetime import date

import requests

from blunder_the_weather.geo.grids import GridPoint
from blunder_the_weather.providers.base import ForecastRecord
from blunder_the_weather.providers.open_meteo.client import DEFAULT_TIMEOUT_SECONDS, build_session
from blunder_the_weather.providers.open_meteo.mappings import assert_point_alignment, parse_live_forecast

_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_DAILY_VARS = (
    "temperature_2m_max,temperature_2m_min,cloud_cover_mean,"
    "relative_humidity_2m_mean,precipitation_probability_max"
)
_FORECAST_DAYS = 7  # matches our 7-day lead horizon


class OpenMeteoLiveForecastProvider:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or build_session()

    def fetch_raw(self, points: list[GridPoint]) -> list[dict]:
        """Raw per-point response entries from the live Forecast API, aligned with `points`."""
        response = self._session.get(
            _BASE_URL,
            params={
                "latitude": ",".join(str(p.lat) for p in points),
                "longitude": ",".join(str(p.lon) for p in points),
                "daily": _DAILY_VARS,
                "forecast_days": _FORECAST_DAYS,
                "timezone": "UTC",
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    def get_live_forecast(self, points: list[GridPoint], issued_date: date) -> list[ForecastRecord]:
        raw_entries = self.fetch_raw(points)
        assert_point_alignment(raw_entries, points)
        return [
            record
            for point, entry in zip(points, raw_entries)
            for record in parse_live_forecast(entry["daily"], point, issued_date)
        ]
