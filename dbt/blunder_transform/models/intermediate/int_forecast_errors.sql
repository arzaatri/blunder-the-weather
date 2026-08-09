select
    f.point_id,
    f.valid_date,
    f.lead_days,
    f.issued_date,
    f.temp_max as temp_max_forecast,
    a.temp_max as temp_max_actual,
    f.cloud_cover_mean as cloud_cover_forecast,
    a.cloud_cover_mean as cloud_cover_actual,
    f.humidity_mean as humidity_forecast,
    a.humidity_mean as humidity_actual,
    f.precip_chance as precip_chance_forecast,
    a.precip_sum as precip_sum_actual
from {{ ref('stg_forecasts') }} f
inner join {{ ref('stg_actuals') }} a
    on f.point_id = a.point_id
    and f.valid_date = a.valid_date
