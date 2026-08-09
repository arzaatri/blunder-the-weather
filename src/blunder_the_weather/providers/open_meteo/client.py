"""Shared HTTP client for the three Open-Meteo APIs, with retry/backoff."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT_SECONDS = 30


def build_session() -> requests.Session:
    session = requests.Session()
    # backoff_factor=2 -> waits ~2/4/8/16/32s; needed headroom against 429s (see dagster.yaml).
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
