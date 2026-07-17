from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

app = FastAPI()

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

# Expanded Tracks
DEFAULT_TRACKS = {
    "monza": {"name": "Monza Circuit", "base_speed": 372.0, "corner_factor": 0.84, "distance": 5793.0, "atmosphere": "Low-downforce temple of speed"},
    "silverstone": {"name": "Silverstone GP", "base_speed": 343.0, "corner_factor": 0.78, "distance": 5891.0, "atmosphere": "High-speed classic sweepers"},
    "spa": {"name": "Spa-Francorchamps", "base_speed": 358.0, "corner_factor": 0.81, "distance": 7004.0, "atmosphere": "Rollercoaster mountain sector"},
    "baku": {"name": "Baku City Circuit", "base_speed": 371.0, "corner_factor": 0.83, "distance": 6003.0, "atmosphere": "Castle-side street straightways"},
    "suzuka": {"name": "Suzuka International", "base_speed": 335.0, "corner_factor": 0.74, "distance": 5807.0, "atmosphere": "Technical figure-eight masterclass"},
    "default": {"name": "Standard Test Track", "base_speed": 340.0, "corner_factor": 0.80, "distance": 5500.0, "atmosphere": "Telemetry proving grounds"}
}

# Extensive Galactic Database Specs
TEAM_SPECS = {
    "Astral Works": {
        "engine": "Apex Astral V6 Hybrid (1,040 HP)",
        "aero_drag": "Ultra-Low",
        "downforce_index": "8.8/10",
        "specialty": "Straight-line hyperdrive and low-drag efficiency",
        "lore": "The premier engineering wing of the Outer Rim, known for raw, unadulterated speed."
    },
    "Sith Racing": {
        "engine": "Dark Matter Combustion Core (1,075 HP)",
        "aero_drag": "Medium-High",
        "downforce_index": "9.6/10",
        "specialty": "High-speed cornering grip and aggressive kinetic energy recovery",
        "lore": "Utilizes experimental plasma stabilizers and extreme downforce packages."
    },
    "Jedi Academy": {
        "engine": "Kyber-Infused Fusion Power Unit (1,020 HP)",
        "aero_drag": "Balanced",
        "downforce_index": "9.1/10",
        "specialty": "Tire thermal management and chassis stability control",
        "lore": "Engineered for balance and flow, offering the smoothest traction profile on wet circuits."
    },
    "Scoundrel F1": {
        "engine": "Modified Corellian Turbocharged Hybrid (995 HP)",
        "aero_drag": "Low",
        "downforce_index": "8.2/10",
        "specialty": "Rapid energy deployment and lightweight chassis overrides",
        "lore": "A rogue outfit using patched-together telemetry arrays and high-risk boost cycles."
    }
}

DRIVER_SPECS = {
    "Apex One": {"real_name": "Classified Prototype Pilot", "experience": "Infinite (Machine Learned)", "reflexes": "99/100", "patience": "72/100", "profile": "Synthesized AI pilot designed for ideal racing lines."},
    "Red Leader": {"real_name": "Garven Dreis", "experience": "12 Seasons", "reflexes": "91/100", "patience": "94/100", "profile": "Veteran racer with impeccable spatial awareness and defensive strategy."},
    "Vader": {"real_name": "Anakin Skywalker", "experience": "9 Seasons", "reflexes": "98/100", "patience": "35/100", "profile": "Terrifying speed profile. Highly aggressive but prone to lockups under pressure."},
    "Solo": {"real_name": "Han Solo", "experience": "7 Seasons", "reflexes": "95/100", "patience": "50/100", "profile": "Known for overtaking in impossible gaps, though chassis integrity takes a hit."},
    "Lewis Hamilton": {"real_name": "Lewis Hamilton", "experience": "20 Seasons", "reflexes": "96/100", "patience": "97/100", "profile": "7-time World Champion. Peerless wet-weather masterclass and race management."},
    "Max Verstappen": {"real_name": "Max Verstappen", "experience": "12 Seasons", "reflexes": "98/100", "patience": "91/100", "profile": "Multi-time World Champion. Unbelievably precise car control and ruthless race pace."},
    "Charles Leclerc": {"real_name": "Charles Leclerc", "experience": "9 Seasons", "reflexes": "97/100", "patience": "85/100", "profile": "Qualifying virtuoso with a reputation for lightning-fast apex speeds."}
}


