"""Daily partitions for bronze/silver ingestion (config/app.yaml's backfill.* settings).

Open-ended on purpose: no end_date, just an end_offset behind "now". Dagster evaluates
that boundary dynamically on every call, not once at process start, so the valid
partition range keeps advancing on its own as real days pass -- this is what lets one
job (backfill_job) serve both the initial historical fill and ongoing daily ingestion.
It's also what makes downtime recoverable rather than a permanent gap: if the app/daemon
is off for a few days, those dates are simply unmaterialized partitions the moment it
comes back, catchable either automatically (the scheduler daemon's max_catchup_runs,
see .dagster_home/dagster.yaml) or manually via the same partition backfill UI/CLI
used for the original historical load -- never a hard dependency on same-day execution.
"""

from dagster import DailyPartitionsDefinition

from blunder_the_weather.config import load_config


def _build_backfill_partitions() -> DailyPartitionsDefinition:
    backfill_config = load_config().backfill
    return DailyPartitionsDefinition(
        start_date=backfill_config.start_date.isoformat(),
        end_offset=-backfill_config.end_lag_days,
    )


BACKFILL_PARTITIONS = _build_backfill_partitions()


def _build_live_partitions() -> DailyPartitionsDefinition:
    """end_offset=1 (verified empirically) makes "today" the newest valid partition,
    unlike backfill's end_offset<=0 -- a live forecast is scored the same day it's
    issued, there's no data-availability lag to wait out. Same open-ended growth and
    catch-up story as BACKFILL_PARTITIONS applies here too."""
    live_config = load_config().live
    return DailyPartitionsDefinition(start_date=live_config.start_date.isoformat(), end_offset=1)


LIVE_PARTITIONS = _build_live_partitions()
