"""Path helpers for the single-bucket medallion lakehouse (bronze/silver/gold/models prefixes)."""

from blunder_the_weather.config import load_config

BRONZE = "bronze"
SILVER = "silver"
GOLD = "gold"
MODELS = "models"


def bucket_name() -> str:
    return load_config().minio.bucket


def s3_uri(*parts: str) -> str:
    """Build an s3://bucket/part1/part2/... URI from path segments."""
    joined = "/".join(part.strip("/") for part in parts if part)
    return f"s3://{bucket_name()}/{joined}"
