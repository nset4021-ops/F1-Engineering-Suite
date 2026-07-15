from unittest.mock import MagicMock, patch

import requests

import app


class FakeResponse:
    def __init__(self, payload, raise_exc=None):
        self._payload = payload
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc

    def json(self):
        return self._payload


class TestFetchOpenF1:
    def setup_method(self):
        app.fetch_openf1.clear()

    def test_successful_fetch_returns_payload_and_real(self):
        payload = [{"lap_number": 1}]
        with patch("app.requests.get", return_value=FakeResponse(payload)) as mock_get:
            data, status = app.fetch_openf1("laps", {"session_key": 1})
        assert data == payload
        assert status == "real"
        mock_get.assert_called_once()

    def test_empty_list_treated_as_error(self):
        with patch("app.requests.get", return_value=FakeResponse([])):
            data, status = app.fetch_openf1("laps", {"session_key": 2})
        assert data == []
        assert "No data returned" in status

    def test_non_list_payload_treated_as_error(self):
        with patch("app.requests.get", return_value=FakeResponse({"error": "bad"})):
            data, status = app.fetch_openf1("laps", {"session_key": 3})
        assert data == []
        assert status != "real"

    def test_request_exception_returns_error_string(self):
        with patch("app.requests.get", side_effect=requests.RequestException("boom")):
            data, status = app.fetch_openf1("laps", {"session_key": 4})
        assert data == []
        assert "boom" in status

    def test_http_error_status_propagates(self):
        resp = FakeResponse([], raise_exc=requests.HTTPError("404 Not Found"))
        with patch("app.requests.get", return_value=resp):
            data, status = app.fetch_openf1("laps", {"session_key": 5})
        assert data == []
        assert "404" in status

    def test_url_and_params_forwarded(self):
        with patch("app.requests.get", return_value=FakeResponse([{"a": 1}])) as mock_get:
            app.fetch_openf1("car_data", {"session_key": 6, "driver_number": 44})
        args, kwargs = mock_get.call_args
        assert args[0] == f"{app.OPENF1_BASE}/car_data"
        assert kwargs["params"] == {"session_key": 6, "driver_number": 44}
        assert kwargs["timeout"] == 10
