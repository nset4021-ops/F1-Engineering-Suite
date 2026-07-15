"""Data fetching and engineering computations for the F1 Engineering Suite.

Ported from the original Streamlit app. This module is UI-agnostic: it returns
plain Python data structures that the FastAPI layer serializes to JSON.
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

OPENF1_BASE = "https://api.openf1.org/v1"

COMPOUND_DEGRADATION = {
    "SOFT": 4.8,
    "MEDIUM": 3.3,
    "HARD": 2.3,
    "INTERMEDIATE": 3.8,
    "WET": 4.2,
    "UNKNOWN": 3.5,
}


def fetch_openf1(endpoint: str, params: Dict[str, int]) -> Tuple[List[Dict], str]:
    """Fetch a list payload from the OpenF1 API.

    Returns (payload, "real") on success or ([], error_message) on failure.
    """
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


def parse_laps(raw_laps: List[Dict]) -> List[Dict]:
    rows = []
    for row in raw_laps:
        lap_time = row.get("lap_duration") or row.get("lap_time")
        lap_no = row.get("lap_number")
        compound = (
            row.get("compound")
            or row.get("tyre_compound")
            or row.get("stint_compound")
            or "UNKNOWN"
        )
        if lap_time is None or lap_no is None:
            continue
        rows.append(
            {
                "lap_number": int(lap_no),
                "lap_time": float(lap_time),
                "compound": str(compound).upper(),
            }
        )
    return sorted(rows, key=lambda r: r["lap_number"])


def compute_strategy(session_key: int, driver_number: int) -> Dict:
    """Fetch laps and compute the theoretical-grip strategy model."""
    raw_laps, status = fetch_openf1(
        "laps", {"session_key": session_key, "driver_number": driver_number}
    )
    if raw_laps:
        laps = parse_laps(raw_laps)
        data_source = "real OpenF1 telemetry"
    else:
        laps = parse_laps(mock_lap_data())
        data_source = "mock fallback"

    if not laps:
        return {"laps": [], "data_source": data_source, "status": status}

    current_compound = laps[-1]["compound"]
    deg_rate = COMPOUND_DEGRADATION.get(current_compound, COMPOUND_DEGRADATION["UNKNOWN"])

    lap_times = np.array([lap["lap_time"] for lap in laps], dtype=float)
    lap_index = np.arange(len(laps))
    baseline = lap_times[0]
    lap_drift = np.maximum(lap_times - baseline, 0)
    theoretical_grip = np.clip(100 - deg_rate * lap_index - 2.2 * lap_drift, 0, 100)

    for lap, grip in zip(laps, theoretical_grip):
        lap["theoretical_grip"] = float(grip)

    latest = laps[-1]
    return {
        "laps": laps,
        "data_source": data_source,
        "status": status if not raw_laps else "real",
        "current_compound": current_compound,
        "degradation_rate": deg_rate,
        "latest_lap_time": latest["lap_time"],
        "latest_grip": latest["theoretical_grip"],
        "pit_recommended": latest["theoretical_grip"] < 45,
    }


def compute_wishbone_geometry(
    roll_angle_deg: float, wishbone_length_mm: float
) -> Tuple[List[Dict], float]:
    roll_rad = math.radians(roll_angle_deg)
    wheel_center_shift = wishbone_length_mm * math.sin(roll_rad)
    camber_change_deg = -math.degrees(math.atan2(wheel_center_shift, wishbone_length_mm))

    chassis_y = 360
    chassis_half_width = 200
    wheel_x = 400 + wheel_center_shift * 0.45

    xs = [-chassis_half_width, -80, wheel_x, wheel_x, 80, chassis_half_width]
    ys = [chassis_y, chassis_y - 85, chassis_y - 55, chassis_y - 195, chassis_y - 85, chassis_y]
    segments = ["chassis", "upper arm", "upright", "upright", "lower arm", "chassis"]
    geometry = [
        {"x": float(x), "y": float(y), "segment": seg}
        for x, y, seg in zip(xs, ys, segments)
    ]
    return geometry, camber_change_deg


def compute_suspension(roll_angle: float, wishbone_length: float) -> Dict:
    geometry, camber = compute_wishbone_geometry(roll_angle, wishbone_length)

    roll_range = np.linspace(-5, 5, 80)
    camber_series = [
        -math.degrees(
            math.atan2(wishbone_length * math.sin(math.radians(r)), wishbone_length)
        )
        for r in roll_range
    ]
    camber_curve = [
        {"roll_angle": float(r), "camber_change": float(c)}
        for r, c in zip(roll_range, camber_series)
    ]
    return {
        "geometry": geometry,
        "camber_change": camber,
        "camber_curve": camber_curve,
    }


def _to_epoch_ms(ts: str) -> Optional[float]:
    """Parse an ISO-ish timestamp to epoch milliseconds; None if unparseable."""
    import datetime as _dt

    if ts is None:
        return None
    try:
        cleaned = str(ts).replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(cleaned).timestamp() * 1000.0
    except (ValueError, TypeError):
        return None


def mock_car_data() -> List[Dict]:
    points = 200
    t = np.arange(points)
    speed = 235 + 55 * np.sin(t / 15)
    throttle = np.clip(68 + 28 * np.sin(t / 11), 0, 100)
    brake = (throttle < 60).astype(int) * np.clip(100 - throttle, 0, 100)
    base = 1767225600000.0  # 2026-01-01
    return [
        {
            "ts": base + i * 2000.0,
            "speed": float(speed[i]),
            "throttle": float(throttle[i]),
            "brake": float(brake[i]),
        }
        for i in range(points)
    ]


def mock_location_data() -> List[Dict]:
    points = 200
    theta = np.linspace(0, 2 * np.pi, points)
    x = 1400 * np.cos(theta) + 120 * np.cos(3 * theta)
    y = 900 * np.sin(theta) + 90 * np.sin(4 * theta)
    base = 1767225600000.0
    return [
        {"ts": base + i * 2000.0, "x": float(x[i]), "y": float(y[i])}
        for i in range(points)
    ]


def parse_car_data(raw: List[Dict]) -> List[Dict]:
    rows = []
    for point in raw:
        ts = _to_epoch_ms(point.get("date") or point.get("timestamp"))
        speed = point.get("speed")
        throttle = point.get("throttle")
        brake = point.get("brake")
        if ts is None or speed is None or throttle is None or brake is None:
            continue
        rows.append(
            {
                "ts": ts,
                "speed": float(speed),
                "throttle": float(throttle),
                "brake": float(brake),
            }
        )
    return sorted(rows, key=lambda r: r["ts"])


def parse_location_data(raw: List[Dict]) -> List[Dict]:
    rows = []
    for point in raw:
        ts = _to_epoch_ms(point.get("date") or point.get("timestamp"))
        x, y = point.get("x"), point.get("y")
        if ts is None or x is None or y is None:
            continue
        rows.append({"ts": ts, "x": float(x), "y": float(y)})
    return sorted(rows, key=lambda r: r["ts"])


def _merge_nearest(car: List[Dict], loc: List[Dict], tolerance_ms: float = 2000.0) -> List[Dict]:
    """Merge location onto car samples by nearest timestamp within a tolerance."""
    if not car or not loc:
        return []
    loc_ts = [p["ts"] for p in loc]
    merged = []
    j = 0
    n = len(loc)
    for c in car:
        # advance j to the closest location sample
        while j + 1 < n and abs(loc_ts[j + 1] - c["ts"]) <= abs(loc_ts[j] - c["ts"]):
            j += 1
        nearest = loc[j]
        if abs(nearest["ts"] - c["ts"]) > tolerance_ms:
            continue
        velocity_state = c["speed"] * (-1 if c["brake"] > 0 else 1)
        merged.append(
            {
                "ts": c["ts"],
                "speed": c["speed"],
                "throttle": c["throttle"],
                "brake": c["brake"],
                "x": nearest["x"],
                "y": nearest["y"],
                "velocity_state": velocity_state,
            }
        )
    return merged


def compute_telemetry(session_key: int, driver_number: int) -> Dict:
    params = {"session_key": session_key, "driver_number": driver_number, "limit": 200}
    raw_car, car_status = fetch_openf1("car_data", params)
    raw_loc, loc_status = fetch_openf1("location", params)

    if raw_car and raw_loc:
        car = parse_car_data(raw_car)
        loc = parse_location_data(raw_loc)
        source = "real OpenF1 telemetry"
    else:
        car = mock_car_data()
        loc = mock_location_data()
        source = "mock fallback"

    merged = _merge_nearest(car, loc)
    return {
        "data_source": source,
        "car_status": car_status,
        "location_status": loc_status,
        "samples": merged,
    }
