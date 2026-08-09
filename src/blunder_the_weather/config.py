"""Application configuration.

Non-secret, structural config (endpoints, bucket names, feature toggles) lives in
config/app.yaml and is safe to commit. Secrets (credentials) live in .env, which is
gitignored, and are loaded separately via pydantic-settings.
"""

from pathlib import Path
from typing import Any

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
    """Backfill window, expressed relative to "today" rather than fixed dates so it
    doesn't go stale. end_lag_days accounts for data-availability lag confirmed via the
    Phase 0 spike (both APIs were current as of yesterday, but a small buffer is safer)."""

    lookback_days: int
    end_lag_days: int


class ThresholdsConfig(BaseModel):
    """"Significant error" cutoffs per dimension. Temps are Celsius (Open-Meteo default,
    confirmed against real backfilled data -- NYC/SF/Chicago August values land in
    13-33 range). precip_chance is binarized rather than diffed (see mappings)."""

    temp_max_celsius: float
    cloud_cover_pp: float
    humidity_pp: float
    precip_chance_cutoff_pct: float


class AppConfig(BaseModel):
    # No field defaults here on purpose: every value must come from config/app.yaml so
    # there is one source of truth, not code defaults that can silently drift from it.
    minio: MinioConfig
    logging: LoggingConfig
    providers: ProvidersConfig
    backfill: BackfillConfig
    thresholds: ThresholdsConfig

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
