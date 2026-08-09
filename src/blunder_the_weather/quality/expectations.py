"""Expectation suites for the silver and gold layers."""

import great_expectations as gx

SILVER_ACTUALS_EXPECTATIONS = [
    gx.expectations.ExpectColumnValuesToNotBeNull(column="point_id"),
    gx.expectations.ExpectColumnValuesToNotBeNull(column="date"),
    gx.expectations.ExpectColumnValuesToBeBetween(column="temp_max", min_value=-50, max_value=60),
    gx.expectations.ExpectColumnValuesToBeBetween(column="temp_min", min_value=-60, max_value=50),
    gx.expectations.ExpectColumnValuesToBeBetween(column="cloud_cover_mean", min_value=0, max_value=100),
    gx.expectations.ExpectColumnValuesToBeBetween(column="humidity_mean", min_value=0, max_value=100),
    gx.expectations.ExpectColumnValuesToBeBetween(column="precip_sum", min_value=0, max_value=None),
]

SILVER_FORECASTS_EXPECTATIONS = [
    gx.expectations.ExpectColumnValuesToNotBeNull(column="point_id"),
    gx.expectations.ExpectColumnValuesToNotBeNull(column="valid_date"),
    gx.expectations.ExpectColumnValuesToBeBetween(column="lead_days", min_value=1, max_value=7),
    gx.expectations.ExpectColumnValuesToBeBetween(column="temp_max", min_value=-50, max_value=60),
    gx.expectations.ExpectColumnValuesToBeBetween(column="temp_min", min_value=-60, max_value=50),
    gx.expectations.ExpectColumnValuesToBeBetween(column="cloud_cover_mean", min_value=0, max_value=100),
    gx.expectations.ExpectColumnValuesToBeBetween(column="humidity_mean", min_value=0, max_value=100),
    # precip_chance is nullable (shorter archive, see mappings) -- between ignores nulls.
    gx.expectations.ExpectColumnValuesToBeBetween(column="precip_chance", min_value=0, max_value=100),
]

GOLD_GROUND_TRUTH_LOG_EXPECTATIONS = [
    gx.expectations.ExpectColumnValuesToBeInSet(
        column="dimension", value_set=["temp_max", "temp_min", "cloud_cover", "humidity", "precip_chance"]
    ),
    gx.expectations.ExpectColumnValuesToBeBetween(column="abs_error", min_value=0, max_value=None),
    gx.expectations.ExpectColumnValuesToNotBeNull(column="threshold_used"),
    gx.expectations.ExpectColumnValuesToNotBeNull(column="is_large_error"),
    gx.expectations.ExpectTableRowCountToBeBetween(min_value=1),
]
