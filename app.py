import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

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
            :root {
                --garage-bg: var(--st-background-color);
                --garage-panel: var(--st-secondary-background-color);
                --garage-text: var(--st-text-color);
                --garage-accent: var(--st-primary-color);
                --garage-border: color-mix(in srgb, var(--st-text-color) 16%, transparent);
                --garage-border-strong: color-mix(in srgb, var(--st-primary-color) 28%, transparent);
                --garage-soft-accent: color-mix(in srgb, var(--st-primary-color) 14%, transparent);
            }

            .stApp {
                color: var(--garage-text);
                background:
                    radial-gradient(circle at 5% 0%, color-mix(in srgb, var(--garage-accent) 12%, transparent) 0%, transparent 40%),
                    radial-gradient(circle at 95% 0%, color-mix(in srgb, var(--garage-accent) 10%, transparent) 0%, transparent 45%),
                    var(--garage-bg);
            }

            .main .block-container {
                padding-top: 1.2rem;
                padding-bottom: 2rem;
                max-width: 1500px;
            }

            .garage-card-grid {
                display: flex;
                gap: 0.9rem;
                flex-wrap: wrap;
                margin: 0.1rem 0 1rem 0;
            }

            .garage-card {
                flex: 1 1 210px;
                min-width: 180px;
                border: 1px solid var(--garage-border);
                background: linear-gradient(
                    180deg,
                    color-mix(in srgb, var(--garage-panel) 88%, transparent) 0%,
                    color-mix(in srgb, var(--garage-bg) 92%, transparent) 100%
                );
                padding: 0.9rem 1rem;
                border-radius: 0.9rem;
            }

            .garage-card-label {
                font-size: 0.74rem;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                opacity: 0.75;
                margin-bottom: 0.3rem;
            }

            .garage-card-value {
                font-size: clamp(1.05rem, 2vw, 1.45rem);
                font-weight: 700;
                line-height: 1.2;
            }

            .strategy-status {
                border: 1px solid var(--garage-border-strong);
                border-radius: 0.95rem;
                padding: 0.95rem 1.1rem;
                margin-bottom: 0.9rem;
                background: linear-gradient(
                    90deg,
                    color-mix(in srgb, var(--garage-accent) 16%, var(--garage-panel) 84%) 0%,
                    color-mix(in srgb, var(--garage-panel) 84%, var(--garage-bg) 16%) 100%
                );
                box-shadow:
                    0 0 0.1rem color-mix(in srgb, var(--garage-accent) 40%, transparent),
                    0 0 1.2rem color-mix(in srgb, var(--garage-accent) 20%, transparent);
            }

            .strategy-status h4 {
                margin: 0 0 0.35rem 0;
                font-size: 0.9rem;
                letter-spacing: 0.03em;
                text-transform: uppercase;
            }

            .strategy-status p {
                margin: 0;
                font-size: 1rem;
                font-weight: 600;
            }

            .garage-note {
                border: 1px solid var(--garage-border);
                background: color-mix(in srgb, var(--garage-panel) 84%, transparent);
                border-radius: 0.75rem;
                padding: 0.7rem 0.8rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def themed_layout(fig: go.Figure, title: str | None = None) -> go.Figure:
    is_dark = str(st.get_option("theme.base") or "light").lower() == "dark"
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5e7eb" if is_dark else "#111827"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=48, r=24, t=62 if title else 28, b=45),
    )
    if title:
        fig.update_layout(title=title)
    return fig


