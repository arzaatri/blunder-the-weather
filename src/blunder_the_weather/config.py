"""Application configuration.

Non-secret, structural config (endpoints, bucket names, feature toggles) lives in
config/app.yaml and is safe to commit. Secrets (credentials) live in .env, which is
gitignored, and are loaded separately via pydantic-settings.
"""

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "app.yaml"
ENV_PATH = REPO_ROOT / ".env"
LOG_DIR = REPO_ROOT / "logs"


class MinioConfig(BaseModel):
    endpoint_url: str
    bucket: str


class LoggingConfig(BaseModel):
    level: str


class ProvidersConfig(BaseModel):
    """Which concrete provider fills each role. Each role is independently swappable --
    changing one is a config edit, not a code change, as long as a matching class is
    registered in providers/factory.py."""

    actuals: str
    historical_forecast: str
    live_forecast: str


class BackfillConfig(BaseModel):
    """start_date is a fixed anchor (not "today - N days") so the partition set only
    grows -- it never silently drops the earliest historical partitions as time passes,
    which would happen if the start point kept sliding forward with "today". end_lag_days
    accounts for data-availability lag confirmed via the Phase 0 spike (both APIs were
    current as of yesterday, but a small buffer is safer); the newest valid partition is
    always "today - end_lag_days", computed dynamically (see dagster_defs/partitions.py)
    so it keeps advancing without needing a code/config change or a process restart."""

    start_date: date
    end_lag_days: int


class ThresholdsConfig(BaseModel):
    """"Significant error" cutoffs per dimension. Temps are Celsius (Open-Meteo default,
    confirmed against real backfilled data -- NYC/SF/Chicago August values land in
    13-33 range). precip_chance is binarized rather than diffed (see mappings)."""

    temp_max_celsius: float
    temp_min_celsius: float
    cloud_cover_pp: float
    humidity_pp: float
    precip_chance_cutoff_pct: float


class ModelsConfig(BaseModel):
    """Training hyperparameters shared by all dimension models. holdout_frac is the
    fraction of distinct valid_dates held out for time-based evaluation; calib_fraction
    is the fraction of the remaining training rows carved out (randomly) to fit
    calibration -- see models/linear.py."""

    holdout_frac: float
    calib_fraction: float
    class_weight: str
    random_state: int


class LiveConfig(BaseModel):
    """start_date anchors the live-scoring partition set (dagster_defs/partitions.py's
    LIVE_PARTITIONS), same fixed-anchor pattern as BackfillConfig.start_date -- it's
    the day live scoring started, not something that should ever move. Unlike backfill,
    there's no end_lag: a live forecast is scored the same day it's issued."""

    start_date: date


class EnsembleConfig(BaseModel):
    """Per-dimension weights for combining the 5 models' calibrated probabilities into
    one volatility score (models/ensemble.py). Normalized internally, so these are
    relative weights, not required to sum to 1."""

    weights: dict[str, float]


class DashboardConfig(BaseModel):
    """city_aggregation controls how the 9 grid points per city are collapsed to one
    city-level number for display -- models/scoring still runs at grid-point
    granularity underneath, this only affects the dashboard's summary view."""

    city_aggregation: Literal["mean", "max"]


class AppConfig(BaseModel):
    # No field defaults here on purpose: every value must come from config/app.yaml so
    # there is one source of truth, not code defaults that can silently drift from it.
    minio: MinioConfig
    logging: LoggingConfig
    providers: ProvidersConfig
    backfill: BackfillConfig
    thresholds: ThresholdsConfig
    models: ModelsConfig
    live: LiveConfig
    ensemble: EnsembleConfig
    dashboard: DashboardConfig

    @classmethod
    def from_yaml(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        with path.open() as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        return cls.model_validate(raw)


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="ignore")

    minio_root_user: str
    minio_root_password: str


def load_config() -> AppConfig:
    return AppConfig.from_yaml()


def load_secrets() -> Secrets:
    return Secrets()
