"""Unit tests for the health check route."""

import asyncio
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


def _run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


@pytest.mark.unit
class TestHealthRoute:
    """Tests for GET /health endpoint logic."""

    def _import_health_check(self):
        """Import the health_check function (deferred to avoid import errors)."""
        from lightning_api.routes.health import health_check

        return health_check

    def test_healthy_when_db_connected(self):
        """Returns 200 with status 'healthy' when DB pool is available and responsive."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        with (
            patch("lightning_api.routes.health.get_pool", return_value=mock_pool),
            patch("lightning_api.routes.health.get_start_time", return_value=0.0),
            patch("lightning_api.routes.health.time") as mock_time,
        ):
            mock_time.monotonic.return_value = 3600.5

            health_check = self._import_health_check()
            response = _run_async(health_check())

        assert response.status_code == 200
        data = json.loads(response.body.decode())
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["uptime_seconds"] == 3600.5

        # Verify DB was actually queried
        mock_pool.get_connection.assert_called_once()
        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_degraded_when_pool_is_none(self):
        """Returns 503 with status 'degraded' when pool is not initialized."""
        with (
            patch("lightning_api.routes.health.get_pool", return_value=None),
            patch("lightning_api.routes.health.get_start_time", return_value=0.0),
            patch("lightning_api.routes.health.time") as mock_time,
        ):
            mock_time.monotonic.return_value = 100.0

            health_check = self._import_health_check()
            response = _run_async(health_check())

        assert response.status_code == 503
        data = json.loads(response.body.decode())
        assert data["status"] == "degraded"
        assert "error:" in data["database"]
        assert "not initialized" in data["database"]
        assert data["uptime_seconds"] == 100.0

    def test_degraded_when_db_connection_fails(self):
        """Returns 503 with status 'degraded' when getting a connection raises."""
        mariadb_mock = sys.modules["mariadb"]

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = mariadb_mock.Error(
            "Can't connect to server"
        )

        with (
            patch("lightning_api.routes.health.get_pool", return_value=mock_pool),
            patch("lightning_api.routes.health.get_start_time", return_value=0.0),
            patch("lightning_api.routes.health.time") as mock_time,
            patch("lightning_api.routes.health.mariadb", mariadb_mock),
        ):
            mock_time.monotonic.return_value = 50.0

            health_check = self._import_health_check()
            response = _run_async(health_check())

        assert response.status_code == 503
        data = json.loads(response.body.decode())
        assert data["status"] == "degraded"
        assert "error:" in data["database"]
        assert data["uptime_seconds"] == 50.0

    def test_degraded_when_query_fails(self):
        """Returns 503 with status 'degraded' when SELECT 1 raises."""
        mariadb_mock = sys.modules["mariadb"]

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = mariadb_mock.Error("Lost connection")

        with (
            patch("lightning_api.routes.health.get_pool", return_value=mock_pool),
            patch("lightning_api.routes.health.get_start_time", return_value=0.0),
            patch("lightning_api.routes.health.time") as mock_time,
            patch("lightning_api.routes.health.mariadb", mariadb_mock),
        ):
            mock_time.monotonic.return_value = 200.0

            health_check = self._import_health_check()
            response = _run_async(health_check())

        assert response.status_code == 503
        data = json.loads(response.body.decode())
        assert data["status"] == "degraded"
        assert "error:" in data["database"]
        assert data["uptime_seconds"] == 200.0
        # Connection should still be closed even on error
        mock_conn.close.assert_called_once()

    def test_uptime_calculated_from_start_time(self):
        """Uptime is calculated as current monotonic time minus start time."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        with (
            patch("lightning_api.routes.health.get_pool", return_value=mock_pool),
            patch("lightning_api.routes.health.get_start_time", return_value=1000.0),
            patch("lightning_api.routes.health.time") as mock_time,
        ):
            mock_time.monotonic.return_value = 1042.7

            health_check = self._import_health_check()
            response = _run_async(health_check())

        data = json.loads(response.body.decode())
        assert abs(data["uptime_seconds"] - 42.7) < 0.01
