"""ActualsProvider backed by Open-Meteo's Historical Weather API (ERA5 reanalysis)."""

from datetime import date

import requests

from blunder_the_weather.geo.grids import GridPoint
from blunder_the_weather.providers.base import ActualObservation
from blunder_the_weather.providers.open_meteo.client import DEFAULT_TIMEOUT_SECONDS, build_session
from blunder_the_weather.providers.open_meteo.mappings import assert_point_alignment, parse_actuals

_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
_DAILY_VARS = "temperature_2m_max,temperature_2m_min,cloud_cover_mean,relative_humidity_2m_mean,precipitation_sum"


class OpenMeteoActualsProvider:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or build_session()

    def fetch_raw(self, points: list[GridPoint], start_date: date, end_date: date) -> list[dict]:
        """Raw per-point response entries from the Historical Weather API, aligned with `points`.
        This is what bronze-layer assets land as-is; silver assets parse it via mappings.py."""
        response = self._session.get(
            _BASE_URL,
            params={
                "latitude": ",".join(str(p.lat) for p in points),
                "longitude": ",".join(str(p.lon) for p in points),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": _DAILY_VARS,
                "timezone": "UTC",
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    def get_actuals(self, points: list[GridPoint], start_date: date, end_date: date) -> list[ActualObservation]:
        raw_entries = self.fetch_raw(points, start_date, end_date)
        assert_point_alignment(raw_entries, points)
        return [obs for point, entry in zip(points, raw_entries) for obs in parse_actuals(entry["daily"], point)]
