import logging
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

logger = logging.getLogger(__name__)

COMPOUND_DEGRADATION = {
    "SOFT": 4.8,
    "MEDIUM": 3.3,
    "HARD": 2.3,
    "INTERMEDIATE": 3.8,
    "WET": 4.2,
    "UNKNOWN": 3.5,
}


class OpenF1Error(RuntimeError):
    pass


class OpenF1DataError(OpenF1Error):
    pass


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
def fetch_openf1(endpoint: str, params: Dict[str, int]) -> List[Dict]:
    try:
        response = requests.get(f"{OPENF1_BASE}/{endpoint}", params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OpenF1Error(f"{endpoint} request failed: {exc}") from exc

    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise OpenF1DataError(f"{endpoint} returned invalid JSON") from exc

    if not isinstance(payload, list):
        raise OpenF1DataError(f"{endpoint} returned an unexpected response")
    if not payload:
        raise OpenF1DataError(f"{endpoint} returned no data")
    if not all(isinstance(item, dict) for item in payload):
        raise OpenF1DataError(f"{endpoint} returned malformed records")
    return payload


def mock_lap_data() -> List[Dict]:
    lap_times = [91.2, 91.7, 92.1, 92.6, 93.2, 94.1, 95.3, 96.5, 97.8]
    return [
        {"lap_number": idx + 1, "lap_duration": lap, "compound": "MEDIUM"}
        for idx, lap in enumerate(lap_times)
    ]


def mock_car_data() -> pd.DataFrame:
    points = 200
    t = np.arange(points)
    speed = 235 + 55 * np.sin(t / 15)
    throttle = np.clip(68 + 28 * np.sin(t / 11), 0, 100)
    brake = (throttle < 60).astype(int) * np.clip(100 - throttle, 0, 100)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=points, freq="2s"),
            "speed": speed,
            "throttle": throttle,
            "brake": brake,
        }
    )


def mock_location_data() -> pd.DataFrame:
    points = 200
    theta = np.linspace(0, 2 * np.pi, points)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=points, freq="2s"),
            "x": 1400 * np.cos(theta) + 120 * np.cos(3 * theta),
            "y": 900 * np.sin(theta) + 90 * np.sin(4 * theta),
        }
    )


def parse_laps(raw_laps: List[Dict]) -> pd.DataFrame:
    rows = []
    invalid_rows = 0
    for row in raw_laps:
        lap_time = row.get("lap_duration") or row.get("lap_time")
        lap_no = row.get("lap_number")
        compound = row.get("compound") or row.get("tyre_compound") or row.get("stint_compound") or "UNKNOWN"
        if lap_time is None or lap_no is None:
            invalid_rows += 1
            continue
        try:
            parsed_lap_time = float(lap_time)
            parsed_lap_no = int(lap_no)
            if not math.isfinite(parsed_lap_time):
                raise ValueError("lap time must be finite")
            rows.append(
                {
                    "lap_number": parsed_lap_no,
                    "lap_time": parsed_lap_time,
                    "compound": str(compound).upper(),
                }
            )
        except (TypeError, ValueError):
            invalid_rows += 1

    if invalid_rows:
        logger.warning("Ignored %d malformed lap records", invalid_rows)
    if raw_laps and not rows:
        raise OpenF1DataError("lap data contained no valid records")
    return (
        pd.DataFrame(rows).sort_values("lap_number")
        if rows
        else pd.DataFrame(columns=["lap_number", "lap_time", "compound"])
    )


def strategy_engine() -> None:
    st.subheader("MODULE 1: THE AI PIT WALL (STRATEGY ENGINE)")
    c1, c2 = st.columns(2)
    driver_number = c1.number_input("Driver Number", min_value=1, max_value=99, value=DEFAULT_DRIVER_NUMBER, step=1)
    session_key = c2.number_input("Session Key", min_value=1, value=DEFAULT_SESSION_KEY, step=1)

    try:
        raw_laps = fetch_openf1(
            "laps",
            {"session_key": int(session_key), "driver_number": int(driver_number)},
        )
        laps_df = parse_laps(raw_laps)
        data_source = "real OpenF1 telemetry"
    except OpenF1Error as exc:
        st.error(f"OpenF1 lap data unavailable ({exc}). Switching to built-in mock laps.")
        laps_df = parse_laps(mock_lap_data())
        data_source = "mock fallback"

    if laps_df.empty:
        st.warning("No lap data available for strategy simulation.")
        return

    current_compound = laps_df["compound"].iloc[-1] if not laps_df.empty else "UNKNOWN"
    deg_rate = COMPOUND_DEGRADATION.get(current_compound, COMPOUND_DEGRADATION["UNKNOWN"])

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
    upright_height = 140
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


