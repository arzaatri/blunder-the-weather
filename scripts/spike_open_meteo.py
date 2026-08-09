"""Phase 0 spike: verify the real behavior of the three Open-Meteo APIs this project
depends on, before writing providers/open_meteo/mappings.py against anything but
reality. Run manually (`uv run python scripts/spike_open_meteo.py`); not part of the
pipeline, safe to delete once Phase 2 providers are built and tested against fixtures.

Checks:
  1. Historical Weather API -- what daily variable names are actually valid for actuals.
  2. Previous Runs API -- confirms _previous_dayN lead-time reconstruction works as documented.
  3. Previous Runs API -- whether multi-location (comma-separated lat/lon) requests are supported
     (undocumented; the plan's Phase 2 batching strategy depends on the answer).
  4. Live Forecast API -- today's operational forecast shape.
"""

import requests

NYC = (40.7128, -74.0060)
SF = (37.7749, -122.4194)

HISTORICAL_WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
LIVE_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _get(url: str, params: dict) -> requests.Response:
    return requests.get(url, params=params, timeout=30)


def spike_historical_actuals() -> None:
    print("\n=== 1. Historical Weather API (actuals) ===")
    response = _get(
        HISTORICAL_WEATHER_URL,
        {
            "latitude": NYC[0],
            "longitude": NYC[1],
            "start_date": "2024-06-01",
            "end_date": "2024-06-03",
            "daily": "temperature_2m_max,temperature_2m_min,cloud_cover_mean,"
            "relative_humidity_2m_mean,precipitation_sum",
            "timezone": "America/New_York",
        },
    )
    print("Status:", response.status_code)
    if not response.ok:
        print("Response body (likely lists valid variable names):", response.text[:1000])
        return
    data = response.json()
    print("Daily keys returned:", list(data["daily"].keys()))
    print("Sample values:", {k: v[:3] for k, v in data["daily"].items()})


def spike_previous_runs_single_location() -> None:
    print("\n=== 2. Previous Runs API (lead-time reconstruction, single location) ===")
    response = _get(
        PREVIOUS_RUNS_URL,
        {
            "latitude": NYC[0],
            "longitude": NYC[1],
            "start_date": "2024-06-01",
            "end_date": "2024-06-03",
            "daily": ",".join(f"temperature_2m_max_previous_day{d}" for d in range(8)),
            "timezone": "America/New_York",
        },
    )
    print("Status:", response.status_code)
    if not response.ok:
        print("Response body:", response.text[:1000])
        return
    data = response.json()
    print("Daily keys returned:", list(data["daily"].keys()))
    print("Row 0 across leads:", {k: v[0] for k, v in data["daily"].items()})


def spike_previous_runs_multi_location() -> None:
    print("\n=== 3. Previous Runs API (multi-location support -- undocumented, checking) ===")
    response = _get(
        PREVIOUS_RUNS_URL,
        {
            "latitude": f"{NYC[0]},{SF[0]}",
            "longitude": f"{NYC[1]},{SF[1]}",
            "start_date": "2024-06-01",
            "end_date": "2024-06-01",
            "daily": "temperature_2m_max_previous_day1",
            "timezone": "auto",
        },
    )
    print("Status:", response.status_code)
    if not response.ok:
        print("Multi-location request failed -- fall back to per-point sequential calls.")
        print("Response body:", response.text[:1000])
        return
    data = response.json()
    is_multi = isinstance(data, list)
    print("Multi-location supported (response is a JSON list):", is_multi)
    print("Response:", data)


def spike_live_forecast() -> None:
    print("\n=== 4. Live Forecast API ===")
    response = _get(
        LIVE_FORECAST_URL,
        {
            "latitude": NYC[0],
            "longitude": NYC[1],
            "daily": "temperature_2m_max,temperature_2m_min,cloud_cover_mean,"
            "relative_humidity_2m_mean,precipitation_probability_max",
            "forecast_days": 7,
            "timezone": "America/New_York",
        },
    )
    print("Status:", response.status_code)
    if not response.ok:
        print("Response body (likely lists valid variable names):", response.text[:1000])
        return
    data = response.json()
    print("Daily keys returned:", list(data["daily"].keys()))
    print("Values:", data["daily"])


if __name__ == "__main__":
    spike_historical_actuals()
    spike_previous_runs_single_location()
    spike_previous_runs_multi_location()
    spike_live_forecast()
