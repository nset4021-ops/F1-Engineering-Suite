from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

OPENF1_BASE_URL = "https://api.openf1.org/v1"
DEFAULT_SESSION_KEY = 9839
DEFAULT_DRIVER_NUMBER = 44
REQUEST_TIMEOUT_SECONDS = 10

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="The Virtual Garage", version="1.0.0")


def _fetch_openf1(endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{OPENF1_BASE_URL}/{endpoint}", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"OpenF1 {endpoint} request failed: {exc}") from exc

    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"OpenF1 {endpoint} returned an empty payload")
    return payload


def _synthetic_pitwall_data(total_laps: int = 32) -> dict[str, Any]:
    laps = np.arange(1, total_laps + 1)
    grip = np.clip(99.0 - 1.7 * laps - 0.045 * (laps**2) + 1.4 * np.sin(laps / 2.4), 15, 100)
    lap_time = 88.6 + (100 - grip) * 0.055 + 0.12 * np.sin(laps / 2.1)
    records = [
        {
            "lap": int(lap),
            "grip": round(float(current_grip), 2),
            "lap_time": round(float(current_lap_time), 3),
        }
        for lap, current_grip, current_lap_time in zip(laps, grip, lap_time)
    ]
    latest_grip = records[-1]["grip"]
    return {
        "source": "synthetic",
        "alert": latest_grip < 45,
        "alert_text": "BOX BOX" if latest_grip < 45 else "Grip stable",
        "laps": records,
    }


