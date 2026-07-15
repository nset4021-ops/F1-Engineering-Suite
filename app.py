import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

OPENF1_BASE = "https://api.openf1.org/v1"
DEFAULT_SESSION_KEY = 9839
DEFAULT_DRIVER_NUMBER = 44
TELEMETRY_FETCH_LIMIT = 5000

COMPOUND_DEGRADATION = {
    "SOFT": 4.8,
    "MEDIUM": 3.3,
    "HARD": 2.3,
    "INTERMEDIATE": 3.8,
    "WET": 4.2,
}


def apply_theme() -> None:
    st.set_page_config(page_title="The Virtual Garage: An F1 Engineering Suite", layout="wide")
    st.markdown(
        """
        <style>
            .stApp {
                background: radial-gradient(circle at top, #111827 0%, #05080f 40%, #02040a 100%);
                color: #e5e7eb;
            }
            h1, h2, h3, .stMarkdown, .stText, label { color: #e5e7eb !important; }
            div[data-testid="stMetricValue"] { color: #10b981; }
            .warning-box {
                border: 1px solid #f97316;
                background-color: rgba(249, 115, 22, 0.12);
                color: #fed7aa;
                border-radius: 10px;
                padding: 12px;
                font-weight: 700;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False, ttl=60)
def fetch_openf1(endpoint: str, session_key: int, driver_number: int, limit: int | None = None) -> Tuple[List[Dict], str]:
    url = f"{OPENF1_BASE}/{endpoint}?session_key={session_key}&driver_number={driver_number}"
    if limit is not None:
        url += f"&limit={int(limit)}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) == 0:
            raise ValueError("No data returned from OpenF1")
        return payload, "real"
    except (requests.RequestException, ValueError) as exc:
        return [], str(exc)


def synthetic_session_dataframe(points: int = 300) -> pd.DataFrame:
    t = np.arange(points)
    theta = np.linspace(0, 2 * np.pi, points)
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=points, freq="2s"),
            "speed": 235 + 55 * np.sin(t / 15),
            "throttle": np.clip(68 + 28 * np.sin(t / 11), 0, 100),
            "brake": np.clip(100 - np.clip(68 + 28 * np.sin(t / 11), 0, 100), 0, 100),
            "x": 1400 * np.cos(theta) + 120 * np.cos(3 * theta),
            "y": 900 * np.sin(theta) + 90 * np.sin(4 * theta),
        }
    )


def mock_lap_data() -> List[Dict]:
    lap_times = [91.2, 91.7, 92.1, 92.6, 93.2, 94.1, 95.3, 96.5, 97.8]
    return [
        {"lap_number": idx + 1, "lap_duration": lap, "compound": "MEDIUM"}
        for idx, lap in enumerate(lap_times)
    ]


def normalize_date_column(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns:
        return df
    df = df.copy()
    try:
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    except (TypeError, ValueError):
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    return df


def parse_laps(raw_laps: List[Dict]) -> pd.DataFrame:
    rows = []
    for row in raw_laps:
        lap_time = row.get("lap_duration") or row.get("lap_time")
        lap_no = row.get("lap_number")
        compound = row.get("compound") or row.get("tyre_compound") or row.get("stint_compound")
        if lap_time is None or lap_no is None:
            continue
        rows.append(
            {
                "lap_number": int(lap_no),
                "lap_time": float(lap_time),
                "compound": compound,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["lap_number", "lap_time", "compound"])

    df = pd.DataFrame(rows).sort_values("lap_number")
    df["compound"] = (
        df["compound"]
        .fillna("MEDIUM")
        .astype(str)
        .str.upper()
        .str.strip()
        .replace({"": "MEDIUM", "NAN": "MEDIUM", "NONE": "MEDIUM"})
    )
    return df


def parse_car_data(raw: List[Dict]) -> pd.DataFrame:
    rows = []
    for point in raw:
        ts = point.get("date") or point.get("timestamp")
        speed = point.get("speed")
        throttle = point.get("throttle")
        brake = point.get("brake")
        if ts is None or speed is None or throttle is None or brake is None:
            continue
        rows.append(
            {
                "date": ts,
                "speed": float(speed),
                "throttle": float(throttle),
                "brake": float(brake),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["date", "speed", "throttle", "brake"])

    df = pd.DataFrame(rows)
    df = normalize_date_column(df)
    return df.dropna(subset=["date"]).sort_values("date")


def parse_location_data(raw: List[Dict]) -> pd.DataFrame:
    rows = []
    for point in raw:
        ts = point.get("date") or point.get("timestamp")
        x, y = point.get("x"), point.get("y")
        if ts is None or x is None or y is None:
            continue
        rows.append({"date": ts, "x": float(x), "y": float(y)})

    if not rows:
        return pd.DataFrame(columns=["date", "x", "y"])

    df = pd.DataFrame(rows)
    df = normalize_date_column(df)
    return df.dropna(subset=["date"]).sort_values("date")


def get_lap_window(raw_laps: List[Dict]) -> Tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if not raw_laps:
        return None, None

    starts = []
    ends = []
    for row in raw_laps:
        start = row.get("date_start") or row.get("lap_start_date")
        end = row.get("date_end")
        if start:
            starts.append(start)
        if end:
            ends.append(end)

    start_ts = pd.to_datetime(starts, utc=True, errors="coerce") if starts else pd.Series(dtype="datetime64[ns, UTC]")
    end_ts = pd.to_datetime(ends, utc=True, errors="coerce") if ends else pd.Series(dtype="datetime64[ns, UTC]")

    valid_start = start_ts.min() if len(start_ts) else pd.NaT
    valid_end = end_ts.max() if len(end_ts) else pd.NaT

    if pd.isna(valid_start):
        valid_start = None
    else:
        valid_start = valid_start.tz_localize(None)

    if pd.isna(valid_end):
        valid_end = None
    else:
        valid_end = valid_end.tz_localize(None)

    return valid_start, valid_end


def strategy_engine() -> None:
    st.subheader("MODULE 1: THE AI PIT WALL (STRATEGY ENGINE)")
    c1, c2 = st.columns(2)
    driver_number = c1.number_input("Driver Number", min_value=1, max_value=99, value=DEFAULT_DRIVER_NUMBER, step=1)
    session_key = c2.number_input("Session Key", min_value=1, value=DEFAULT_SESSION_KEY, step=1)

    raw_laps, status = fetch_openf1("laps", int(session_key), int(driver_number))
    if raw_laps:
        laps_df = parse_laps(raw_laps)
        data_source = "real OpenF1 telemetry"
    else:
        st.error(f"Lap API failed ({status}). Switching to built-in synthetic laps.")
        laps_df = parse_laps(mock_lap_data())
        data_source = "synthetic fallback"

    if laps_df.empty:
        st.warning("No lap data available for strategy simulation.")
        return

    current_compound = laps_df["compound"].iloc[-1] if not laps_df.empty else "MEDIUM"
    deg_rate = COMPOUND_DEGRADATION.get(current_compound, COMPOUND_DEGRADATION["MEDIUM"])

    lap_index = np.arange(len(laps_df))
    baseline = laps_df["lap_time"].iloc[0]
    lap_drift = np.maximum(laps_df["lap_time"] - baseline, 0)
    theoretical_grip = np.clip(100 - deg_rate * lap_index - 2.2 * lap_drift, 0, 100)
    laps_df["theoretical_grip"] = theoretical_grip

    st.caption(f"Data source: {data_source}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Compound", current_compound)
    m2.metric("Latest Lap Time (s)", f"{laps_df['lap_time'].iloc[-1]:.3f}")
    m3.metric("Theoretical Grip (%)", f"{laps_df['theoretical_grip'].iloc[-1]:.1f}")

    if laps_df["theoretical_grip"].iloc[-1] < 45:
        st.markdown(
            f"<div class='warning-box'>BOX BOX: Tyre grip low. Recommend Pit Stop for {current_compound}.</div>",
            unsafe_allow_html=True,
        )

    fig = px.line(
        laps_df,
        x="lap_number",
        y="lap_time",
        markers=True,
        title="Real Lap Time Trend",
        template="plotly_dark",
    )
    fig.update_layout(xaxis_title="Lap", yaxis_title="Lap Time (s)")
    st.plotly_chart(fig, use_container_width=True)


def compute_wishbone_geometry(roll_angle_deg: float, wishbone_length_mm: float) -> Tuple[pd.DataFrame, float]:
    roll_rad = math.radians(roll_angle_deg)
    wheel_center_shift = wishbone_length_mm * math.sin(roll_rad)
    camber_change_deg = -math.degrees(math.atan2(wheel_center_shift, wishbone_length_mm))

    chassis_y = 360
    chassis_half_width = 200
    wheel_x = 400 + wheel_center_shift * 0.45

    geometry = pd.DataFrame(
        {
            "x": [-chassis_half_width, -80, wheel_x, wheel_x, 80, chassis_half_width],
            "y": [chassis_y, chassis_y - 85, chassis_y - 55, chassis_y - 195, chassis_y - 85, chassis_y],
            "segment": ["chassis", "upper arm", "upright", "upright", "lower arm", "chassis"],
        }
    )
    return geometry, camber_change_deg


def suspension_lab() -> None:
    st.subheader("MODULE 2: SUSPENSION LAB (KINEMATICS SIMULATOR)")
    roll_angle = st.sidebar.slider("Chassis Roll Angle (degrees)", min_value=-5.0, max_value=5.0, value=0.0, step=0.1)
    wishbone_length = st.sidebar.slider("Wishbone Length (mm)", min_value=300, max_value=500, value=380, step=5)

    geometry, camber = compute_wishbone_geometry(roll_angle, wishbone_length)
    st.metric("Resulting Camber Angle Change (degrees)", f"{camber:.2f}")

    col1, col2 = st.columns(2)

    with col1:
        schematic = go.Figure()
        schematic.add_trace(
            go.Scatter(
                x=geometry["x"],
                y=geometry["y"],
                mode="lines+markers",
                line=dict(width=4, color="#22d3ee"),
                marker=dict(size=10, color="#f97316"),
            )
        )
        schematic.update_layout(
            title="Double-Wishbone Geometry (2D Schematic)",
            template="plotly_dark",
            xaxis_title="Lateral Position",
            yaxis_title="Vertical Position",
            yaxis=dict(scaleanchor="x", scaleratio=1),
            showlegend=False,
        )
        st.plotly_chart(schematic, use_container_width=True)

    with col2:
        roll_range = np.linspace(-5, 5, 80)
        camber_series = [-math.degrees(math.atan2(wishbone_length * math.sin(math.radians(r)), wishbone_length)) for r in roll_range]
        camber_df = pd.DataFrame({"Roll Angle": roll_range, "Camber Change": camber_series})
        camber_fig = px.line(camber_df, x="Roll Angle", y="Camber Change", title="Camber Change vs. Roll Angle", template="plotly_dark")
        st.plotly_chart(camber_fig, use_container_width=True)


def telemetry_center() -> None:
    st.subheader("MODULE 3: TELEMETRY CENTER (REAL DATA VISUALIZER)")
    c1, c2 = st.columns(2)
    driver_number = c1.text_input("Driver Number", value=str(DEFAULT_DRIVER_NUMBER))
    session_key = c2.text_input("Session Key", value=str(DEFAULT_SESSION_KEY))

    try:
        session_key_int = int(session_key)
        driver_number_int = int(driver_number)
    except ValueError:
        st.error("Session key and driver number must be valid integers.")
        return

    raw_laps, laps_status = fetch_openf1("laps", session_key_int, driver_number_int)
    raw_car, car_status = fetch_openf1("car_data", session_key_int, driver_number_int, limit=TELEMETRY_FETCH_LIMIT)
    raw_loc, loc_status = fetch_openf1("location", session_key_int, driver_number_int, limit=TELEMETRY_FETCH_LIMIT)

    try:
        if raw_car and raw_loc:
            car_df = parse_car_data(raw_car)
            loc_df = parse_location_data(raw_loc)
            source = "real OpenF1 telemetry"

            lap_start, lap_end = get_lap_window(raw_laps)
            if lap_start is not None:
                car_df = car_df[car_df["date"] >= lap_start]
                loc_df = loc_df[loc_df["date"] >= lap_start]
            if lap_end is not None:
                car_df = car_df[car_df["date"] <= lap_end]
                loc_df = loc_df[loc_df["date"] <= lap_end]

            car_df = car_df.head(200)
            loc_df = loc_df.head(200)
        else:
            raise ValueError(f"car_data: {car_status}; location: {loc_status}; laps: {laps_status}")
    except Exception as exc:
        st.error(f"Telemetry API failed ({exc}). Switching to built-in synthetic telemetry.")
        synthetic_df = synthetic_session_dataframe(points=200)
        car_df = synthetic_df[["date", "speed", "throttle", "brake"]].copy()
        loc_df = synthetic_df[["date", "x", "y"]].copy()
        source = "synthetic fallback"

    car_df = normalize_date_column(car_df)
    loc_df = normalize_date_column(loc_df)

    car_df = car_df.dropna(subset=["date"])
    loc_df = loc_df.dropna(subset=["date"])

    car_df = car_df.sort_values("date")
    loc_df = loc_df.sort_values("date")

    if car_df.empty or loc_df.empty:
        st.warning("No telemetry data available for visualization.")
        return

    merged = pd.merge_asof(
        car_df,
        loc_df,
        on="date",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=2),
    ).dropna(subset=["x", "y"])

    if merged.empty:
        st.warning("Unable to align telemetry and location data.")
        return

    st.caption(f"Data source: {source}")

    trend_long = merged[["date", "speed", "throttle", "brake"]].melt(
        id_vars=["date"], var_name="Signal", value_name="Value"
    )

    trend_fig = px.line(
        trend_long,
        x="date",
        y="Value",
        color="Signal",
        template="plotly_dark",
        title="Speed, Throttle, and Braking Over Time",
    )
    st.plotly_chart(trend_fig, use_container_width=True)

    merged["velocity_state"] = merged["speed"] * np.where(merged["brake"] > 0, -1, 1)
    track_fig = px.scatter(
        merged,
        x="x",
        y="y",
        color="velocity_state",
        color_continuous_scale=[(0.0, "#ef4444"), (0.5, "#fbbf24"), (1.0, "#22c55e")],
        title="Track Map (Red = Braking, Green = Acceleration)",
        template="plotly_dark",
        hover_data={"speed": True, "throttle": True, "brake": True, "x": ":.1f", "y": ":.1f"},
    )
    track_fig.update_traces(marker=dict(size=8, opacity=0.85))
    track_fig.update_layout(yaxis=dict(scaleanchor="x", scaleratio=1))
    st.plotly_chart(track_fig, use_container_width=True)


def main() -> None:
    apply_theme()
    st.title("🏁 The Virtual Garage: An F1 Engineering Suite")
    st.sidebar.title("Garage Modules")
    module = st.sidebar.radio(
        "Select Module",
        [
            "THE AI PIT WALL (STRATEGY ENGINE)",
            "SUSPENSION LAB (KINEMATICS SIMULATOR)",
            "TELEMETRY CENTER (REAL DATA VISUALIZER)",
        ],
    )

    if module.startswith("THE AI PIT WALL"):
        strategy_engine()
    elif module.startswith("SUSPENSION LAB"):
        suspension_lab()
    else:
        telemetry_center()


if __name__ == "__main__":
    main()
