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
    level: str = "INFO"


class AppConfig(BaseModel):
    minio: MinioConfig
    logging: LoggingConfig = LoggingConfig()

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