@st.cache_data(show_spinner=False, ttl=60)
def fetch_openf1(endpoint: str, params: Dict[str, int]) -> Tuple[List[Dict], str]:
    try:
        response = requests.get(f"{OPENF1_BASE}/{endpoint}", params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError("No records returned")
        return payload, "real"
    except (requests.RequestException, ValueError) as exc:
        return [], str(exc)


def normalize_time_column(df: pd.DataFrame, column: str = "timestamp") -> pd.DataFrame:
    if column not in df.columns:
        df[column] = pd.NaT
    df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")
    return df.dropna(subset=[column]).sort_values(column).drop_duplicates(subset=[column])


def render_metric_cards(metrics: List[Tuple[str, str]]) -> None:
    cards = "".join(
        f"<div class='garage-card'><div class='garage-card-label'>{label}</div><div class='garage-card-value'>{value}</div></div>"
        for label, value in metrics
    )
    st.markdown(f"<div class='garage-card-grid'>{cards}</div>", unsafe_allow_html=True)


def fallback_laps(lap_count: int = 24) -> pd.DataFrame:
    lap_idx = np.arange(1, lap_count + 1)
    base = 90.8 + 0.11 * lap_idx
    degradation = 0.035 * np.power(lap_idx, 1.35)
    rng = np.random.default_rng(44)
    noise = rng.normal(0, 0.11, size=lap_count)
    compounds = np.where(lap_idx <= 11, "SOFT", np.where(lap_idx <= 18, "MEDIUM", "HARD"))
    laps = pd.DataFrame(
        {
            "lap_number": lap_idx,
            "lap_time": np.round(base + degradation + noise, 3),
            "compound": compounds,
        }
    )
    laps["lap_time"] = laps["lap_time"].clip(lower=75, upper=140)
    return laps


def parse_laps(raw_laps: List[Dict]) -> pd.DataFrame:
    if not raw_laps:
        return pd.DataFrame(columns=["lap_number", "lap_time", "compound"])

    df = pd.DataFrame(raw_laps)
    lap_col = "lap_duration" if "lap_duration" in df.columns else "lap_time"
    compound_col = next((c for c in ["compound", "tyre_compound", "stint_compound"] if c in df.columns), None)
    if compound_col is not None:
        compound = df[compound_col].fillna("UNKNOWN").astype(str).str.upper()
    else:
        compound = "UNKNOWN"
    result = pd.DataFrame(
        {
            "lap_number": pd.to_numeric(df.get("lap_number"), errors="coerce"),
            "lap_time": pd.to_numeric(df.get(lap_col), errors="coerce"),
            "compound": compound,
        }
    )
    result = result.dropna(subset=["lap_number", "lap_time"]).copy()
    if result.empty:
        return pd.DataFrame(columns=["lap_number", "lap_time", "compound"])
    result["lap_number"] = result["lap_number"].astype(int)
    result["lap_time"] = result["lap_time"].clip(lower=45, upper=220)
    return result.sort_values("lap_number").drop_duplicates(subset=["lap_number"], keep="last")


def generate_fallback_telemetry(points: int = 900, hz: int = 5) -> Tuple[pd.DataFrame, pd.DataFrame]:
    t = np.arange(points) / hz
    timestamps = pd.to_datetime("2026-01-01T00:00:00Z") + pd.to_timedelta(t, unit="s")

    theta = np.linspace(0, 2 * np.pi * 1.65, points)
    x = 1850 * np.cos(theta) + 220 * np.cos(3.1 * theta)
    y = 1120 * np.sin(theta) + 145 * np.sin(4.2 * theta)

    dx = np.gradient(x)
    dy = np.gradient(y)
    curvature = np.abs(np.gradient(np.arctan2(dy, dx)))
    raw_speed = 312 - 2150 * curvature + 15 * np.sin(theta * 2.0)
    speed = np.clip(raw_speed, 74, 333)

    throttle = np.clip(100 - curvature * 12000 + 10 * np.sin(theta * 3.5), 8, 100)
    brake = np.clip(curvature * 9300 - 45, 0, 100)

    car_df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "speed": speed,
            "throttle": throttle,
            "brake": brake,
        }
    )

    loc_df = pd.DataFrame(
        {
            "timestamp": timestamps + pd.to_timedelta(np.where(np.mod(np.arange(points), 7) == 0, 120, -80), unit="ms"),
            "x": x,
            "y": y,
        }
    )

    return car_df, loc_df


