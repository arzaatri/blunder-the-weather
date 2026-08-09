
  
  create view "memory"."main"."stg_forecasts__dbt_tmp" as (
    select
    point_id,
    valid_date,
    lead_days,
    issued_date,
    temp_max,
    temp_min,
    cloud_cover_mean,
    humidity_mean,
    precip_chance,
    source
from 's3://blunder-the-weather/silver/forecasts/dt=*/part.parquet'
  );
