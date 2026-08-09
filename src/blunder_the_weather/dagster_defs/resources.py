"""Dagster resources shared across assets/jobs."""

from dagster import EnvVar
from dagster_aws.s3 import S3Resource

from blunder_the_weather.config import load_config


def build_s3_resource() -> S3Resource:
    """S3Resource pointed at the local MinIO endpoint. Swapping to real AWS S3 later
    is a matter of changing endpoint_url (and dropping use_ssl=False), not code."""
    config = load_config()
    return S3Resource(
        endpoint_url=config.minio.endpoint_url,
        aws_access_key_id=EnvVar("MINIO_ROOT_USER"),
        aws_secret_access_key=EnvVar("MINIO_ROOT_PASSWORD"),
        use_ssl=False,
    )