def parse_car_data(raw: List[Dict]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["timestamp", "speed", "throttle", "brake"])

    df = pd.DataFrame(raw)
    result = pd.DataFrame(
        {
            "timestamp": df.get("date", df.get("timestamp")),
            "speed": pd.to_numeric(df.get("speed"), errors="coerce"),
            "throttle": pd.to_numeric(df.get("throttle"), errors="coerce"),
            "brake": pd.to_numeric(df.get("brake"), errors="coerce"),
        }
    )
    result = normalize_time_column(result)
    result = result.dropna(subset=["speed", "throttle", "brake"]).copy()
    if result.empty:
        return pd.DataFrame(columns=["timestamp", "speed", "throttle", "brake"])

    result["speed"] = result["speed"].clip(lower=0, upper=390)
    result["throttle"] = result["throttle"].clip(lower=0, upper=100)
    result["brake"] = result["brake"].clip(lower=0, upper=100)
    return result


def parse_location_data(raw: List[Dict]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["timestamp", "x", "y"])

    df = pd.DataFrame(raw)
    result = pd.DataFrame(
        {
            "timestamp": df.get("date", df.get("timestamp")),
            "x": pd.to_numeric(df.get("x"), errors="coerce"),
            "y": pd.to_numeric(df.get("y"), errors="coerce"),
        }
    )
    result = normalize_time_column(result)
    result = result.dropna(subset=["x", "y"])
    return result


