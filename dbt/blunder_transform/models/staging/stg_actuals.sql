select
    point_id,
    date as valid_date,
    temp_max,
    temp_min,
    cloud_cover_mean,
    humidity_mean,
    precip_sum
from {{ source('silver', 'actuals') }}
