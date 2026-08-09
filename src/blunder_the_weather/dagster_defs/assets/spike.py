"""Phase 0 throwaway asset: proves the whole storage chain works end to end
(Docker -> MinIO -> dagster-aws S3Resource -> Parquet write -> DuckDB httpfs read-back)
before any real pipeline logic is built on top of it. Safe to delete once Phase 2 lands.
"""

import io

import pandas as pd
from dagster import AssetExecutionContext, MaterializeResult, asset
from dagster_aws.s3 import S3Resource

from blunder_the_weather.lakehouse.duckdb_query import get_connection
from blunder_the_weather.lakehouse.paths import bucket_name, s3_uri


@asset
def roundtrip_check(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    """Write a tiny table to MinIO as Parquet, read it back via DuckDB, and confirm it matches."""
    written = pd.DataFrame({"id": [1, 2, 3], "label": ["a", "b", "c"]})

    buffer = io.BytesIO()
    written.to_parquet(buffer, index=False)

    key = "_spike/roundtrip_check.parquet"
    s3.get_client().put_object(Bucket=bucket_name(), Key=key, Body=buffer.getvalue())
    context.log.info(f"Wrote {len(written)} rows to {s3_uri(key)}")

    connection = get_connection()
    read_back = connection.execute(f"SELECT * FROM read_parquet('{s3_uri(key)}') ORDER BY id").df()

    if not written.equals(read_back):
        raise ValueError(f"Round-trip mismatch: wrote {written.to_dict()} but read {read_back.to_dict()}")

    context.log.info("Round-trip check passed: MinIO + DuckDB httpfs chain is working.")
    return MaterializeResult(metadata={"rows": len(read_back)})