def _simulate_telemetry_data(track_id: str, car_type: str, weather_type: str) -> pd.DataFrame:
    track = DEFAULT_TRACKS.get(track_id, DEFAULT_TRACKS["default"])
    base_speed = track["base_speed"]
    corner_factor = track["corner_factor"]

    if car_type == "Low Drag":
        base_speed += 15.0
        corner_factor -= 0.05
    elif car_type == "High Downforce":
        base_speed -= 10.0
        corner_factor += 0.06

    if weather_type == "damp":
        base_speed *= 0.90
        corner_factor *= 0.92
    elif weather_type == "wet":
        base_speed *= 0.80
        corner_factor *= 0.84

    num_samples = 150
    t = np.linspace(0, 2 * np.pi, num_samples)

    if track_id == "monza":
        x = 2200 * np.cos(t) + 400 * np.sin(2*t)
        y = 800 * np.sin(t)
    elif track_id == "silverstone":
        x = 1800 * np.cos(t) + 600 * np.sin(3*t)
        y = 1200 * np.sin(t)
    elif track_id == "spa":
        x = 2500 * np.cos(t) + 300 * np.sin(4*t)
        y = 1500 * np.sin(t) + 500 * np.cos(2*t)
    elif track_id == "baku":
        x = 2000 * np.cos(t) + 800 * np.sin(t)
        y = 900 * np.sin(2*t)
    elif track_id == "suzuka":
        x = 1600 * np.cos(t) + 1200 * np.sin(2*t)
        y = 1200 * np.sin(t)
    else:
        x = 1500 * np.cos(t)
        y = 1500 * np.sin(t)

    speeds = []
    throttles = []
    brakes = []
    
    for i in range(num_samples):
        next_i = (i + 1) % num_samples
        dx = x[next_i] - x[i]
        dy = y[next_i] - y[i]
        if i == 0:
            curvature = 0.0
        else:
            prev_i = (i - 1) % num_samples
            dx_p = x[i] - x[prev_i]
            dy_p = y[i] - y[prev_i]
            v1 = np.array([dx_p, dy_p])
            v2 = np.array([dx, dy])
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 > 0 and norm2 > 0:
                cos_theta = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
                curvature = float(np.arccos(cos_theta))
            else:
                curvature = 0.0

        is_curve = curvature > 0.05
        if is_curve:
            speed_val = base_speed * corner_factor * (1.0 - min(curvature * 2.0, 0.45))
            throttle_val = max(10.0, 45.0 - (curvature * 150.0))
            brake_val = min(100.0, curvature * 220.0)
        else:
            speed_val = base_speed * (0.88 + 0.12 * np.sin(i / 10.0))
            throttle_val = min(100.0, 85.0 + 15.0 * np.sin(i / 10.0))
            brake_val = 0.0

        speeds.append(speed_val)
        throttles.append(throttle_val)
        brakes.append(brake_val)

    velocity_states = np.array(speeds) * np.where(np.array(brakes) > 0, -1, 1)

    df = pd.DataFrame({
        "x": x,
        "y": y,
        "speed": speeds,
        "throttle": throttles,
        "brake": brakes,
        "velocity_state": velocity_states
    })
    return df


def _pitwall_payload(session_key: int, driver_number: int) -> Dict[str, Any]:
    try:
        lap_resp = requests.get(f"{OPENF1_BASE}/laps?session_key={session_key}&driver_number={driver_number}", timeout=3.5)
        st_resp = requests.get(f"{OPENF1_BASE}/stints?session_key={session_key}&driver_number={driver_number}", timeout=3.5)
        
        if lap_resp.status_code == 200 and st_resp.status_code == 200:
            laps_data = lap_resp.json()
            stints_data = st_resp.json()
            if laps_data and stints_data:
                latest_lap = laps_data[-1]
                latest_stint = stints_data[-1]
                compound = latest_stint.get("compound", "MEDIUM").upper()
                deg_rate = COMPOUND_DEGRADATION.get(compound, 3.3)
                current_lap = int(latest_lap.get("lap_number", 1))
                stint_lap = max(1, current_lap - int(latest_stint.get("lap_start", 1)))
                calculated_grip = max(12.0, round(100.0 - (stint_lap * deg_rate), 1))

                return {
                    "source": "live",
                    "compound": compound,
                    "lap_number": current_lap,
                    "grip_level": calculated_grip,
                    "session_key": session_key,
                }
    except Exception:
        pass

    return {
        "source": "sandbox",
        "compound": "MEDIUM",
        "lap_number": 24,
        "grip_level": 74.5,
        "session_key": session_key,
    }


def _suspension_payload(session_key: int, driver_number: int) -> Dict[str, Any]:
    return {
        "source": "sandbox",
        "camber_proxy": -1.85,
    }


