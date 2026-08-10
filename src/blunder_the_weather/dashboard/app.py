"""Streamlit dashboard: `streamlit run src/blunder_the_weather/dashboard/app.py`.

City selector -> 7-day x 5-dimension probability table + combined volatility score +
a SHAP panel for one dimension at the city-center grid point. Reads gold/ directly
from MinIO via dashboard/data.py -- no persisted .duckdb file, no separate database.
"""

import duckdb
import pandas as pd
import pydeck as pdk
import streamlit as st

from blunder_the_weather.dashboard.data import (
    city_dimension_table,
    city_overview_scores,
    explain_city_center,
    latest_scored_date,
    load_predictions,
    load_volatility_scores,
)
from blunder_the_weather.geo.registry import all_cities
from blunder_the_weather.models.registry import DIMENSIONS

_CITY_LAYER_ID = "cities"

# Hardcoded per-metric so a line's color never shifts as the checkbox selection below
# changes which subset of columns st.line_chart is asked to plot.
METRIC_COLORS: dict[str, str] = {
    "temp_max": "#e6194b",
    "temp_min": "#4363d8",
    "cloud_cover": "#808080",
    "humidity": "#3cb44b",
    "precip_chance": "#f58231",
    "combined": "#000000",
}


def _score_color(score: float) -> list[int]:
    """Green (reliable) -> red (volatile) for a score in [0, 1]; grey for a city with
    no data (e.g. NaN if a city somehow has zero grid points scored)."""
    if pd.isna(score):
        return [150, 150, 150, 160]
    score = max(0.0, min(1.0, score))
    return [int(200 * score), int(170 * (1 - score)), 40, 200]


def _render_map(overview: pd.DataFrame):
    """Renders the city overview map and returns its selection event (on_select=
    "rerun" makes a click trigger a rerun, same as any other widget interaction)."""
    overview = overview.copy()
    overview["color"] = overview["score"].apply(_score_color)
    overview["score_label"] = overview["score"].apply(lambda s: "no data" if pd.isna(s) else f"{s:.0%}")

    layer = pdk.Layer(
        "ScatterplotLayer",
        id=_CITY_LAYER_ID,  # required for selection state to be keyed/returned at all
        data=overview,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius=20000,
        pickable=True,
        stroked=True,
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
    )
    view_state = pdk.ViewState(latitude=overview["lat"].mean(), longitude=overview["lon"].mean(), zoom=3.2)
    return st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{name}\nAvg. 7-day volatility: {score_label}"},
        ),
        width="stretch",
        on_select="rerun",
        selection_mode="single-object",
        key="city_map",
    )


def _clicked_city_id(map_event) -> str | None:
    objects = map_event.selection.get("objects", {}).get(_CITY_LAYER_ID, [])
    return objects[0]["city_id"] if objects else None


st.set_page_config(page_title="Blunder the Weather", layout="wide")
st.title("Blunder the Weather")
st.caption("How likely is today's forecast to turn out wrong, per dimension, over the next 7 days?")

try:
    scored_date = latest_scored_date()
except duckdb.IOException:
    st.error(
        "Can't reach MinIO. Is the stack running? Try `./start_app.sh` "
        "(or check that `docker compose ps` shows the `minio` service up)."
    )
    st.stop()

if scored_date is None:
    st.warning(
        "No live predictions yet. Run `daily_live_job` in Dagster "
        "(or enable `daily_live_schedule`) to generate today's scores."
    )
    st.stop()

st.caption(f"Forecast issued: {scored_date.isoformat()}")

predictions = load_predictions(scored_date)
volatility = load_volatility_scores(scored_date)

st.subheader("Overview")
map_event = _render_map(city_overview_scores(volatility))

cities = all_cities()
city_name_by_id = {city.city_id: city.name for city in cities}

if "city_selector" not in st.session_state:
    st.session_state["city_selector"] = cities[0].name

# The map's selection state persists across reruns (e.g. a checkbox toggle below also
# reruns this script), so only push a click into the dropdown the run it actually
# happens on -- otherwise a stale click would keep overriding later manual dropdown
# choices on every unrelated rerun.
clicked_city_id = _clicked_city_id(map_event)
if clicked_city_id is not None and st.session_state.get("_last_map_click") != clicked_city_id:
    st.session_state["city_selector"] = city_name_by_id[clicked_city_id]
    st.session_state["_last_map_click"] = clicked_city_id

selected_name = st.selectbox("City", options=[city.name for city in cities], key="city_selector")
selected_city_id = next(city.city_id for city in cities if city.name == selected_name)

table = city_dimension_table(predictions, volatility, selected_city_id)

st.subheader(f"{city_name_by_id[selected_city_id]}: 7-day error-probability outlook")
display = table.copy()
display["valid_date"] = pd.to_datetime(display["valid_date"]).dt.strftime("%a %b %d")
display = display.rename(columns={"valid_date": "Date", "lead_days": "Lead (days)", "combined": "Combined"})
percent_columns = [*DIMENSIONS, "Combined"]
st.dataframe(
    display.set_index(["Date", "Lead (days)"]).style.format({c: "{:.0%}" for c in percent_columns}),
    width="stretch",
)

st.subheader("Volatility score by lead time")
chart_metrics = [*DIMENSIONS, "combined"]
chart_labels = {**{d: d.replace("_", " ").title() for d in DIMENSIONS}, "combined": "Combined"}
default_visible = {"combined"}

spacer_left, *checkbox_columns, spacer_right = st.columns([2, *([1] * len(chart_metrics)), 2])
visible_metrics = []
for column, metric in zip(checkbox_columns, chart_metrics):
    with column:
        if st.checkbox(chart_labels[metric], value=metric in default_visible, key=f"show_{metric}"):
            visible_metrics.append(metric)

if visible_metrics:
    st.line_chart(
        table.set_index("lead_days")[visible_metrics],
        x_label="Lead (days)",
        y_label="Volatility score",
        color=[METRIC_COLORS[metric] for metric in visible_metrics],
    )
else:
    st.info("Select at least one metric above to display the chart.")

st.subheader("Why? SHAP feature attribution (city-center grid point)")
shap_dimension = st.selectbox("Dimension", options=DIMENSIONS, key="shap_dimension")
shap_lead = st.selectbox("Lead (days)", options=list(range(1, 8)), key="shap_lead")

explanation, feature_df = explain_city_center(scored_date, selected_city_id, shap_dimension)
row_idx = feature_df.reset_index(drop=True).index[feature_df["lead_days"].reset_index(drop=True) == shap_lead][0]
shap_row = pd.Series(explanation.shap_values[row_idx], index=explanation.feature_names).sort_values()
st.bar_chart(shap_row, horizontal=True, x_label="SHAP value", y_label="Feature")
st.caption(f"Base value: {explanation.base_value:.3f} (log-odds before feature contributions)")
