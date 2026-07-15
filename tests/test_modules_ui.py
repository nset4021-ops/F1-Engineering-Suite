from unittest.mock import MagicMock, patch

import pytest

import app


def make_fake_st(number_values=None, text_values=None, slider_values=None, radio_value=""):
    """Build a MagicMock standing in for streamlit with configurable widget returns."""
    st = MagicMock()

    def make_column():
        col = MagicMock()
        if number_values is not None:
            col.number_input.side_effect = list(number_values)
        if text_values is not None:
            col.text_input.side_effect = list(text_values)
        return col

    st.columns.side_effect = lambda n, *a, **k: [make_column() for _ in range(n)]
    if slider_values is not None:
        st.sidebar.slider.side_effect = list(slider_values)
    st.radio.return_value = radio_value
    st.sidebar.radio.return_value = radio_value
    return st


class TestStrategyEngine:
    def test_uses_real_data_when_fetch_succeeds(self):
        st = make_fake_st(number_values=[44, 9839])
        raw = [{"lap_number": i, "lap_duration": 90.0 + i, "compound": "SOFT"} for i in range(1, 6)]
        with patch("app.st", st), patch("app.fetch_openf1", return_value=(raw, "real")):
            app.strategy_engine()
        assert st.plotly_chart.called
        st.error.assert_not_called()

    def test_falls_back_to_mock_when_fetch_fails(self):
        st = make_fake_st(number_values=[44, 9839])
        with patch("app.st", st), patch("app.fetch_openf1", return_value=([], "boom")):
            app.strategy_engine()
        st.error.assert_called_once()
        assert st.plotly_chart.called

    def test_low_grip_triggers_box_warning(self):
        st = make_fake_st(number_values=[44, 9839])
        # Steep degradation + rising lap times drive theoretical grip below 45.
        raw = [{"lap_number": i, "lap_duration": 90.0 + 3 * i, "compound": "SOFT"} for i in range(1, 25)]
        with patch("app.st", st), patch("app.fetch_openf1", return_value=(raw, "real")):
            app.strategy_engine()
        warning_html = " ".join(str(c.args[0]) for c in st.markdown.call_args_list)
        assert "BOX BOX" in warning_html


class TestSuspensionLab:
    def test_renders_two_charts_and_metric(self):
        st = make_fake_st(slider_values=[2.0, 380])
        with patch("app.st", st):
            app.suspension_lab()
        assert st.metric.called
        assert st.plotly_chart.call_count == 2


class TestTelemetryCenter:
    def test_uses_real_data_when_both_endpoints_succeed(self):
        st = make_fake_st(text_values=["44", "9839"])
        car = [
            {"date": f"2026-01-01T00:00:0{i}Z", "speed": 200 + i, "throttle": 50, "brake": 0}
            for i in range(5)
        ]
        loc = [
            {"date": f"2026-01-01T00:00:0{i}Z", "x": float(i), "y": float(i)}
            for i in range(5)
        ]
        with patch("app.st", st), patch("app.fetch_openf1", side_effect=[(car, "real"), (loc, "real")]):
            app.telemetry_center()
        st.error.assert_not_called()
        assert st.plotly_chart.call_count == 2

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Known app bug: mock_car_data/mock_location_data produce tz-naive "
            "timestamps, so telemetry_center's mock-fallback path raises "
            "TypeError at `.dt.tz_convert(None)`."
        ),
    )
    def test_falls_back_to_mock_when_fetch_fails(self):
        st = make_fake_st(text_values=["44", "9839"])
        with patch("app.st", st), patch("app.fetch_openf1", side_effect=[([], "e1"), ([], "e2")]):
            app.telemetry_center()
        st.error.assert_called_once()
        assert st.plotly_chart.call_count == 2


class TestApplyThemeAndMain:
    def test_apply_theme_sets_page_config(self):
        st = MagicMock()
        with patch("app.st", st):
            app.apply_theme()
        st.set_page_config.assert_called_once()
        st.markdown.assert_called_once()

    def test_main_routes_to_strategy_engine(self):
        st = make_fake_st(radio_value="THE AI PIT WALL (STRATEGY ENGINE)")
        with patch("app.st", st), patch("app.apply_theme") as theme, patch(
            "app.strategy_engine"
        ) as strat, patch("app.suspension_lab") as susp, patch("app.telemetry_center") as tele:
            app.main()
        theme.assert_called_once()
        strat.assert_called_once()
        susp.assert_not_called()
        tele.assert_not_called()

    def test_main_routes_to_suspension_lab(self):
        st = make_fake_st(radio_value="SUSPENSION LAB (KINEMATICS SIMULATOR)")
        with patch("app.st", st), patch("app.apply_theme"), patch(
            "app.strategy_engine"
        ) as strat, patch("app.suspension_lab") as susp, patch("app.telemetry_center") as tele:
            app.main()
        susp.assert_called_once()
        strat.assert_not_called()
        tele.assert_not_called()

    def test_main_routes_to_telemetry_center(self):
        st = make_fake_st(radio_value="TELEMETRY CENTER (REAL DATA VISUALIZER)")
        with patch("app.st", st), patch("app.apply_theme"), patch(
            "app.strategy_engine"
        ) as strat, patch("app.suspension_lab") as susp, patch("app.telemetry_center") as tele:
            app.main()
        tele.assert_called_once()
        strat.assert_not_called()
        susp.assert_not_called()
