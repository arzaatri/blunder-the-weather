"""dbt project handle: transforms silver -> gold (see dbt/blunder_transform).

Sets up its own env (profiles.yml needs MINIO_* at Jinja-render time, i.e. even
during `dbt parse`) rather than relying on definitions.py's import order.
"""

import os

from dagster_dbt import DbtProject
from dotenv import load_dotenv

from blunder_the_weather.config import ENV_PATH, REPO_ROOT, load_config

load_dotenv(ENV_PATH)
os.environ.setdefault(
    "MINIO_ENDPOINT_HOST", load_config().minio.endpoint_url.removeprefix("http://").removeprefix("https://")
)

DBT_PROJECT_DIR = REPO_ROOT / "dbt" / "blunder_transform"

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR, profiles_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()
