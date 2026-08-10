import optuna

from blunder_the_weather.models.tuning import _SEARCH_SPACE, _suggest_params

# tune_dimension() itself isn't unit-tested here, same as train_and_evaluate() in
# training.py -- both need a real gold_ground_truth_log frame via duckdb/MinIO, so
# they're exercised via a live run (see train_model.sh) rather than a synthetic test.
# What's cheap and worth checking without that infra is the search-space wiring
# itself: a typo swapping a (low, high) bound would otherwise fail silently.


def test_suggest_params_covers_search_space_within_bounds() -> None:
    study = optuna.create_study()
    trial = study.ask()
    params = _suggest_params(trial)

    assert set(params) == set(_SEARCH_SPACE)
    for name, (low, high) in _SEARCH_SPACE.items():
        assert low <= params[name] <= high