def parse_car_data(raw: List[Dict]) -> pd.DataFrame:
    rows = []
    invalid_rows = 0
    for point in raw:
        ts = point.get("date") or point.get("timestamp")
        speed = point.get("speed")
        throttle = point.get("throttle")
        brake = point.get("brake")
        if ts is None or speed is None or throttle is None or brake is None:
            invalid_rows += 1
            continue
        try:
            timestamp = pd.to_datetime(ts, utc=True)
            parsed_speed = float(speed)
            parsed_throttle = float(throttle)
            parsed_brake = float(brake)
            if pd.isna(timestamp) or not all(
                math.isfinite(value)
                for value in (parsed_speed, parsed_throttle, parsed_brake)
            ):
                raise ValueError("telemetry values must be valid")
            rows.append(
                {
                    "timestamp": timestamp,
                    "speed": parsed_speed,
                    "throttle": parsed_throttle,
                    "brake": parsed_brake,
                }
            )
        except (TypeError, ValueError):
            invalid_rows += 1

    if invalid_rows:
        logger.warning("Ignored %d malformed car telemetry records", invalid_rows)
    if raw and not rows:
        raise OpenF1DataError("car telemetry contained no valid records")
    return (
        pd.DataFrame(rows).sort_values("timestamp")
        if rows
        else pd.DataFrame(columns=["timestamp", "speed", "throttle", "brake"])
    )


def parse_location_data(raw: List[Dict]) -> pd.DataFrame:
    rows = []
    invalid_rows = 0
    for point in raw:
        ts = point.get("date") or point.get("timestamp")
        x, y = point.get("x"), point.get("y")
        if ts is None or x is None or y is None:
            invalid_rows += 1
            continue
        try:
            timestamp = pd.to_datetime(ts, utc=True)
            parsed_x = float(x)
            parsed_y = float(y)
            if pd.isna(timestamp) or not all(
                math.isfinite(value) for value in (parsed_x, parsed_y)
            ):
                raise ValueError("location values must be valid")
            rows.append(
                {
                    "timestamp": timestamp,
                    "x": parsed_x,
                    "y": parsed_y,
                }
            )
        except (TypeError, ValueError):
            invalid_rows += 1

    if invalid_rows:
        logger.warning("Ignored %d malformed location records", invalid_rows)
    if raw and not rows:
        raise OpenF1DataError("location data contained no valid records")
    return (
        pd.DataFrame(rows).sort_values("timestamp")
        if rows
        else pd.DataFrame(columns=["timestamp", "x", "y"])
    )


def telemetry_center() -> None:
    st.subheader("MODULE 3: TELEMETRY CENTER (REAL DATA VISUALIZER)")
    c1, c2 = st.columns(2)
    driver_number = c1.text_input("Driver Number", value=str(DEFAULT_DRIVER_NUMBER))
    session_key = c2.text_input("Session Key", value=str(DEFAULT_SESSION_KEY))

    try:
        params = {
            "session_key": int(session_key),
            "driver_number": int(driver_number),
            "limit": 200,
        }
    except ValueError:
        st.error("Driver Number and Session Key must be integers.")
        return

    try:
        raw_car = fetch_openf1("car_data", params)
        raw_loc = fetch_openf1("location", params)
        car_df = parse_car_data(raw_car)
        loc_df = parse_location_data(raw_loc)
        source = "real OpenF1 telemetry"
    except OpenF1Error as exc:
        st.error(
            f"OpenF1 telemetry unavailable ({exc}). Switching to built-in mock telemetry."
        )
        car_df = mock_car_data()
        loc_df = mock_location_data()
        source = "mock fallback"

    if car_df.empty or loc_df.empty:
        st.warning("No telemetry data available for visualization.")
        return

    merged = pd.merge_asof(
        car_df.sort_values("timestamp"),
        loc_df.sort_values("timestamp"),
        on="timestamp",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=2),
    ).dropna(subset=["x", "y"])

    if merged.empty:
        st.warning("Unable to align telemetry and location data.")
        return

    st.caption(f"Data source: {source}")

    trend_df = merged[["timestamp", "speed", "throttle", "brake"]].copy()
    trend_df["timestamp"] = trend_df["timestamp"].dt.tz_convert(None)
    trend_long = trend_df.melt(id_vars=["timestamp"], var_name="Signal", value_name="Value")

    trend_fig = px.line(
        trend_long,
        x="timestamp",
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
        hover_data={"speed": True, "throttle": True, "brake": True, "x": ':.1f', "y": ':.1f'},
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
