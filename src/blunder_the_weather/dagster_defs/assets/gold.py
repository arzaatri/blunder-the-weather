"""Gold-layer assets: dbt models (silver -> gold), exposed as Dagster assets so the
lineage graph spans both the Python-based bronze/silver ingestion and the dbt-based
transformation in one connected DAG.
"""

import json
from collections.abc import Mapping
from typing import Any

from dagster import AssetExecutionContext
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from blunder_the_weather.config import load_config
from blunder_the_weather.dagster_defs.assets.silver import silver_actuals, silver_forecasts
from blunder_the_weather.dagster_defs.dbt_project import dbt_project

_SOURCE_TABLE_TO_ASSET = {
    "actuals": silver_actuals.key,
    "forecasts": silver_forecasts.key,
}


class BlunderDbtTranslator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]):
        if dbt_resource_props["resource_type"] == "source":
            mapped = _SOURCE_TABLE_TO_ASSET.get(dbt_resource_props["name"])
            if mapped is not None:
                return mapped
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=BlunderDbtTranslator())
def blunder_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    thresholds = load_config().thresholds
    dbt_vars = {
        "temp_max_threshold": thresholds.temp_max_celsius,
        "temp_min_threshold": thresholds.temp_min_celsius,
        "cloud_cover_threshold": thresholds.cloud_cover_pp,
        "humidity_threshold": thresholds.humidity_pp,
        "precip_chance_cutoff": thresholds.precip_chance_cutoff_pct,
    }
    yield from dbt.cli(["build", "--vars", json.dumps(dbt_vars)], context=context).stream()
