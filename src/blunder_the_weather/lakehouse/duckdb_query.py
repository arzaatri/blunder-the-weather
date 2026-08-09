"""Ephemeral DuckDB query engine over the MinIO-backed lakehouse.

There is deliberately no persisted .duckdb file: every caller (the dashboard, ad hoc
gold reads, Dagster assets that need to query what they just wrote) opens a fresh
in-memory connection configured for the MinIO S3 endpoint via httpfs. This avoids any
single-writer file-locking concerns, since DuckDB never owns durable state here --
MinIO does.
"""

import duckdb

from blunder_the_weather.config import load_config, load_secrets


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection ready to read/write s3://<bucket>/... paths
    on the local MinIO instance. Open one of these per query rather than holding it long-lived."""
    config = load_config()
    secrets = load_secrets()
    endpoint = config.minio.endpoint_url.removeprefix("http://").removeprefix("https://")

    connection = duckdb.connect(database=":memory:")
    connection.execute("INSTALL httpfs; LOAD httpfs;")
    connection.execute(
        f"""
        CREATE OR REPLACE SECRET minio (
            TYPE s3,
            KEY_ID '{secrets.minio_root_user}',
            SECRET '{secrets.minio_root_password}',
            ENDPOINT '{endpoint}',
            URL_STYLE 'path',
            USE_SSL false
        )
        """
    )
    return connection
