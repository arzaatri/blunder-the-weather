"""Daily schedules driving the pipeline's ongoing growth. Both are defined but stopped
by default (see .dagster_home/dagster.yaml's scheduler.max_catchup_runs for the other
half of the gap-tolerance story: if these are off for a few days, the daemon backfills
the missed ticks itself once it's running again, instead of leaving a permanent gap).
"""

from dagster import DefaultScheduleStatus, ScheduleDefinition, build_schedule_from_partitioned_job

from blunder_the_weather.dagster_defs.jobs import backfill_job, daily_live_job, train_models_job, transform_job

# One tick per day, targeting whatever the newest valid BACKFILL_PARTITIONS key is that
# day (see partitions.py) -- the same job used for the original historical load. A run
# for an already-materialized partition is just a cheap re-fetch, not an error.
daily_backfill_schedule = build_schedule_from_partitioned_job(
    backfill_job,
    name="daily_backfill_schedule",
    hour_of_day=6,
    default_status=DefaultScheduleStatus.STOPPED,
)

# Rebuilds gold from whatever silver partitions exist in MinIO (dbt reads a dt=* glob,
# not Dagster's partition set -- see stg_actuals.sql/stg_forecasts.sql), so it picks up
# any catch-up partitions the backfill schedule/daemon just landed. Runs an hour after
# the backfill schedule to give same-day ingestion time to land first.
daily_transform_schedule = ScheduleDefinition(
    name="daily_transform_schedule",
    job=transform_job,
    cron_schedule="0 7 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)

# Scores today's operational forecast. No dependency ordering on the two schedules
# above -- it reads gold_model_registry (whatever was last trained) and today's own
# live forecast pull, neither of which the backfill/transform schedules touch.
daily_live_schedule = build_schedule_from_partitioned_job(
    daily_live_job,
    name="daily_live_schedule",
    hour_of_day=8,
    default_status=DefaultScheduleStatus.STOPPED,
)

# Retraining is just train_models_job (the same manual job from Phase 4) on a cadence --
# no separate "retrain_job" definition, since that would just be train_models_job under
# a different name. Weekly rather than daily: retraining on every single day's marginal
# addition of data risks chasing noise more than it improves the model, and there's no
# evidence yet that daily retraining is worth the extra churn on model_registry/models/.
# Sundays, after the daily jobs above so the week's newest data is already in gold.
retrain_schedule = ScheduleDefinition(
    name="retrain_schedule",
    job=train_models_job,
    cron_schedule="0 9 * * 0",
    default_status=DefaultScheduleStatus.STOPPED,
)
