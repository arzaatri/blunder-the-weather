

with errors as (
    select * from "memory"."main"."int_forecast_errors"
),

temp_max as (
    select
        point_id, valid_date, lead_days, issued_date,
        'temp_max' as dimension,
        temp_max_forecast as forecast_value,
        temp_max_actual as actual_value,
        abs(temp_max_forecast - temp_max_actual) as abs_error,
        3.0 as threshold_used
    from errors
),

temp_min as (
    select
        point_id, valid_date, lead_days, issued_date,
        'temp_min' as dimension,
        temp_min_forecast as forecast_value,
        temp_min_actual as actual_value,
        abs(temp_min_forecast - temp_min_actual) as abs_error,
        3.0 as threshold_used
    from errors
),

cloud_cover as (
    select
        point_id, valid_date, lead_days, issued_date,
        'cloud_cover' as dimension,
        cloud_cover_forecast as forecast_value,
        cloud_cover_actual as actual_value,
        abs(cloud_cover_forecast - cloud_cover_actual) as abs_error,
        25.0 as threshold_used
    from errors
),

humidity as (
    select
        point_id, valid_date, lead_days, issued_date,
        'humidity' as dimension,
        humidity_forecast as forecast_value,
        humidity_actual as actual_value,
        abs(humidity_forecast - humidity_actual) as abs_error,
        15.0 as threshold_used
    from errors
),

-- Binarized rather than diffed: a forecast probability has no direct actual-world
-- analog. actual_value/abs_error are 0-or-1 mismatch indicators so this dimension
-- still fits the same is_large_error = abs_error > threshold_used rule as the rest.
precip_chance as (
    select
        point_id, valid_date, lead_days, issued_date,
        'precip_chance' as dimension,
        precip_chance_forecast as forecast_value,
        (case when precip_sum_actual > 0.1 then 1.0 else 0.0 end) as actual_value,
        abs(
            (case when precip_chance_forecast > 50.0 then 1.0 else 0.0 end)
            - (case when precip_sum_actual > 0.1 then 1.0 else 0.0 end)
        ) as abs_error,
        0.5 as threshold_used
    from errors
    where precip_chance_forecast is not null
),

unioned as (
    select * from temp_max
    union all
    select * from temp_min
    union all
    select * from cloud_cover
    union all
    select * from humidity
    union all
    select * from precip_chance
)

select
    *,
    abs_error > threshold_used as is_large_error,
    current_timestamp as resolved_at
from unioned