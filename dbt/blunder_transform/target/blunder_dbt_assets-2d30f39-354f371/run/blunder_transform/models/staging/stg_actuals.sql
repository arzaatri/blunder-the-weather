
  
  create view "memory"."main"."stg_actuals__dbt_tmp" as (
    select
    point_id,
    date as valid_date,
    temp_max,
    temp_min,
    cloud_cover_mean,
    humidity_mean,
    precip_sum
from 's3://blunder-the-weather/silver/actuals/dt=*/part.parquet'
  );
