"""Canonical schemas and provider role interfaces.

Everything downstream of ingestion (labeling, features, storage, models) codes against
ActualObservation/ForecastRecord and the three Protocols below -- never against raw
Open-Meteo JSON. This is the seam that lets the historical-forecast, live-forecast, and
actuals data sources be swapped independently later.
"""

from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel

from blunder_the_weather.geo.grids import GridPoint

ForecastSource = Literal["previous_runs_backfill", "live_daily"]

# The Previous Runs API only reconstructs lead 1-7 (lead 0 is the current run, not a
# forecast made in advance); this is the shared default across providers/assets.
DEFAULT_LEAD_DAYS = list(range(1, 8))


class ActualObservation(BaseModel):
    """A single day's observed actuals at one grid point."""

    point_id: str
    date: date
    temp_max: float
    temp_min: float
    cloud_cover_mean: float
    humidity_mean: float
    precip_sum: float  # mm; used only to derive the binary "did it rain" ground truth


class ForecastRecord(BaseModel):
    """A forecast for one (point, valid_date) issued at a given lead time, regardless
    of whether it came from the historical-forecast provider or the live provider."""

    point_id: str
    valid_date: date
    lead_days: int
    issued_date: date
    temp_max: float
    temp_min: float
    cloud_cover_mean: float
    humidity_mean: float
    # Forecast probability of precipitation, 0-100. Nullable: the Previous Runs API's
    # archive of this variable starts later than the other three (confirmed via spike --
    # null before ~2024-09, populated by 2025-01), so older backfilled rows may lack it.
    precip_chance: float | None
    source: ForecastSource


class ActualsProvider(Protocol):
    def get_actuals(self, points: list[GridPoint], start_date: date, end_date: date) -> list[ActualObservation]: ...


class HistoricalForecastProvider(Protocol):
    def get_historical_forecasts(
        self, points: list[GridPoint], start_date: date, end_date: date, lead_days: list[int]
    ) -> list[ForecastRecord]: ...


class LiveForecastProvider(Protocol):
    def get_live_forecast(self, points: list[GridPoint], issued_date: date) -> list[ForecastRecord]: ...
