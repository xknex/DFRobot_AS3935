"""Unit tests for the events routes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lightning_api.models import EventResponse, PaginatedEventsResponse, StatsResponse


@pytest.fixture
def mock_pool():
    """Create a mock connection pool that returns a mock connection."""
    pool = MagicMock()
    conn = MagicMock()
    pool.get_connection.return_value = conn
    return pool, conn


@pytest.fixture
def client(mock_pool):
    """Create a test client with mocked DB pool."""
    pool, _ = mock_pool

    with patch("lightning_api.app.get_pool", return_value=pool):
        with patch("lightning_api.dependencies.get_pool", return_value=pool):
            from lightning_api.app import create_app
            from lightning_common.config import ApiSettings

            settings = ApiSettings(
                db_host="localhost",
                db_port=3306,
                db_user="test",
                db_password="test",
                db_name="testdb",
            )

            # Patch lifespan to avoid real DB pool creation
            with patch("lightning_api.app.lifespan") as mock_lifespan:
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def noop_lifespan(app):
                    yield

                mock_lifespan.side_effect = noop_lifespan

                app = create_app(settings=settings)

                # Override the dependency to use our mock
                from lightning_api.dependencies import get_db_connection

                def override_get_db_connection():
                    conn = pool.get_connection()
                    try:
                        yield conn
                    finally:
                        conn.close()

                app.dependency_overrides[get_db_connection] = override_get_db_connection

                yield TestClient(app)


@pytest.fixture
def mock_cursor(mock_pool):
    """Return the mock cursor from the mock connection."""
    _, conn = mock_pool
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return cursor


class TestListEvents:
    """Tests for GET /events endpoint."""

    def test_returns_paginated_events(self, client, mock_cursor):
        """Test basic paginated response with events."""
        # Setup: count query returns 2, data query returns 2 rows
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            (1, datetime(2024, 7, 15, 14, 32, 1, tzinfo=timezone.utc), "lightning", 12, 0.45),
            (2, datetime(2024, 7, 15, 14, 33, 0, tzinfo=timezone.utc), "noise", None, None),
        ]

        response = client.get("/events")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_count"] == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 50
        assert data["pagination"]["total_pages"] == 1
        assert len(data["data"]) == 2
        assert data["data"][0]["event_type"] == "lightning"
        assert data["data"][0]["distance_km"] == 12

    def test_empty_results(self, client, mock_cursor):
        """Test response when no events exist."""
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.fetchall.return_value = []

        response = client.get("/events")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_count"] == 0
        assert data["pagination"]["total_pages"] == 1
        assert data["data"] == []

    def test_page_size_exceeds_200_returns_422(self, client, mock_cursor):
        """Test that page_size > 200 returns 422."""
        response = client.get("/events?page_size=201")

        assert response.status_code == 422
        assert response.json()["detail"] == "page_size must not exceed 200"

    def test_page_less_than_1_returns_422(self, client, mock_cursor):
        """Test that page < 1 returns 422."""
        response = client.get("/events?page=0")

        assert response.status_code == 422
        assert response.json()["detail"] == "page must be at least 1"

    def test_custom_pagination_params(self, client, mock_cursor):
        """Test custom page and page_size parameters."""
        mock_cursor.fetchone.return_value = (100,)
        mock_cursor.fetchall.return_value = []

        response = client.get("/events?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["page_size"] == 10
        assert data["pagination"]["total_pages"] == 10

    def test_filter_by_event_type(self, client, mock_cursor):
        """Test filtering by event_type."""
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            (1, datetime(2024, 7, 15, 14, 32, 1, tzinfo=timezone.utc), "lightning", 12, 0.45),
        ]

        response = client.get("/events?event_type=lightning")

        assert response.status_code == 200
        # Verify the query included event_type filter
        calls = mock_cursor.execute.call_args_list
        # The count query should contain event_type filter
        assert "event_type = ?" in calls[0][0][0]


class TestLatestEvent:
    """Tests for GET /events/latest endpoint."""

    def test_returns_latest_event(self, client, mock_cursor):
        """Test returning the most recent event."""
        mock_cursor.fetchone.return_value = (
            150,
            datetime(2024, 7, 15, 14, 32, 1, tzinfo=timezone.utc),
            "lightning",
            12,
            0.45,
        )

        response = client.get("/events/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 150
        assert data["event_type"] == "lightning"
        assert data["distance_km"] == 12

    def test_no_events_returns_404(self, client, mock_cursor):
        """Test 404 when no events exist."""
        mock_cursor.fetchone.return_value = None

        response = client.get("/events/latest")

        assert response.status_code == 404
        assert response.json()["detail"] == "No events found"


class TestStats:
    """Tests for GET /events/stats endpoint."""

    def test_returns_stats(self, client, mock_cursor):
        """Test returning event statistics."""
        # Setup sequential fetchone/fetchall calls:
        # 1. fetchall for count_by_type GROUP BY
        # 2. fetchone for count_last_24h
        # 3. fetchone for count_last_7d
        # 4. fetchone for latest_event_timestamp
        mock_cursor.fetchall.return_value = [
            ("lightning", 42),
            ("disturber", 85),
            ("noise", 23),
        ]
        mock_cursor.fetchone.side_effect = [
            (5,),   # count_last_24h
            (28,),  # count_last_7d
            (datetime(2024, 7, 15, 14, 32, 1, tzinfo=timezone.utc),),  # latest timestamp
        ]

        response = client.get("/events/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["count_by_type"]["lightning"] == 42
        assert data["count_by_type"]["disturber"] == 85
        assert data["count_by_type"]["noise"] == 23
        assert data["count_last_24h"] == 5
        assert data["count_last_7d"] == 28
        assert data["latest_event_timestamp"] is not None

    def test_empty_database_returns_zero_counts(self, client, mock_cursor):
        """Test stats with empty database returns zeros and null timestamp."""
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.side_effect = [
            (0,),    # count_last_24h
            (0,),    # count_last_7d
            (None,),  # latest timestamp
        ]

        response = client.get("/events/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["count_by_type"]["lightning"] == 0
        assert data["count_by_type"]["disturber"] == 0
        assert data["count_by_type"]["noise"] == 0
        assert data["count_last_24h"] == 0
        assert data["count_last_7d"] == 0
        assert data["latest_event_timestamp"] is None