def _synthetic_telemetry_data(points: int = 900) -> dict[str, Any]:
    t = np.linspace(0, 10 * np.pi, points)
    speed = np.clip(238 + 42 * np.sin(t) + 17 * np.sin(3.2 * t + 0.6), 62, 345)
    throttle = np.clip(62 + 36 * np.sin(t + 0.42) + 9 * np.sin(3.2 * t + 1.1), 0, 100)
    decel = np.clip(-np.gradient(speed), 0, None)
    brake = np.clip((100 - throttle) * 0.85 + decel * 1.8, 0, 100)

    x = 1900 * np.cos(t) + 330 * np.cos(3 * t + 0.22) + 90 * np.cos(7 * t)
    y = 1280 * np.sin(t) + 250 * np.sin(2 * t) + 110 * np.sin(6 * t + 0.4)

    start = datetime.now(UTC) - timedelta(seconds=points // 7)
    date_index = pd.date_range(start=start, periods=points, freq="150ms", tz="UTC").tz_localize(None)

    merged = pd.DataFrame(
        {
            "date": date_index,
            "speed": speed,
            "throttle": throttle,
            "brake": brake,
            "x": x,
            "y": y,
        }
    ).head(200)

    return {
        "source": "synthetic",
        "telemetry": [
            {
                "date": row["date"].isoformat(),
                "speed": round(float(row["speed"]), 2),
                "throttle": round(float(row["throttle"]), 2),
                "brake": round(float(row["brake"]), 2),
                "x": round(float(row["x"]), 2),
                "y": round(float(row["y"]), 2),
            }
            for _, row in merged.iterrows()
        ],
    }


def _pitwall_from_openf1(session_key: int, driver_number: int) -> dict[str, Any]:
    raw_laps = _fetch_openf1("laps", {"session_key": session_key, "driver_number": driver_number})
    frame = pd.DataFrame(raw_laps)
    if frame.empty:
        raise RuntimeError("No lap data returned")

    lap_column = "lap_number" if "lap_number" in frame.columns else "lap"
    if lap_column not in frame.columns:
        raise RuntimeError("Lap number field missing")

    if "lap_duration" in frame.columns:
        lap_time_column = "lap_duration"
    elif "lap_time" in frame.columns:
        lap_time_column = "lap_time"
    else:
        raise RuntimeError("Lap time field missing")

    frame = frame[[lap_column, lap_time_column]].rename(columns={lap_column: "lap", lap_time_column: "lap_time"})
    frame = frame.dropna(subset=["lap", "lap_time"]).sort_values("lap")
    frame["lap"] = frame["lap"].astype(int)
    frame["lap_time"] = frame["lap_time"].astype(float)

    baseline = frame["lap_time"].iloc[0]
    frame["grip"] = np.clip(100 - (frame["lap"] - 1) * 2.6 - np.maximum(frame["lap_time"] - baseline, 0) * 1.9, 0, 100)

    records = [
        {
            "lap": int(row["lap"]),
            "grip": round(float(row["grip"]), 2),
            "lap_time": round(float(row["lap_time"]), 3),
        }
        for _, row in frame.iterrows()
    ]
    latest_grip = records[-1]["grip"]
    return {
        "source": "openf1",
        "alert": latest_grip < 45,
        "alert_text": "BOX BOX" if latest_grip < 45 else "Grip stable",
        "laps": records,
    }


def _telemetry_from_openf1(session_key: int, driver_number: int) -> dict[str, Any]:
    base_params = {"session_key": session_key, "driver_number": driver_number}
    car_raw = _fetch_openf1("car_data", base_params)
    loc_raw = _fetch_openf1("location", base_params)

    df_car = pd.DataFrame(car_raw)
    df_loc = pd.DataFrame(loc_raw)

    if "date" not in df_car.columns or "date" not in df_loc.columns:
        raise RuntimeError("Required date field missing in telemetry response")

    df_car["date"] = pd.to_datetime(df_car["date"], utc=True).dt.tz_localize(None)
    df_loc["date"] = pd.to_datetime(df_loc["date"], utc=True).dt.tz_localize(None)

    required_car_columns = ["date", "speed", "throttle", "brake"]
    required_loc_columns = ["date", "x", "y"]
    if any(column not in df_car.columns for column in required_car_columns) or any(
        column not in df_loc.columns for column in required_loc_columns
    ):
        raise RuntimeError("Telemetry payload schema changed")

    df_car = df_car[required_car_columns].dropna().sort_values("date")
    df_loc = df_loc[required_loc_columns].dropna().sort_values("date")

    if df_car.empty or df_loc.empty:
        raise RuntimeError("Telemetry payload contains no usable rows")

    merged = pd.merge_asof(df_car, df_loc, on="date", direction="nearest")
    merged = merged.dropna(subset=["speed", "throttle", "brake", "x", "y"]).head(200)

    if merged.empty:
        raise RuntimeError("Merged telemetry dataset is empty")

    return {
        "source": "openf1",
        "telemetry": [
            {
                "date": row["date"].isoformat(),
                "speed": round(float(row["speed"]), 2),
                "throttle": round(float(row["throttle"]), 2),
                "brake": round(float(row["brake"]), 2),
                "x": round(float(row["x"]), 2),
                "y": round(float(row["y"]), 2),
            }
            for _, row in merged.iterrows()
        ],
    }


def _calculate_suspension_kinematics(roll_angle_deg: float, wishbone_length_mm: float) -> dict[str, Any]:
    roll_rad = math.radians(roll_angle_deg)
    wheel_shift = wishbone_length_mm * math.sin(roll_rad) * 0.12
    camber_change = -math.degrees(math.atan2(wheel_shift, max(wishbone_length_mm, 1.0)))

    chassis_left = np.array([120.0, 180.0])
    chassis_right = np.array([420.0, 180.0])
    upright_top = np.array([300.0 + wheel_shift, 120.0])
    upright_bottom = np.array([300.0 + wheel_shift, 250.0])

    upper_vector = upright_top - chassis_left
    lower_vector = upright_bottom - np.array([200.0, 250.0])

    return {
        "roll_angle_deg": round(roll_angle_deg, 2),
        "wishbone_length_mm": round(wishbone_length_mm, 2),
        "camber_change_deg": round(camber_change, 3),
        "vectors": {
            "upper": {"x": round(float(upper_vector[0]), 3), "y": round(float(upper_vector[1]), 3)},
            "lower": {"x": round(float(lower_vector[0]), 3), "y": round(float(lower_vector[1]), 3)},
        },
        "points": {
            "chassis_left": {"x": chassis_left[0], "y": chassis_left[1]},
            "chassis_right": {"x": chassis_right[0], "y": chassis_right[1]},
            "upright_top": {"x": round(float(upright_top[0]), 3), "y": upright_top[1]},
            "upright_bottom": {"x": round(float(upright_bottom[0]), 3), "y": upright_bottom[1]},
            "lower_pivot": {"x": 200.0, "y": 250.0},
        },
    }


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/style.css")
def serve_style() -> FileResponse:
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")


@app.get("/app.js")
def serve_script() -> FileResponse:
    return FileResponse(BASE_DIR / "app.js", media_type="application/javascript")


@app.get("/api/pitwall")
def get_pitwall(
    session_key: int = Query(DEFAULT_SESSION_KEY, ge=1),
    driver_number: int = Query(DEFAULT_DRIVER_NUMBER, ge=1, le=99),
) -> dict[str, Any]:
    try:
        return _pitwall_from_openf1(session_key=session_key, driver_number=driver_number)
    except Exception:
        return _synthetic_pitwall_data()


@app.get("/api/suspension")
def get_suspension(
    roll_angle: float = Query(0.0, ge=-8.0, le=8.0),
    wishbone_length: float = Query(380.0, ge=260.0, le=520.0),
) -> dict[str, Any]:
    return _calculate_suspension_kinematics(roll_angle_deg=roll_angle, wishbone_length_mm=wishbone_length)


@app.get("/api/telemetry")
def get_telemetry(
    session_key: int = Query(DEFAULT_SESSION_KEY, ge=1),
    driver_number: int = Query(DEFAULT_DRIVER_NUMBER, ge=1, le=99),
) -> dict[str, Any]:
    try:
        return _telemetry_from_openf1(session_key=session_key, driver_number=driver_number)
    except Exception:
        return _synthetic_telemetry_data()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