def ensure_telemetry_frames(car_df: pd.DataFrame, loc_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    if len(car_df) < 60 or len(loc_df) < 60:
        fallback_car, fallback_loc = generate_fallback_telemetry()
        return fallback_car, fallback_loc, "mock fallback (validation recovery)"

    if not car_df["timestamp"].is_monotonic_increasing:
        car_df = car_df.sort_values("timestamp")
    if not loc_df["timestamp"].is_monotonic_increasing:
        loc_df = loc_df.sort_values("timestamp")

    if car_df["timestamp"].max() < loc_df["timestamp"].min() or loc_df["timestamp"].max() < car_df["timestamp"].min():
        fallback_car, fallback_loc = generate_fallback_telemetry()
        return fallback_car, fallback_loc, "mock fallback (timestamp mismatch recovery)"

    return car_df, loc_df, "real OpenF1 telemetry"


def strategy_engine() -> None:
    st.subheader("MODULE 1: THE AI PIT WALL")

    if "race_clock_s" not in st.session_state:
        st.session_state.race_clock_s = 0
    if "race_clock_last_tick" not in st.session_state:
        st.session_state.race_clock_last_tick = time.time()

    controls = st.columns([1.1, 1.1, 0.7, 0.7, 1])
    driver_number = controls[0].number_input("Driver Number", min_value=1, max_value=99, value=DEFAULT_DRIVER_NUMBER, step=1)
    session_key = controls[1].number_input("Session Key", min_value=1, value=DEFAULT_SESSION_KEY, step=1)
    tick_step = controls[2].selectbox("Tick (+s)", [1, 2, 5, 10], index=2)
    auto_tick = controls[3].toggle("Auto Tick", value=True)

    if controls[4].button("Reset Clock", use_container_width=True):
        st.session_state.race_clock_s = 0
        st.session_state.race_clock_last_tick = time.time()

    now = time.time()
    elapsed = max(0, int(now - st.session_state.race_clock_last_tick))
    if auto_tick and elapsed > 0:
        st.session_state.race_clock_s += elapsed * int(tick_step)
        st.session_state.race_clock_last_tick = now
        st.rerun()
    elif not auto_tick and controls[4].button("Advance Clock", use_container_width=True):
        st.session_state.race_clock_s += int(tick_step)
        st.session_state.race_clock_last_tick = now
    else:
        st.session_state.race_clock_last_tick = now

    raw_laps, status = fetch_openf1("laps", {"session_key": int(session_key), "driver_number": int(driver_number)})
    laps_df = parse_laps(raw_laps)
    source = "real OpenF1 telemetry"

    if laps_df.empty:
        laps_df = fallback_laps()
        source = f"mock fallback ({status})"

    compound = laps_df["compound"].iloc[-1]
    deg_rate = COMPOUND_DEGRADATION.get(compound, COMPOUND_DEGRADATION["UNKNOWN"])

    lap_idx = np.arange(len(laps_df))
    baseline = laps_df["lap_time"].iloc[:3].mean() if len(laps_df) >= 3 else laps_df["lap_time"].iloc[0]
    lap_drift = np.maximum(laps_df["lap_time"].to_numpy() - baseline, 0)
    laps_df["grip_pct"] = np.clip(100 - deg_rate * lap_idx - 2.4 * lap_drift, 0, 100)
    laps_df["cumulative_time_s"] = laps_df["lap_time"].cumsum()

    mm, ss = divmod(int(st.session_state.race_clock_s), 60)
    hh, mm = divmod(mm, 60)
    clock = f"{hh:02d}:{mm:02d}:{ss:02d}"

    render_metric_cards(
        [
            ("Race Clock", clock),
            ("Current Compound", compound),
            ("Latest Lap (s)", f"{laps_df['lap_time'].iloc[-1]:.3f}"),
            ("Estimated Grip", f"{laps_df['grip_pct'].iloc[-1]:.1f}%"),
        ]
    )

    grip_now = laps_df["grip_pct"].iloc[-1]
    if grip_now < 38:
        status_msg = f"BOX THIS LAP • Critical grip drop detected ({grip_now:.1f}%)."
    elif grip_now < 52:
        status_msg = f"Prepare pit window • Degradation trending high ({grip_now:.1f}%)."
    else:
        status_msg = f"Tyre condition stable • Continue push cycle ({grip_now:.1f}%)."

    st.markdown(
        f"""
        <div class="strategy-status">
            <h4>AI Strategy Advisory Panel</h4>
            <p>{status_msg}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Data source: {source}")

    strategy_fig = make_subplots(specs=[[{"secondary_y": True}]])
    strategy_fig.add_trace(
        go.Scatter(
            x=laps_df["lap_number"],
            y=laps_df["grip_pct"],
            mode="lines+markers",
            name="Tyre Grip %",
            line=dict(width=3),
        ),
        secondary_y=False,
    )
    strategy_fig.add_trace(
        go.Scatter(
            x=laps_df["lap_number"],
            y=laps_df["cumulative_time_s"],
            mode="lines+markers",
            name="Cumulative Lap Time (s)",
            line=dict(width=2.8, dash="dot"),
        ),
        secondary_y=True,
    )
    strategy_fig.update_xaxes(title_text="Lap Number")
    strategy_fig.update_yaxes(title_text="Tyre Grip (%)", secondary_y=False)
    strategy_fig.update_yaxes(title_text="Cumulative Time (s)", secondary_y=True)
    themed_layout(strategy_fig, "Tyre Degradation Curve vs Cumulative Lap Time")
    st.plotly_chart(strategy_fig, use_container_width=True)


def compute_wishbone_state(
    roll_deg: float,
    heave_mm: float,
    track_mm: float,
    upper_length_mm: float,
    lower_length_mm: float,
) -> Tuple[pd.DataFrame, float]:
    roll_rad = np.deg2rad(roll_deg)

    inner_upper = np.array([0.0, 235.0])
    inner_lower = np.array([0.0, 70.0])

    roll_vertical_shift = np.tan(roll_rad) * (track_mm * 0.08)
    heave_shift = heave_mm * 0.5

    inner_upper_dyn = inner_upper + np.array([0.0, roll_vertical_shift + heave_shift])
    inner_lower_dyn = inner_lower + np.array([0.0, roll_vertical_shift + heave_shift])

    upper_angle = np.deg2rad(-16 + 0.92 * roll_deg + 0.03 * heave_mm)
    lower_angle = np.deg2rad(6 + 0.55 * roll_deg + 0.018 * heave_mm)

    upper_vector = np.array([np.cos(upper_angle), np.sin(upper_angle)]) * upper_length_mm
    lower_vector = np.array([np.cos(lower_angle), np.sin(lower_angle)]) * lower_length_mm

    outer_upper = inner_upper_dyn + upper_vector
    outer_lower = inner_lower_dyn + lower_vector

    upright_vector = outer_upper - outer_lower
    camber_change = -np.degrees(np.arctan2(upright_vector[0], upright_vector[1]))

    wheel_center = (outer_upper + outer_lower) / 2
    tire_top = wheel_center + np.array([-36.0, 120.0])
    tire_bottom = wheel_center + np.array([36.0, -120.0])

    geometry = pd.DataFrame(
        {
            "segment": [
                "Upper Arm",
                "Upper Arm",
                "Lower Arm",
                "Lower Arm",
                "Upright",
                "Upright",
                "Tyre",
                "Tyre",
            ],
            "x": [
                inner_upper_dyn[0],
                outer_upper[0],
                inner_lower_dyn[0],
                outer_lower[0],
                outer_lower[0],
                outer_upper[0],
                tire_bottom[0],
                tire_top[0],
            ],
            "y": [
                inner_upper_dyn[1],
                outer_upper[1],
                inner_lower_dyn[1],
                outer_lower[1],
                outer_lower[1],
                outer_upper[1],
                tire_bottom[1],
                tire_top[1],
            ],
            "node_order": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )
    return geometry, float(camber_change)


def suspension_lab() -> None:
    st.subheader("MODULE 2: THE SUSPENSION LAB")

    controls = st.columns(4)
    roll_angle = controls[0].slider("Roll Angle (deg)", min_value=-8.0, max_value=8.0, value=0.0, step=0.1)
    heave_mm = controls[1].slider("Wheel Heave (mm)", min_value=-40.0, max_value=40.0, value=0.0, step=1.0)
    upper_len = controls[2].slider("Upper Arm Length (mm)", min_value=240, max_value=420, value=330, step=5)
    lower_len = controls[3].slider("Lower Arm Length (mm)", min_value=260, max_value=460, value=390, step=5)

    geometry, camber = compute_wishbone_state(roll_angle, heave_mm, 1600.0, float(upper_len), float(lower_len))

    render_metric_cards(
        [
            ("Computed Camber Δ", f"{camber:.2f}°"),
            ("Roll Input", f"{roll_angle:.1f}°"),
            ("Wheel Heave", f"{heave_mm:.0f} mm"),
            ("Arm Ratio", f"{upper_len/lower_len:.3f}"),
        ]
    )

    col1, col2 = st.columns([1.25, 1])

    with col1:
        schematic = go.Figure()
        for segment in ["Upper Arm", "Lower Arm", "Upright", "Tyre"]:
            seg = geometry[geometry["segment"] == segment].sort_values("node_order")
            schematic.add_trace(
                go.Scatter(
                    x=seg["x"],
                    y=seg["y"],
                    mode="lines+markers",
                    name=segment,
                    marker=dict(size=8),
                    line=dict(width=4 if segment in {"Upper Arm", "Lower Arm"} else 3),
                )
            )
        schematic.update_layout(showlegend=True)
        schematic.update_yaxes(scaleanchor="x", scaleratio=1, title="Vertical Axis (mm)")
        schematic.update_xaxes(title="Lateral Axis (mm)")
        themed_layout(schematic, "Double-Wishbone Geometry Transformation")
        st.plotly_chart(schematic, use_container_width=True)

    with col2:
        roll_sweep = np.linspace(-8, 8, 161)
        camber_curve = np.array(
            [compute_wishbone_state(float(r), heave_mm, 1600.0, float(upper_len), float(lower_len))[1] for r in roll_sweep]
        )
        camber_df = pd.DataFrame({"Roll Angle (deg)": roll_sweep, "Camber Change (deg)": camber_curve})
        camber_fig = px.line(
            camber_df,
            x="Roll Angle (deg)",
            y="Camber Change (deg)",
            labels={"Roll Angle (deg)": "Roll Angle (deg)", "Camber Change (deg)": "Camber Change (deg)"},
        )
        camber_fig.add_vline(x=roll_angle, line_dash="dash")
        camber_fig.add_hline(y=camber, line_dash="dot")
        camber_fig.update_yaxes(autorange=True)
        themed_layout(camber_fig, "Camber Change vs Roll Angle")
        st.plotly_chart(camber_fig, use_container_width=True)


def telemetry_center() -> None:
    st.subheader("MODULE 3: THE TELEMETRY CENTER")

    c1, c2 = st.columns(2)
    driver_number = c1.number_input("Driver Number", min_value=1, max_value=99, value=DEFAULT_DRIVER_NUMBER, step=1)
    session_key = c2.number_input("Session Key", min_value=1, value=DEFAULT_SESSION_KEY, step=1)

    params = {"session_key": int(session_key), "driver_number": int(driver_number), "limit": 2500}
    raw_car, car_status = fetch_openf1("car_data", params)
    raw_loc, loc_status = fetch_openf1("location", params)

    car_df = parse_car_data(raw_car)
    loc_df = parse_location_data(raw_loc)
    source = "real OpenF1 telemetry"

    if car_df.empty or loc_df.empty:
        car_df, loc_df = generate_fallback_telemetry()
        source = f"mock fallback (car_data: {car_status}; location: {loc_status})"
    else:
        car_df, loc_df, source = ensure_telemetry_frames(car_df, loc_df)

    merged = pd.merge_asof(
        car_df.sort_values("timestamp"),
        loc_df.sort_values("timestamp"),
        on="timestamp",
        tolerance=pd.Timedelta("400ms"),
        direction="nearest",
    ).dropna(subset=["x", "y"])

    if merged.empty:
        car_df, loc_df = generate_fallback_telemetry()
        merged = pd.merge_asof(
            car_df.sort_values("timestamp"),
            loc_df.sort_values("timestamp"),
            on="timestamp",
            tolerance=pd.Timedelta("400ms"),
            direction="nearest",
        ).dropna(subset=["x", "y"])
        source = "mock fallback (merge alignment recovery)"

    merged = normalize_time_column(merged)
    merged["dt_s"] = merged["timestamp"].diff().dt.total_seconds().fillna(0).clip(lower=0, upper=2)
    merged["distance_m"] = (merged["speed"] / 3.6 * merged["dt_s"]).cumsum()

    render_metric_cards(
        [
            ("Telemetry Points", f"{len(merged):,}"),
            ("Top Speed", f"{merged['speed'].max():.1f} km/h"),
            ("Avg Throttle", f"{merged['throttle'].mean():.1f}%"),
            ("Peak Brake", f"{merged['brake'].max():.1f}%"),
        ]
    )
    st.caption(f"Data source: {source}")

    signal_fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    signal_fig.add_trace(go.Scatter(x=merged["distance_m"], y=merged["speed"], mode="lines", name="Speed (km/h)"), row=1, col=1)
    signal_fig.add_trace(go.Scatter(x=merged["distance_m"], y=merged["throttle"], mode="lines", name="Throttle (%)"), row=2, col=1)
    signal_fig.add_trace(go.Scatter(x=merged["distance_m"], y=merged["brake"], mode="lines", name="Brake (%)"), row=3, col=1)
    signal_fig.update_yaxes(title_text="Speed", row=1, col=1)
    signal_fig.update_yaxes(title_text="Throttle", row=2, col=1)
    signal_fig.update_yaxes(title_text="Brake", row=3, col=1)
    signal_fig.update_xaxes(title_text="Distance Along Lap (m)", row=3, col=1)
    themed_layout(signal_fig, "Synchronized Telemetry Channels")
    st.plotly_chart(signal_fig, use_container_width=True)

    track_fig = px.scatter(
        merged,
        x="x",
        y="y",
        color="speed",
        color_continuous_scale="Turbo",
        hover_data={
            "timestamp": True,
            "speed": ":.1f",
            "throttle": ":.1f",
            "brake": ":.1f",
            "distance_m": ":.1f",
            "x": ":.1f",
            "y": ":.1f",
        },
    )
    track_fig.update_traces(marker=dict(size=9, opacity=0.86))
    track_fig.update_yaxes(scaleanchor="x", scaleratio=1)
    themed_layout(track_fig, "Interactive Track Map (Velocity Heat)")
    st.plotly_chart(track_fig, use_container_width=True)


def main() -> None:
    apply_theme()
    st.title("🏁 The Virtual Garage: F1 Engineering Suite")

    st.sidebar.title("Garage Modules")
    module = st.sidebar.radio(
        "Select Module",
        [
            "THE AI PIT WALL",
            "THE SUSPENSION LAB",
            "THE TELEMETRY CENTER",
        ],
    )

    if module == "THE AI PIT WALL":
        strategy_engine()
    elif module == "THE SUSPENSION LAB":
        suspension_lab()
    else:
        telemetry_center()


if __name__ == "__main__":
    main()
