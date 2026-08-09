"""Thin wrapper around Great Expectations' fluent API for validating an in-memory
DataFrame against a list of expectations. Each call gets its own ephemeral context --
these run inside short-lived Dagster check steps, not a shared long-running process."""

import great_expectations as gx
import pandas as pd
from great_expectations.core.expectation_validation_result import ExpectationSuiteValidationResult
from great_expectations.expectations.expectation import Expectation


def validate_dataframe(
    df: pd.DataFrame, suite_name: str, expectations: list[Expectation]
) -> ExpectationSuiteValidationResult:
    context = gx.get_context(mode="ephemeral")
    suite = context.suites.add(gx.ExpectationSuite(name=suite_name))
    for expectation in expectations:
        suite.add_expectation(expectation)

    data_source = context.data_sources.add_pandas("pandas")
    data_asset = data_source.add_dataframe_asset(suite_name)
    batch_definition = data_asset.add_batch_definition_whole_dataframe("batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
    return batch.validate(suite)
