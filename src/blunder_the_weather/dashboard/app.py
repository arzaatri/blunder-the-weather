"""Streamlit dashboard: `streamlit run src/blunder_the_weather/dashboard/app.py`.

City selector -> 7-day x 5-dimension probability table + combined volatility score +
a SHAP panel for one dimension at the city-center grid point. Reads gold/ directly
from MinIO via dashboard/data.py -- no persisted .duckdb file, no separate database.
"""

import altair as alt
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

# Fixed rather than height="stretch": with no fixed-size anchor anywhere in the column,
# two independently-"stretching" cards don't equalize against each other -- both just
# collapse to some small default. A shared pixel height is what actually keeps the
# map and chart cards the same size.
_CHART_HEIGHT = 480

# Hardcoded per-metric so a line's color never shifts as the pills selection below
# changes which subset of columns the chart is asked to plot. Matched to the "storm
# watch" theme's semantic colors (.streamlit/config.toml) rather than arbitrary
# values -- "combined" in particular used to be pure black, which is invisible
# against the theme's navy background.
METRIC_COLORS: dict[str, str] = {
    "combined": "#FFFFFF",
    "temp_max": "#F43F5E",
    "temp_min": "#C084FC",  # pivoted off blue entirely -- too close to the navy background
    "cloud_cover": "#7DD3FC",
    "humidity": "#34D399",
    "precip_chance": "#FB923C",
}


def _score_color(score: float) -> list[int]:
    """Green (reliable) -> red (volatile) for a score in [0, 1], interpolated between
    the theme's greenColor/redColor; grey (theme's grayColor) for a city with no data
    (e.g. NaN if a city somehow has zero grid points scored)."""
    if pd.isna(score):
        return [148, 163, 184, 180]
    score = max(0.0, min(1.0, score))
    green, red = (52, 211, 153), (244, 63, 94)
    return [int(green[i] + (red[i] - green[i]) * score) for i in range(3)] + [230]


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
            map_style="dark_no_labels",  # pin explicitly for the dark theme rather than relying on pydeck's default
        ),
        width="stretch",
        height=_CHART_HEIGHT,
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

predictions = load_predictions(scored_date)
volatility = load_volatility_scores(scored_date)
overview = city_overview_scores(volatility)

cities = all_cities()
city_name_by_id = {city.city_id: city.name for city in cities}

# KPI row -- all four derived from data already loaded above, no new queries. None
# carry a chart_data sparkline -- that made one card taller than the other three.
riskiest = overview.loc[overview["score"].idxmax()]
calmest = overview.loc[overview["score"].idxmin()]
dim_means = predictions.groupby("dimension")["calibrated_prob"].mean()
worst_dim = dim_means.idxmax()
best_dim = dim_means.idxmin()

with st.container(horizontal=True):
    st.metric(
        "Riskiest city today",
        f":material/warning: {riskiest['name']}",
        delta=f"{riskiest['score']:.0%} avg 7-day volatility",
        delta_color="off",
        border=True,
    )
    st.metric(
        "Most stable city today",
        f":material/verified: {calmest['name']}",
        delta=f"{calmest['score']:.0%} avg 7-day volatility",
        delta_color="off",
        border=True,
    )
    st.metric(
        "Least reliable dimension (network)",
        f":material/thunderstorm: {worst_dim.replace('_', ' ').title()}",
        delta=f"{dim_means[worst_dim]:.0%} avg error probability",
        delta_color="off",
        border=True,
    )
    st.metric(
        "Most reliable dimension (network)",
        f":material/check_circle: {best_dim.replace('_', ' ').title()}",
        delta=f"{dim_means[best_dim]:.0%} avg error probability",
        delta_color="off",
        border=True,
    )

# Top row: map + city selector on the left, the line chart (and its metric toggles)
# on the right. selected_city_id/table are needed by both this row and everything
# below, so they're resolved inside col_map before col_chart and the bottom sections
# read them -- placement in `with` blocks controls layout, not execution order.
col_map, col_chart = st.columns(2)

