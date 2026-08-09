"""Small S3 read/write helpers shared by bronze/silver Dagster assets, so each asset
function is just "fetch or parse, then one of these" rather than repeating
boto3/serialization boilerplate."""

import io
import json

import pandas as pd
from dagster_aws.s3 import S3Resource

from blunder_the_weather.lakehouse.paths import bucket_name


def put_json(s3: S3Resource, key: str, data: object) -> None:
    s3.get_client().put_object(Bucket=bucket_name(), Key=key, Body=json.dumps(data).encode())


def get_json(s3: S3Resource, key: str) -> object:
    body = s3.get_client().get_object(Bucket=bucket_name(), Key=key)["Body"].read()
    return json.loads(body)


def put_parquet(s3: S3Resource, key: str, df: pd.DataFrame) -> None:
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    s3.get_client().put_object(Bucket=bucket_name(), Key=key, Body=buffer.getvalue())
