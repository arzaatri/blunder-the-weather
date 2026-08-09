"""Small S3 read/write helpers shared by bronze/silver Dagster assets, so each asset
function is just "fetch or parse, then one of these" rather than repeating
boto3/serialization boilerplate."""

import io
import json
from pathlib import Path

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


def put_bytes(s3: S3Resource, key: str, data: bytes) -> None:
    s3.get_client().put_object(Bucket=bucket_name(), Key=key, Body=data)


def get_bytes(s3: S3Resource, key: str) -> bytes:
    return s3.get_client().get_object(Bucket=bucket_name(), Key=key)["Body"].read()


def upload_dir_to_s3(s3: S3Resource, local_dir: Path, s3_prefix: str) -> None:
    """Uploads every file directly under local_dir (non-recursive) to s3_prefix/<filename> --
    used for model artifact directories (model.save() writes several small files)."""
    for file in local_dir.iterdir():
        put_bytes(s3, f"{s3_prefix}/{file.name}", file.read_bytes())


def download_dir_from_s3(s3: S3Resource, s3_prefix: str, local_dir: Path) -> None:
    client = s3.get_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name(), Prefix=f"{s3_prefix}/"):
        for obj in page.get("Contents", []):
            filename = obj["Key"].rsplit("/", 1)[-1]
            (local_dir / filename).write_bytes(get_bytes(s3, obj["Key"]))