with col_map, st.container(border=True):
    st.markdown("### :material/radar: Overview")
    map_event = _render_map(overview)

    if "city_selector" not in st.session_state:
        st.session_state["city_selector"] = cities[0].name

    # The map's selection state persists across reruns (e.g. a pills toggle also
    # reruns this script), so only push a click into the dropdown the run it actually
    # happens on -- otherwise a stale click would keep overriding later manual
    # dropdown choices on every unrelated rerun.
    clicked_city_id = _clicked_city_id(map_event)
    if clicked_city_id is not None and st.session_state.get("_last_map_click") != clicked_city_id:
        st.session_state["city_selector"] = city_name_by_id[clicked_city_id]
        st.session_state["_last_map_click"] = clicked_city_id

    selected_name = st.selectbox("City", options=[city.name for city in cities], key="city_selector")
    selected_city_id = next(city.city_id for city in cities if city.name == selected_name)

table = city_dimension_table(predictions, volatility, selected_city_id)

with col_chart, st.container(border=True):
    st.markdown("### :material/monitoring: Volatility score by lead time")
    st.caption(f"Forecast issued: {scored_date.isoformat()}")

    chart_metrics = ["combined", *DIMENSIONS]
    chart_labels = {"combined": "Combined", **{d: d.replace("_", " ").title() for d in DIMENSIONS}}
    visible_metrics = st.pills(
        "Metrics",
        options=chart_metrics,
        format_func=lambda m: chart_labels[m],
        selection_mode="multi",
        default=["combined"],
        label_visibility="collapsed",
        key="chart_metrics",
    )

    if visible_metrics:
        # A continuous temporal (":T") x-axis lets Vega-Lite pick its own tick
        # spacing, which -- with only 7 days on the axis -- lands on a sub-daily
        # interval and prints two ticks per calendar day, both formatted the same
        # ("Aug 10 Aug 10 Aug 11 ..."). Using the pre-formatted label as an ordinal
        # (":O") field instead gives exactly one tick per data point; an explicit
        # `sort` (rather than relying on alphabetical order) keeps it chronological
        # across a month boundary, e.g. "Jul 31" before "Aug 01".
        chart_df = table[["valid_date", *visible_metrics]].copy()
        chart_df["date_label"] = pd.to_datetime(chart_df["valid_date"]).dt.strftime("%b %d")
        date_order = chart_df["date_label"].tolist()
        chart_df = chart_df.melt(id_vars=["date_label"], value_vars=visible_metrics, var_name="metric", value_name="value")
        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("date_label:O", title="Date", sort=date_order, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("value:Q", title="Volatility score"),
                color=alt.Color(
                    "metric:N",
                    scale=alt.Scale(domain=visible_metrics, range=[METRIC_COLORS[m] for m in visible_metrics]),
                    legend=alt.Legend(title=" ", orient="bottom"),
                ),
                tooltip=["date_label", "metric", "value"],
            )
        )
        st.altair_chart(chart, width="stretch", height=_CHART_HEIGHT)
    else:
        st.info("Select at least one metric above to display the chart.")

# Bottom: per-dimension score table, then the SHAP panel.
with st.container(border=True):
    st.markdown(f"### :material/table_chart: {city_name_by_id[selected_city_id]}: 7-day error-probability outlook")
    display = table.copy()
    display["valid_date"] = pd.to_datetime(display["valid_date"]).dt.strftime("%a %b %d")
    display = display.rename(columns={"valid_date": "Date", "lead_days": "Lead (days)", "combined": "Combined"})
    percent_columns = [*DIMENSIONS, "Combined"]
    st.dataframe(
        display.set_index(["Date", "Lead (days)"]).style.format({c: "{:.0%}" for c in percent_columns}),
        width="stretch",
    )

with st.container(border=True):
    st.markdown("### :material/query_stats: Why? SHAP feature attribution (city-center grid point)")
    shap_dimension = st.selectbox("Dimension", options=DIMENSIONS, key="shap_dimension")
    shap_lead = st.selectbox("Lead (days)", options=list(range(1, 8)), key="shap_lead")

    explanation, feature_df = explain_city_center(scored_date, selected_city_id, shap_dimension)
    row_idx = feature_df.reset_index(drop=True).index[feature_df["lead_days"].reset_index(drop=True) == shap_lead][0]
    shap_row = pd.Series(explanation.shap_values[row_idx], index=explanation.feature_names).sort_values()
    st.bar_chart(shap_row, horizontal=True, x_label="SHAP value", y_label="Feature")
    st.caption(f"Base value: {explanation.base_value:.3f} (log-odds before feature contributions)")
