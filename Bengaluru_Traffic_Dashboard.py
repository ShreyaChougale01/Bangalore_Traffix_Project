import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import io

st.set_page_config(page_title="Bengaluru Traffic Dashboard", page_icon="🚦", layout="wide")
st.title("🚦 Bengaluru Traffic Flow & Congestion Dashboard")
st.caption("Explore traffic volume, congestion, speed, and road-capacity utilization.")

@st.cache_data
def load_data(file_bytes):
    data = pd.read_csv(io.BytesIO(file_bytes))
    data.columns = (
        data.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[/\s]+", "_", regex=True)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    if "date" not in data.columns:
        raise ValueError("CSV must contain a Date/date column.")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in ["traffic_volume", "average_speed", "congestion_level",
                "travel_time_index", "road_capacity_utilization", "risk_flag"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data

with st.sidebar:
    st.header("Dashboard controls")
    uploaded = st.file_uploader("Upload traffic CSV", type=["csv"])

if uploaded is not None:
    try:
        df = load_data(uploaded.getvalue())
    except Exception as exc:
        st.error(f"Could not load the CSV: {exc}")
        st.stop()
else:
    paths = [Path("Banglore_Traffic_Cleaned_Enriched.csv"), Path("Banglore_traffic_Dataset.csv")]
    csv_path = next((p for p in paths if p.exists()), None)
    if csv_path is None:
        st.info("Upload your cleaned/enriched traffic CSV or original Banglore_traffic_Dataset.csv using the sidebar.")
        st.stop()
    try:
        df = load_data(csv_path.read_bytes())
    except Exception as exc:
        st.error(f"Could not load the CSV: {exc}")
        st.stop()

required = ["date", "traffic_volume", "average_speed", "congestion_level"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error("Missing required columns: " + ", ".join(missing))
    st.stop()

for col in ["area_name", "road_intersection_name", "weather_conditions", "roadwork_and_construction_activity"]:
    if col not in df.columns:
        df[col] = "Not available"
    df[col] = df[col].fillna("Not available").astype(str)
for col in ["travel_time_index", "road_capacity_utilization", "risk_flag"]:
    if col not in df.columns:
        df[col] = pd.NA

with st.sidebar:
    st.subheader("Filters")
    areas = sorted(df["area_name"].unique().tolist())
    selected_areas = st.multiselect("Area", areas, default=areas)
    roads = sorted(df["road_intersection_name"].unique().tolist())
    selected_roads = st.multiselect("Road/intersection", roads, default=roads)
    valid_dates = df["date"].dropna()
    if not valid_dates.empty:
        start, end = valid_dates.min().date(), valid_dates.max().date()
        date_range = st.date_input("Date range", value=(start, end), min_value=start, max_value=end)
    else:
        date_range = ()

filtered = df[df["area_name"].isin(selected_areas) & df["road_intersection_name"].isin(selected_roads)].copy()
if len(date_range) == 2:
    filtered = filtered[filtered["date"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))]
if filtered.empty:
    st.warning("No records match these filters. Select more areas/roads or a wider date range.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Records", f"{len(filtered):,}")
c2.metric("Average congestion", f"{filtered['congestion_level'].mean():.2f}")
c3.metric("Average speed", f"{filtered['average_speed'].mean():.2f}")
c4.metric("Average traffic volume", f"{filtered['traffic_volume'].mean():,.0f}")
st.divider()

st.subheader("Weekly Traffic Trend")
weekly = (filtered.set_index("date").resample("W")
          .agg(mean_congestion=("congestion_level", "mean"),
               mean_speed=("average_speed", "mean"),
               mean_volume=("traffic_volume", "mean")).reset_index())
metric_labels = {"Congestion": "mean_congestion", "Average speed": "mean_speed", "Traffic volume": "mean_volume"}
chosen_metric = st.selectbox("Choose weekly metric", list(metric_labels))
trend = px.line(weekly, x="date", y=metric_labels[chosen_metric], markers=True,
                title=f"Weekly average {chosen_metric.lower()}")
trend.update_layout(height=400, xaxis_title="Week", yaxis_title=chosen_metric)
st.plotly_chart(trend, use_container_width=True)

left, right = st.columns(2)
area_summary = (filtered.groupby("area_name", as_index=False)
                .agg(mean_congestion=("congestion_level", "mean"), mean_speed=("average_speed", "mean"),
                     mean_volume=("traffic_volume", "mean")).sort_values("mean_congestion", ascending=False))
with left:
    st.subheader("Average Congestion by Area")
    fig = px.bar(area_summary, x="area_name", y="mean_congestion", hover_data=["mean_speed", "mean_volume"])
    fig.update_layout(height=420, xaxis_title="Area", yaxis_title="Average congestion")
    st.plotly_chart(fig, use_container_width=True)
with right:
    road_summary = (filtered.groupby("road_intersection_name", as_index=False)
                    .agg(mean_congestion=("congestion_level", "mean"), mean_speed=("average_speed", "mean"))
                    .sort_values("mean_congestion", ascending=False).head(15))
    st.subheader("Top 15 Congested Roads/Intersections")
    fig = px.bar(road_summary, x="road_intersection_name", y="mean_congestion", hover_data=["mean_speed"])
    fig.update_layout(height=420, xaxis_title="Road/intersection", yaxis_title="Average congestion")
    st.plotly_chart(fig, use_container_width=True)

# Each relationship is plotted exactly once; a sample reduces visual overlap.
scatter_data = filtered.sample(n=min(1200, len(filtered)), random_state=42)
left, right = st.columns(2)
with left:
    st.subheader("Traffic Volume vs Congestion")
    fig = px.scatter(scatter_data, x="traffic_volume", y="congestion_level", color="area_name",
                     opacity=0.22, hover_data=["date", "road_intersection_name"])
    fig.update_traces(marker=dict(size=4))
    fig.update_layout(height=430, xaxis_title="Traffic volume", yaxis_title="Congestion level")
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Average Speed vs Congestion")
    fig = px.scatter(scatter_data, x="average_speed", y="congestion_level", color="area_name",
                     opacity=0.22, hover_data=["date", "road_intersection_name"])
    fig.update_traces(marker=dict(size=4))
    fig.update_layout(height=430, xaxis_title="Average speed", yaxis_title="Congestion level")
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
st.subheader("Weather and Roadwork Context")
with left:
    st.caption("Weather")
    st.dataframe(filtered.groupby("weather_conditions", as_index=False)
                 .agg(records=("date", "size"), mean_congestion=("congestion_level", "mean"),
                      mean_speed=("average_speed", "mean")).round(2), use_container_width=True)
with right:
    st.caption("Roadwork")
    st.dataframe(filtered.groupby("roadwork_and_construction_activity", as_index=False)
                 .agg(records=("date", "size"), mean_congestion=("congestion_level", "mean"),
                      mean_speed=("average_speed", "mean")).round(2), use_container_width=True)

st.subheader("Highest Congestion Records")
display_cols = [c for c in ["date", "area_name", "road_intersection_name", "traffic_volume",
               "average_speed", "congestion_level", "travel_time_index",
               "road_capacity_utilization", "risk_flag"] if c in filtered.columns]
st.dataframe(filtered.sort_values("congestion_level", ascending=False)[display_cols].head(100),
             use_container_width=True)
st.caption("Interpretation note: these charts describe patterns in the supplied data. Associations do not prove causation; scenario changes are illustrative unless validated with a suitable model.")