def _telemetry_payload(session_key: int, driver_number: int, track_id: str = "monza", car_type: str = "Balanced", weather_type: str = "dry") -> Dict[str, Any]:
    try:
        url_car = f"{OPENF1_BASE}/car_data?session_key={session_key}&driver_number={driver_number}"
        url_loc = f"{OPENF1_BASE}/location?session_key={session_key}&driver_number={driver_number}"
        
        r_car = requests.get(url_car, timeout=3.5)
        r_loc = requests.get(url_loc, timeout=3.5)

        if r_car.status_code == 200 and r_loc.status_code == 200:
            car_data = r_car.json()
            loc_data = r_loc.json()
            if car_data and loc_data:
                df_car = pd.DataFrame(car_data)
                df_loc = pd.DataFrame(loc_data)

                df_car["date"] = pd.to_datetime(df_car["date"], utc=True).dt.tz_localize(None)
                df_loc["date"] = pd.to_datetime(df_loc["date"], utc=True).dt.tz_localize(None)

                df_car = df_car.sort_values("date").dropna()
                df_loc = df_loc.sort_values("date").dropna()

                merged = pd.merge_asof(df_car, df_loc, on="date", direction="nearest")
                merged = merged.head(150)

                merged["x"] = merged["x"].astype(float) / 10.0
                merged["y"] = merged["y"].astype(float) / 10.0
                merged["speed"] = merged["speed"].astype(float)
                merged["throttle"] = merged["throttle"].astype(float)
                merged["brake"] = merged["brake"].astype(float)

                data_points = []
                for idx, row in enumerate(merged.itertuples(index=False)):
                    try:
                        # Extract real parts and cast cleanly to prevent dynamic type conflicts
                        x_val = float(getattr(row, "x", 0.0).real if hasattr(getattr(row, "x", 0.0), "real") else getattr(row, "x", 0.0))
                        y_val = float(getattr(row, "y", 0.0).real if hasattr(getattr(row, "y", 0.0), "real") else getattr(row, "y", 0.0))
                        speed_val = float(getattr(row, "speed", 0.0))
                        throttle_val = float(getattr(row, "throttle", 0.0))
                        brake_val = float(getattr(row, "brake", 0.0))
                        
                        velocity_state = speed_val * (-1.0 if brake_val > 10.0 else 1.0)
                        
                        data_points.append({
                            "loop": idx,
                            "x": round(x_val, 3),
                            "y": round(y_val, 3),
                            "speed": round(speed_val, 1),
                            "throttle": round(throttle_val, 1),
                            "brake": round(brake_val, 1),
                            "velocity_state": round(velocity_state, 3)
                        })
                    except (ValueError, TypeError):
                        continue

                return {
                    "source": "live",
                    "data": data_points
                }
    except Exception:
        pass

    telemetry = _simulate_telemetry_data(track_id, car_type, weather_type)
    
    # Safe data parsing using real numerical casting for sandbox frames
    sandbox_data = []
    for idx, row in enumerate(telemetry.itertuples(index=False)):
        x_raw = getattr(row, "x", 0.0)
        y_raw = getattr(row, "y", 0.0)
        speed_raw = getattr(row, "speed", 0.0)
        throttle_raw = getattr(row, "throttle", 0.0)
        brake_raw = getattr(row, "brake", 0.0)
        vel_raw = getattr(row, "velocity_state", 0.0)

        sandbox_data.append({
            "loop": idx,
            "speed": round(float(speed_raw.real if hasattr(speed_raw, "real") else speed_raw), 1),
            "throttle": round(float(throttle_raw.real if hasattr(throttle_raw, "real") else throttle_raw), 1),
            "brake": round(float(brake_raw.real if hasattr(brake_raw, "real") else brake_raw), 1),
            "x": round(float(x_raw.real if hasattr(x_raw, "real") else x_raw), 3),
            "y": round(float(y_raw.real if hasattr(y_raw, "real") else y_raw), 3),
            "velocity_state": round(float(vel_raw.real if hasattr(vel_raw, "real") else vel_raw), 3),
        })

    return {
        "source": "sandbox",
        "data": sandbox_data
    }


@app.get("/api/specs")
def api_specs() -> Dict[str, Any]:
    """Exposes high-fidelity team and driver galactic technical data profiles."""
    return {
        "teams": TEAM_SPECS,
        "drivers": DRIVER_SPECS
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
    track_id: str = "monza",
    car_type: str = "Balanced",
    weather_type: str = "dry",
) -> Dict[str, Any]:
    return _telemetry_payload(session_key, driver_number, track_id, car_type, weather_type)


# Middleware to disable browser caching during development
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/") and not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Serve Static Assets cleanly from current directory
app.mount("/", StaticFiles(directory=".", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)