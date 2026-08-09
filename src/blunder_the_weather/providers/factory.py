"""Maps config-declared provider roles (config/app.yaml -> providers.*) to concrete
implementations. Swapping a role to a different vendor later is one new class plus one
registry entry here -- no changes to any caller, since everyone codes against the
Protocols in providers/base.py."""

from blunder_the_weather.config import load_config
from blunder_the_weather.providers.base import ActualsProvider, HistoricalForecastProvider, LiveForecastProvider
from blunder_the_weather.providers.open_meteo.actuals import OpenMeteoActualsProvider
from blunder_the_weather.providers.open_meteo.historical_forecast import OpenMeteoHistoricalForecastProvider
from blunder_the_weather.providers.open_meteo.live_forecast import OpenMeteoLiveForecastProvider

_ACTUALS_PROVIDERS: dict[str, type[ActualsProvider]] = {"open_meteo": OpenMeteoActualsProvider}
_HISTORICAL_FORECAST_PROVIDERS: dict[str, type[HistoricalForecastProvider]] = {
    "open_meteo": OpenMeteoHistoricalForecastProvider
}
_LIVE_FORECAST_PROVIDERS: dict[str, type[LiveForecastProvider]] = {"open_meteo": OpenMeteoLiveForecastProvider}


def build_actuals_provider() -> ActualsProvider:
    name = load_config().providers.actuals
    return _ACTUALS_PROVIDERS[name]()


def build_historical_forecast_provider() -> HistoricalForecastProvider:
    name = load_config().providers.historical_forecast
    return _HISTORICAL_FORECAST_PROVIDERS[name]()


def build_live_forecast_provider() -> LiveForecastProvider:
    name = load_config().providers.live_forecast
    return _LIVE_FORECAST_PROVIDERS[name]()
