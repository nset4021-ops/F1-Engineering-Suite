import html
import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from f1_utils import camber_change_deg, extract_timestamp, parse_records

OPENF1_BASE = "https://api.openf1.org/v1"
DEFAULT_SESSION_KEY = 9839
DEFAULT_DRIVER_NUMBER = 44

COMPOUND_DEGRADATION = {
    "SOFT": 4.8,
    "MEDIUM": 3.3,
    "HARD": 2.3,
    "INTERMEDIATE": 3.8,
    "WET": 4.2,
    "UNKNOWN": 3.5,
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
def fetch_openf1(endpoint: str, params: Dict[str, int]) -> Tuple[List[Dict], str]:
    try:
        response = requests.get(f"{OPENF1_BASE}/{endpoint}", params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) == 0:
            raise ValueError("No data returned from OpenF1")
        return payload, "real"
    except (requests.RequestException, ValueError) as exc:
        return [], str(exc)


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


def _lap_row(row: Dict) -> Dict:
    lap_time = row.get("lap_duration") or row.get("lap_time")
    lap_no = row.get("lap_number")
    compound = row.get("compound") or row.get("tyre_compound") or row.get("stint_compound") or "UNKNOWN"
    if lap_time is None or lap_no is None:
        return None
    return {"lap_number": int(lap_no), "lap_time": float(lap_time), "compound": str(compound).upper()}


def parse_laps(raw_laps: List[Dict]) -> pd.DataFrame:
    return parse_records(raw_laps, _lap_row, ["lap_number", "lap_time", "compound"], "lap_number")


def strategy_engine() -> None:
    st.subheader("MODULE 1: THE AI PIT WALL (STRATEGY ENGINE)")
    c1, c2 = st.columns(2)
    driver_number = c1.number_input("Driver Number", min_value=1, max_value=99, value=DEFAULT_DRIVER_NUMBER, step=1)
    session_key = c2.number_input("Session Key", min_value=1, value=DEFAULT_SESSION_KEY, step=1)

    raw_laps, status = fetch_openf1("laps", {"session_key": int(session_key), "driver_number": int(driver_number)})
    if raw_laps:
        laps_df = parse_laps(raw_laps)
        data_source = "real OpenF1 telemetry"
    else:
        st.error(f"Lap API failed ({status}). Switching to built-in mock laps.")
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
        safe_compound = html.escape(str(current_compound))
        st.markdown(
            f"<div class='warning-box'>BOX BOX: Tyre grip low. Recommend Pit Stop for {safe_compound}.</div>",
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
    wheel_center_shift = wishbone_length_mm * math.sin(math.radians(roll_angle_deg))
    camber_change = camber_change_deg(roll_angle_deg, wishbone_length_mm)

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
    return geometry, camber_change


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
        camber_series = [camber_change_deg(r, wishbone_length) for r in roll_range]
        camber_df = pd.DataFrame({"Roll Angle": roll_range, "Camber Change": camber_series})
        camber_fig = px.line(camber_df, x="Roll Angle", y="Camber Change", title="Camber Change vs. Roll Angle", template="plotly_dark")
        st.plotly_chart(camber_fig, use_container_width=True)


def _car_row(point: Dict) -> Dict:
    ts = extract_timestamp(point)
    speed = point.get("speed")
    throttle = point.get("throttle")
    brake = point.get("brake")
    if ts is None or speed is None or throttle is None or brake is None:
        return None
    return {
        "timestamp": pd.to_datetime(ts, utc=True, errors="coerce"),
        "speed": float(speed),
        "throttle": float(throttle),
        "brake": float(brake),
    }


def parse_car_data(raw: List[Dict]) -> pd.DataFrame:
    return parse_records(
        raw,
        _car_row,
        ["timestamp", "speed", "throttle", "brake"],
        "timestamp",
        dropna_subset=["timestamp"],
    )


def _location_row(point: Dict) -> Dict:
    ts = extract_timestamp(point)
    x, y = point.get("x"), point.get("y")
    if ts is None or x is None or y is None:
        return None
    return {"timestamp": pd.to_datetime(ts, utc=True, errors="coerce"), "x": float(x), "y": float(y)}


def parse_location_data(raw: List[Dict]) -> pd.DataFrame:
    return parse_records(
        raw,
        _location_row,
        ["timestamp", "x", "y"],
        "timestamp",
        dropna_subset=["timestamp"],
    )


def telemetry_center() -> None:
    st.subheader("MODULE 3: TELEMETRY CENTER (REAL DATA VISUALIZER)")
    c1, c2 = st.columns(2)
    driver_number = c1.text_input("Driver Number", value=str(DEFAULT_DRIVER_NUMBER))
    session_key = c2.text_input("Session Key", value=str(DEFAULT_SESSION_KEY))

    try:
        driver_number_int = int(str(driver_number).strip())
        session_key_int = int(str(session_key).strip())
    except ValueError:
        st.error("Driver Number and Session Key must be whole numbers.")
        return

    if not (1 <= driver_number_int <= 99):
        st.error("Driver Number must be between 1 and 99.")
        return
    if session_key_int < 1:
        st.error("Session Key must be a positive integer.")
        return

    params = {"session_key": session_key_int, "driver_number": driver_number_int, "limit": 200}
    raw_car, car_status = fetch_openf1("car_data", params)
    raw_loc, loc_status = fetch_openf1("location", params)

    if raw_car and raw_loc:
        car_df = parse_car_data(raw_car)
        loc_df = parse_location_data(raw_loc)
        source = "real OpenF1 telemetry"
    else:
        st.error(
            f"Telemetry API failed (car_data: {car_status}; location: {loc_status}). Switching to built-in mock telemetry."
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


SYNTHETIC_DRIVERS = [
    {"driver_number": 1, "name_acronym": "VER", "full_name": "Max Verstappen", "team_name": "Red Bull Racing", "team_colour": "3671C6"},
    {"driver_number": 4, "name_acronym": "NOR", "full_name": "Lando Norris", "team_name": "McLaren", "team_colour": "FF8000"},
    {"driver_number": 16, "name_acronym": "LEC", "full_name": "Charles Leclerc", "team_name": "Ferrari", "team_colour": "E80020"},
    {"driver_number": 44, "name_acronym": "HAM", "full_name": "Lewis Hamilton", "team_name": "Mercedes", "team_colour": "27F4D2"},
    {"driver_number": 63, "name_acronym": "RUS", "full_name": "George Russell", "team_name": "Mercedes", "team_colour": "27F4D2"},
    {"driver_number": 81, "name_acronym": "PIA", "full_name": "Oscar Piastri", "team_name": "McLaren", "team_colour": "FF8000"},
    {"driver_number": 55, "name_acronym": "SAI", "full_name": "Carlos Sainz", "team_name": "Ferrari", "team_colour": "E80020"},
    {"driver_number": 14, "name_acronym": "ALO", "full_name": "Fernando Alonso", "team_name": "Aston Martin", "team_colour": "229971"},
    {"driver_number": 11, "name_acronym": "PER", "full_name": "Sergio Perez", "team_name": "Red Bull Racing", "team_colour": "3671C6"},
    {"driver_number": 22, "name_acronym": "TSU", "full_name": "Yuki Tsunoda", "team_name": "RB", "team_colour": "6692FF"},
]


def parse_drivers(raw: List[Dict]) -> List[Dict]:
    drivers = []
    seen = set()
    for row in raw:
        number = row.get("driver_number")
        if number is None or number in seen:
            continue
        seen.add(number)
        drivers.append(
            {
                "driver_number": int(number),
                "name_acronym": str(row.get("name_acronym") or f"#{number}"),
                "full_name": str(row.get("full_name") or row.get("broadcast_name") or f"Driver {number}"),
                "team_name": str(row.get("team_name") or "Unknown Team"),
                "team_colour": str(row.get("team_colour") or "9ca3af"),
            }
        )
    return drivers


def simulate_race(drivers: List[Dict], num_laps: int, base_lap_time: float = 90.0, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for idx, driver in enumerate(drivers):
        pace_offset = 0.12 * idx + rng.normal(0.0, 0.15)
        consistency = abs(rng.normal(0.35, 0.12))
        for lap in range(1, num_laps + 1):
            degradation = 0.045 * lap
            noise = rng.normal(0.0, consistency)
            lap_time = base_lap_time + pace_offset + degradation + noise
            rows.append(
                {
                    "driver_number": driver["driver_number"],
                    "name_acronym": driver["name_acronym"],
                    "full_name": driver["full_name"],
                    "team_name": driver["team_name"],
                    "team_colour": driver["team_colour"],
                    "lap_number": lap,
                    "lap_time": lap_time,
                }
            )
    race_df = pd.DataFrame(rows)
    race_df["cumulative_time"] = race_df.groupby("driver_number")["lap_time"].cumsum()
    race_df["position"] = race_df.groupby("lap_number")["cumulative_time"].rank(method="min").astype(int)
    return race_df


def racing_simulator() -> None:
    st.subheader("MODULE 4: RACING SIMULATOR (GRID SHOOTOUT)")

    use_real_drivers = st.toggle(
        "Use real OpenF1 drivers",
        value=False,
        help="Off: run the simulation with built-in synthetic drivers. On: pull the actual driver grid from OpenF1.",
    )

    if use_real_drivers:
        session_key = st.number_input(
            "Session Key", min_value=1, value=DEFAULT_SESSION_KEY, step=1, key="race_session_key"
        )
        raw_drivers, status = fetch_openf1("drivers", {"session_key": int(session_key)})
        drivers = parse_drivers(raw_drivers)
        if drivers:
            driver_source = "real OpenF1 grid"
        else:
            st.error(f"Drivers API failed ({status}). Falling back to synthetic drivers.")
            drivers = SYNTHETIC_DRIVERS
            driver_source = "synthetic fallback"
    else:
        drivers = SYNTHETIC_DRIVERS
        driver_source = "synthetic drivers"

    if not drivers:
        st.warning("No drivers available to simulate.")
        return

    c1, c2 = st.columns(2)
    grid_size = c1.slider("Grid Size", min_value=2, max_value=len(drivers), value=min(10, len(drivers)), step=1)
    num_laps = c2.slider("Race Distance (laps)", min_value=3, max_value=70, value=20, step=1)

    grid = drivers[:grid_size]
    race_df = simulate_race(grid, num_laps)

    st.caption(f"Driver source: {driver_source} · {grid_size} drivers · {num_laps} laps")

    final_lap = race_df[race_df["lap_number"] == num_laps].sort_values("position")
    winner = final_lap.iloc[0]
    leader_time = winner["cumulative_time"]
    podium = " · ".join(f"P{int(r.position)} {r.name_acronym}" for r in final_lap.head(3).itertuples())

    m1, m2, m3 = st.columns(3)
    m1.metric("Winner", winner["name_acronym"])
    m2.metric("Race Time (s)", f"{leader_time:.1f}")
    m3.metric("Fastest Lap (s)", f"{race_df['lap_time'].min():.3f}")
    st.markdown(f"**Podium:** {podium}")

    color_map = {row["name_acronym"]: f"#{row['team_colour']}" for row in grid}

    pos_fig = px.line(
        race_df,
        x="lap_number",
        y="position",
        color="name_acronym",
        markers=False,
        title="Race Positions by Lap",
        template="plotly_dark",
        color_discrete_map=color_map,
    )
    pos_fig.update_yaxes(autorange="reversed", dtick=1, title="Position")
    pos_fig.update_xaxes(title="Lap")
    st.plotly_chart(pos_fig, use_container_width=True)

    standings = final_lap[["position", "name_acronym", "full_name", "team_name", "cumulative_time"]].copy()
    standings["gap_to_leader"] = standings["cumulative_time"] - leader_time
    standings = standings.rename(
        columns={
            "position": "Pos",
            "name_acronym": "Driver",
            "full_name": "Name",
            "team_name": "Team",
            "cumulative_time": "Total Time (s)",
            "gap_to_leader": "Gap (s)",
        }
    )
    standings["Total Time (s)"] = standings["Total Time (s)"].round(3)
    standings["Gap (s)"] = standings["Gap (s)"].round(3)
    st.dataframe(
        standings[["Pos", "Driver", "Name", "Team", "Total Time (s)", "Gap (s)"]].set_index("Pos"),
        use_container_width=True,
    )


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
            "RACING SIMULATOR (GRID SHOOTOUT)",
        ],
    )

    if module.startswith("THE AI PIT WALL"):
        strategy_engine()
    elif module.startswith("SUSPENSION LAB"):
        suspension_lab()
    elif module.startswith("TELEMETRY CENTER"):
        telemetry_center()
    else:
        racing_simulator()


if __name__ == "__main__":
    main()
