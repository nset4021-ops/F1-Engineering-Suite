from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(title="The Virtual Garage: An F1 Engineering Suite", version="2.0.0")


def _request_openf1(endpoint: str, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    url = f"{OPENF1_BASE}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Unexpected response type from {endpoint}")
        return payload, "real"
    except (requests.RequestException, ValueError, TimeoutError) as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _compound_name(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    name = str(value).strip().upper()
    return name or "UNKNOWN"


def _normalize_date_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _fallback_pitwall_frame() -> pd.DataFrame:
    lap_numbers = np.arange(1, 13)
    lap_times = np.array([91.2, 91.5, 91.9, 92.3, 92.8, 93.5, 94.4, 95.2, 96.1, 97.1, 98.0, 98.8])
    compounds = ["MEDIUM"] * 4 + ["SOFT"] * 8
    dates = pd.date_range(end=pd.Timestamp.utcnow().tz_localize(None), periods=len(lap_numbers), freq="90s")
    frame = pd.DataFrame(
        {
            "lap_number": lap_numbers,
            "lap_time": lap_times,
            "compound": compounds,
            "date": dates,
        }
    )
    return _normalize_date_frame(frame)


def _fallback_telemetry_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    points = 200
    dates = pd.date_range(end=pd.Timestamp.utcnow().tz_localize(None), periods=points, freq="2s")
    index = np.arange(points)
    speed = 235 + 55 * np.sin(index / 15)
    throttle = np.clip(68 + 28 * np.sin(index / 11), 0, 100)
    brake = np.clip(np.where(throttle < 60, 100 - throttle, 0), 0, 100)

    theta = np.linspace(0, 2 * np.pi, points)
    x = 1400 * np.cos(theta) + 120 * np.cos(3 * theta)
    y = 900 * np.sin(theta) + 90 * np.sin(4 * theta)

    car_df = pd.DataFrame(
        {
            "date": dates,
            "speed": speed,
            "throttle": throttle,
            "brake": brake,
        }
    )
    loc_df = pd.DataFrame(
        {
            "date": dates,
            "x": x,
            "y": y,
        }
    )
    return car_df, loc_df


def _parse_pitwall_rows(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    parsed_rows: List[Dict[str, Any]] = []
    for row in rows:
        lap_number = row.get("lap_number") or row.get("lap")
        lap_time = row.get("lap_duration") or row.get("lap_time") or row.get("duration")
        date_value = row.get("date") or row.get("date_start") or row.get("timestamp")
        compound = row.get("compound") or row.get("tyre_compound") or row.get("stint_compound")
        if lap_number is None or lap_time is None:
            continue
        parsed_rows.append(
            {
                "lap_number": int(lap_number),
                "lap_time": float(lap_time),
                "compound": _compound_name(compound),
                "date": date_value,
            }
        )

    if not parsed_rows:
        return pd.DataFrame(columns=["lap_number", "lap_time", "compound", "date"])

    frame = pd.DataFrame(parsed_rows)
    if frame["date"].isna().all():
        frame["date"] = pd.date_range(end=pd.Timestamp.utcnow().tz_localize(None), periods=len(frame), freq="90s")
    return _normalize_date_frame(frame)


def _parse_telemetry_rows(rows: List[Dict[str, Any]], kind: str) -> pd.DataFrame:
    parsed_rows: List[Dict[str, Any]] = []
    for row in rows:
        date_value = row.get("date") or row.get("timestamp")
        if kind == "car":
            speed = row.get("speed")
            throttle = row.get("throttle")
            brake = row.get("brake")
            if date_value is None or speed is None or throttle is None or brake is None:
                continue
            parsed_rows.append(
                {
                    "date": date_value,
                    "speed": float(speed),
                    "throttle": float(throttle),
                    "brake": float(brake),
                }
            )
        else:
            x_value = row.get("x")
            y_value = row.get("y")
            if date_value is None or x_value is None or y_value is None:
                continue
            parsed_rows.append(
                {
                    "date": date_value,
                    "x": float(x_value),
                    "y": float(y_value),
                }
            )

    if not parsed_rows:
        columns = ["date", "speed", "throttle", "brake"] if kind == "car" else ["date", "x", "y"]
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(parsed_rows)
    return _normalize_date_frame(frame)


def _pitwall_payload(session_key: int, driver_number: int) -> Dict[str, Any]:
    params = {"session_key": session_key, "driver_number": driver_number}
    raw_laps, source = _request_openf1("laps", params)

    laps_df = _parse_pitwall_rows(raw_laps) if raw_laps else pd.DataFrame()
    if laps_df.empty:
        laps_df = _fallback_pitwall_frame()
        source = "mock"

    laps_df = laps_df.sort_values("date").dropna(subset=["lap_time", "lap_number", "date"]).reset_index(drop=True)
    latest_compound = _compound_name(laps_df["compound"].iloc[-1] if not laps_df.empty else "UNKNOWN")
    decay_rate = COMPOUND_DEGRADATION.get(latest_compound, COMPOUND_DEGRADATION["UNKNOWN"])

    lap_index = np.arange(len(laps_df), dtype=float)
    baseline = float(laps_df["lap_time"].iloc[0])
    lap_drift = np.clip(laps_df["lap_time"].to_numpy(dtype=float) - baseline, 0, None)
    grip = np.clip(100 - decay_rate * lap_index - 2.1 * lap_drift, 0, 100)
    laps_df["grip"] = grip

    latest = laps_df.iloc[-1]
    return {
        "source": source,
        "session_key": session_key,
        "driver_number": driver_number,
        "compound": latest_compound,
        "latest_grip": round(float(latest["grip"]), 2),
        "warning": bool(float(latest["grip"]) < 45),
        "data": [
            {
                "lap_number": int(row.lap_number),
                "lap_time": round(float(row.lap_time), 3),
                "compound": row.compound,
                "date": row.date.isoformat(),
                "grip": round(float(row.grip), 2),
            }
            for row in laps_df.itertuples(index=False)
        ],
    }


def _suspension_payload(session_key: int, driver_number: int) -> Dict[str, Any]:
    params = {"session_key": session_key, "driver_number": driver_number}
    raw_car, source = _request_openf1("car_data", params)
    car_df = _parse_telemetry_rows(raw_car, "car") if raw_car else pd.DataFrame()

    if car_df.empty:
        car_df, _ = _fallback_telemetry_frames()
        source = "mock"

    car_df = car_df.sort_values("date").dropna(subset=["date", "speed", "throttle", "brake"]).head(200).reset_index(drop=True)

    return {
        "source": source,
        "session_key": session_key,
        "driver_number": driver_number,
        "defaults": {
            "roll_angle_deg": 0.0,
            "wishbone_length_mm": 420.0,
            "chassis_half_width_mm": 220.0,
            "upright_height_mm": 165.0,
        },
        "summary": {
            "average_speed": round(float(car_df["speed"].mean()), 2),
            "peak_brake": round(float(car_df["brake"].max()), 2),
            "mean_throttle": round(float(car_df["throttle"].mean()), 2),
            "sample_count": int(len(car_df)),
        },
        "samples": [
            {
                "date": row.date.isoformat(),
                "speed": round(float(row.speed), 2),
                "throttle": round(float(row.throttle), 2),
                "brake": round(float(row.brake), 2),
            }
            for row in car_df.itertuples(index=False)
        ],
    }


def _telemetry_payload(session_key: int, driver_number: int) -> Dict[str, Any]:
    params = {"session_key": session_key, "driver_number": driver_number}
    raw_car, car_source = _request_openf1("car_data", params)
    raw_loc, loc_source = _request_openf1("location", params)

    car_df = _parse_telemetry_rows(raw_car, "car") if raw_car else pd.DataFrame()
    loc_df = _parse_telemetry_rows(raw_loc, "location") if raw_loc else pd.DataFrame()

    if car_df.empty or loc_df.empty:
        car_df, loc_df = _fallback_telemetry_frames()
        car_source = loc_source = "mock"

    car_df = car_df.sort_values("date").dropna(subset=["date", "speed", "throttle", "brake"]).head(200).reset_index(drop=True)
    loc_df = loc_df.sort_values("date").dropna(subset=["date", "x", "y"]).head(200).reset_index(drop=True)

    merged = pd.merge_asof(car_df, loc_df, on="date", direction="nearest")
    merged = merged.dropna(subset=["x", "y", "speed", "throttle", "brake"]).reset_index(drop=True)

    if merged.empty:
        car_df, loc_df = _fallback_telemetry_frames()
        merged = pd.merge_asof(
            car_df.sort_values("date").head(200).reset_index(drop=True),
            loc_df.sort_values("date").head(200).reset_index(drop=True),
            on="date",
            direction="nearest",
        ).dropna(subset=["x", "y", "speed", "throttle", "brake"]).reset_index(drop=True)
        car_source = loc_source = "mock"

    return {
        "source": {"car_data": car_source, "location": loc_source},
        "session_key": session_key,
        "driver_number": driver_number,
        "data": [
            {
                "date": row.date.isoformat(),
                "speed": round(float(row.speed), 2),
                "throttle": round(float(row.throttle), 2),
                "brake": round(float(row.brake), 2),
                "x": round(float(row.x), 3),
                "y": round(float(row.y), 3),
            }
            for row in merged.itertuples(index=False)
        ],
    }


@app.get("/api/pitwall")
def api_pitwall(
    session_key: int = Query(DEFAULT_SESSION_KEY, ge=1),
    driver_number: int = Query(DEFAULT_DRIVER_NUMBER, ge=1, le=99),
) -> Dict[str, Any]:
    return _pitwall_payload(session_key, driver_number)


@app.get("/api/suspension")
def api_suspension(
    session_key: int = Query(DEFAULT_SESSION_KEY, ge=1),
    driver_number: int = Query(DEFAULT_DRIVER_NUMBER, ge=1, le=99),
) -> Dict[str, Any]:
    return _suspension_payload(session_key, driver_number)


@app.get("/api/telemetry")
def api_telemetry(
    session_key: int = Query(DEFAULT_SESSION_KEY, ge=1),
    driver_number: int = Query(DEFAULT_DRIVER_NUMBER, ge=1, le=99),
) -> Dict[str, Any]:
    return _telemetry_payload(session_key, driver_number)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent, html=True), name="frontend")


def main() -> None:
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()