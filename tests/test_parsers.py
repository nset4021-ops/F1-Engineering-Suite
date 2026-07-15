import math

import numpy as np
import pandas as pd
import pytest

import app


class TestParseLaps:
    def test_returns_sorted_normalized_frame(self):
        raw = [
            {"lap_number": 3, "lap_duration": 92.1, "compound": "soft"},
            {"lap_number": 1, "lap_duration": 91.2, "compound": "Medium"},
            {"lap_number": 2, "lap_duration": 91.7, "compound": "HARD"},
        ]
        df = app.parse_laps(raw)
        assert list(df.columns) == ["lap_number", "lap_time", "compound"]
        assert df["lap_number"].tolist() == [1, 2, 3]
        assert df["compound"].tolist() == ["MEDIUM", "HARD", "SOFT"]
        assert df["lap_time"].dtype == float

    def test_lap_time_alias_lap_time_key(self):
        df = app.parse_laps([{"lap_number": 1, "lap_time": 90.0}])
        assert df["lap_time"].iloc[0] == 90.0

    def test_compound_aliases_and_default(self):
        raw = [
            {"lap_number": 1, "lap_duration": 90.0, "tyre_compound": "wet"},
            {"lap_number": 2, "lap_duration": 90.0, "stint_compound": "inter"},
            {"lap_number": 3, "lap_duration": 90.0},
        ]
        df = app.parse_laps(raw)
        assert df["compound"].tolist() == ["WET", "INTER", "UNKNOWN"]

    def test_rows_missing_time_or_number_are_skipped(self):
        raw = [
            {"lap_number": 1, "lap_duration": 90.0, "compound": "SOFT"},
            {"lap_number": 2, "compound": "SOFT"},
            {"lap_duration": 90.0, "compound": "SOFT"},
        ]
        df = app.parse_laps(raw)
        assert len(df) == 1
        assert df["lap_number"].iloc[0] == 1

    def test_empty_input_returns_empty_frame_with_columns(self):
        df = app.parse_laps([])
        assert df.empty
        assert list(df.columns) == ["lap_number", "lap_time", "compound"]


class TestComputeWishboneGeometry:
    def test_zero_roll_produces_zero_camber(self):
        _, camber = app.compute_wishbone_geometry(0.0, 380)
        assert camber == pytest.approx(0.0, abs=1e-9)

    def test_geometry_shape_and_segments(self):
        geometry, _ = app.compute_wishbone_geometry(2.0, 380)
        assert list(geometry.columns) == ["x", "y", "segment"]
        assert len(geometry) == 6
        assert geometry["segment"].tolist() == [
            "chassis",
            "upper arm",
            "upright",
            "upright",
            "lower arm",
            "chassis",
        ]

    def test_positive_roll_gives_negative_camber(self):
        _, camber = app.compute_wishbone_geometry(5.0, 380)
        assert camber < 0

    def test_camber_sign_is_antisymmetric(self):
        _, pos = app.compute_wishbone_geometry(3.0, 380)
        _, neg = app.compute_wishbone_geometry(-3.0, 380)
        assert pos == pytest.approx(-neg)

    def test_wheel_x_shifts_with_roll(self):
        geometry, _ = app.compute_wishbone_geometry(4.0, 400)
        expected_shift = 400 * math.sin(math.radians(4.0))
        assert geometry["x"].iloc[2] == pytest.approx(400 + expected_shift * 0.45)


class TestParseCarData:
    def test_parses_and_sorts_by_timestamp(self):
        raw = [
            {"date": "2026-01-01T00:00:02Z", "speed": 300, "throttle": 90, "brake": 0},
            {"date": "2026-01-01T00:00:00Z", "speed": 250, "throttle": 50, "brake": 10},
        ]
        df = app.parse_car_data(raw)
        assert list(df.columns) == ["timestamp", "speed", "throttle", "brake"]
        assert df["speed"].tolist() == [250.0, 300.0]

    def test_timestamp_alias(self):
        raw = [{"timestamp": "2026-01-01T00:00:00Z", "speed": 1, "throttle": 2, "brake": 3}]
        df = app.parse_car_data(raw)
        assert len(df) == 1

    def test_incomplete_rows_skipped(self):
        raw = [
            {"date": "2026-01-01T00:00:00Z", "speed": 1, "throttle": 2, "brake": 3},
            {"date": "2026-01-01T00:00:01Z", "speed": 1, "throttle": 2},
        ]
        df = app.parse_car_data(raw)
        assert len(df) == 1

    def test_invalid_timestamp_dropped(self):
        raw = [
            {"date": "not-a-date", "speed": 1, "throttle": 2, "brake": 3},
            {"date": "2026-01-01T00:00:00Z", "speed": 1, "throttle": 2, "brake": 3},
        ]
        df = app.parse_car_data(raw)
        assert len(df) == 1

    def test_empty_returns_columns(self):
        df = app.parse_car_data([])
        assert df.empty
        assert list(df.columns) == ["timestamp", "speed", "throttle", "brake"]


class TestParseLocationData:
    def test_parses_and_sorts(self):
        raw = [
            {"date": "2026-01-01T00:00:01Z", "x": 5, "y": 6},
            {"date": "2026-01-01T00:00:00Z", "x": 1, "y": 2},
        ]
        df = app.parse_location_data(raw)
        assert df["x"].tolist() == [1.0, 5.0]

    def test_incomplete_rows_skipped(self):
        raw = [
            {"date": "2026-01-01T00:00:00Z", "x": 1, "y": 2},
            {"date": "2026-01-01T00:00:01Z", "x": 1},
        ]
        assert len(app.parse_location_data(raw)) == 1

    def test_empty_returns_columns(self):
        df = app.parse_location_data([])
        assert df.empty
        assert list(df.columns) == ["timestamp", "x", "y"]


class TestMockData:
    def test_mock_lap_data(self):
        laps = app.mock_lap_data()
        assert len(laps) == 9
        assert all(set(l) == {"lap_number", "lap_duration", "compound"} for l in laps)
        assert [l["lap_number"] for l in laps] == list(range(1, 10))

    def test_mock_car_data(self):
        df = app.mock_car_data()
        assert list(df.columns) == ["timestamp", "speed", "throttle", "brake"]
        assert len(df) == 200
        assert df["throttle"].between(0, 100).all()

    def test_mock_location_data(self):
        df = app.mock_location_data()
        assert list(df.columns) == ["timestamp", "x", "y"]
        assert len(df) == 200
