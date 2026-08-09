"""Daily partitions covering the backfill window, computed relative to today (from
config/app.yaml's backfill.* settings) so the window doesn't go stale in code."""

from datetime import date, timedelta

from dagster import DailyPartitionsDefinition

from blunder_the_weather.config import load_config


def _build_backfill_partitions() -> DailyPartitionsDefinition:
    backfill_config = load_config().backfill
    start = date.today() - timedelta(days=backfill_config.lookback_days)
    end = date.today() - timedelta(days=backfill_config.end_lag_days)
    return DailyPartitionsDefinition(start_date=start.isoformat(), end_date=end.isoformat())


BACKFILL_PARTITIONS = _build_backfill_partitions()
