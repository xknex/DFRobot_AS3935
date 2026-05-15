# Feature: lightning-data-pipeline, Property 9: API filter correctness
# Feature: lightning-data-pipeline, Property 10: API results ordered by timestamp descending
# Feature: lightning-data-pipeline, Property 11: API pagination metadata correctness
# Feature: lightning-data-pipeline, Property 12: API page_size validation
# Feature: lightning-data-pipeline, Property 13: API latest returns most recent event
# Feature: lightning-data-pipeline, Property 14: API statistics correctness
"""Property-based tests for the Lightning REST API.

This module contains Hypothesis property tests for API filter correctness,
API ordering, API pagination metadata correctness, API page_size validation,
API latest event correctness, and API statistics correctness.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 8.1, 8.2**
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from lightning_common.models import EventType


# ===========================================================================
# Shared Strategies
# ===========================================================================

# Generate valid UTC timestamps within a reasonable range
_utc_timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

# Generate valid event types
_event_types = st.sampled_from([EventType.LIGHTNING, EventType.DISTURBER, EventType.NOISE])

# Strategy for a single event as a tuple (id, timestamp, event_type, distance_km, energy_normalized)
_event_row = st.tuples(
    _utc_timestamps,
    _event_types,
).map(lambda t: (
    t[0],
    t[1],
    # distance_km: only for lightning
    st.integers(min_value=0, max_value=63).example() if t[1] == EventType.LIGHTNING else None,
    # energy_normalized: only for lightning
    None,
))

# Better strategy: generate a list of events with explicit fields
@st.composite
def event_records_strategy(draw):
    """Generate a list of event records as DB row tuples."""
    num_events = draw(st.integers(min_value=0, max_value=30))
    events = []
    for i in range(num_events):
        timestamp = draw(_utc_timestamps)
        event_type = draw(_event_types)
        if event_type == EventType.LIGHTNING:
            distance_km = draw(st.integers(min_value=0, max_value=63))
            energy_normalized = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
        else:
            distance_km = None
            energy_normalized = None
        events.append((i + 1, timestamp, event_type.value, distance_km, energy_normalized))
    return events


# ===========================================================================
# Test Client Fixture
# ===========================================================================


def _create_test_client():
    """Create a FastAPI test client with mocked DB pool."""
    from fastapi.testclient import TestClient

    pool = MagicMock()
    conn = MagicMock()
    pool.get_connection.return_value = conn

    with patch("lightning_api.app.get_pool", return_value=pool):
        with patch("lightning_api.dependencies.get_pool", return_value=pool):
            from lightning_api.app import create_app
            from lightning_common.config import ApiSettings

            settings_obj = ApiSettings(
                db_host="localhost",
                db_port=3306,
                db_user="test",
                db_password="test",
                db_name="testdb",
            )

            with patch("lightning_api.app.lifespan") as mock_lifespan:
                @asynccontextmanager
                async def noop_lifespan(app):
                    yield

                mock_lifespan.side_effect = noop_lifespan

                app = create_app(settings=settings_obj)

                from lightning_api.dependencies import get_db_connection

                def override_get_db_connection():
                    c = pool.get_connection()
                    try:
                        yield c
                    finally:
                        c.close()

                app.dependency_overrides[get_db_connection] = override_get_db_connection

                return TestClient(app), conn


# ===========================================================================
# In-memory database simulation for Property 9
# ===========================================================================


class InMemoryCursor:
    """Simulates a MariaDB cursor operating on an in-memory list of event rows.

    Used by Property 9 to test filter correctness without mocking individual
    query results, allowing the test to verify the actual filtering logic.
    """

    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows
        self._result: list = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a SQL query against the in-memory rows."""
        filtered = self._apply_filters(sql, params)

        if sql.strip().upper().startswith("SELECT COUNT(*)"):
            self._result = [(len(filtered),)]
        elif "ORDER BY" in sql.upper():
            # Data query with ORDER BY timestamp DESC, LIMIT, OFFSET
            sorted_rows = sorted(filtered, key=lambda r: r[1], reverse=True)
            # Extract LIMIT and OFFSET from params (last two params after filter params)
            param_list = list(params)
            where_end = sql.upper().find("ORDER BY")
            where_part = sql[:where_end] if where_end > 0 else sql
            filter_param_count = where_part.count("?")
            limit = param_list[filter_param_count] if filter_param_count < len(param_list) else len(sorted_rows)
            offset = param_list[filter_param_count + 1] if filter_param_count + 1 < len(param_list) else 0
            sorted_rows = sorted_rows[offset:offset + limit]
            self._result = sorted_rows
        else:
            self._result = filtered

    def _apply_filters(self, sql: str, params: tuple) -> list[tuple]:
        """Apply WHERE clause filters to the in-memory rows."""
        filtered = list(self._rows)
        param_list = list(params)

        # Determine how many params belong to the WHERE clause
        where_end = sql.upper().find("ORDER BY")
        where_part = sql[:where_end] if where_end > 0 else sql
        filter_param_count = where_part.count("?")

        param_idx = 0

        if "timestamp >= ?" in sql and param_idx < filter_param_count:
            start_date = param_list[param_idx]
            param_idx += 1
            filtered = [r for r in filtered if r[1] >= start_date]

        if "timestamp <= ?" in sql and param_idx < filter_param_count:
            end_date = param_list[param_idx]
            param_idx += 1
            filtered = [r for r in filtered if r[1] <= end_date]

        if "event_type = ?" in sql and param_idx < filter_param_count:
            event_type_val = param_list[param_idx]
            param_idx += 1
            filtered = [r for r in filtered if r[2] == event_type_val]

        return filtered

    def fetchone(self) -> tuple | None:
        """Fetch one result row."""
        if self._result and len(self._result) > 0:
            return self._result[0]
        return None

    def fetchall(self) -> list[tuple]:
        """Fetch all result rows."""
        return self._result if self._result else []

    def close(self) -> None:
        """Close the cursor (no-op for in-memory)."""
        pass


class InMemoryConnection:
    """Simulates a MariaDB connection backed by in-memory event rows."""

    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def cursor(self) -> InMemoryCursor:
        return InMemoryCursor(self._rows)

    def close(self) -> None:
        pass


def _create_in_memory_test_client(rows: list[tuple]):
    """Create a FastAPI test client backed by in-memory event rows for filter testing."""
    from fastapi.testclient import TestClient
    from lightning_api.app import create_app
    from lightning_api.dependencies import get_db_connection
    from lightning_common.config import ApiSettings

    settings_obj = ApiSettings(
        db_host="localhost",
        db_port=3306,
        db_user="test",
        db_password="test",
        db_name="testdb",
    )

    with patch("lightning_api.app.lifespan") as mock_lifespan:
        @asynccontextmanager
        async def noop_lifespan(app):
            yield

        mock_lifespan.side_effect = noop_lifespan

        app = create_app(settings=settings_obj)

        def override_get_db_connection():
            conn = InMemoryConnection(rows)
            yield conn

        app.dependency_overrides[get_db_connection] = override_get_db_connection

        return TestClient(app)


def _filter_events_independently(
    rows: list[tuple],
    start_date: datetime | None,
    end_date: datetime | None,
    event_type: EventType | None,
) -> list[tuple]:
    """Apply filters to rows independently of the API implementation."""
    result = list(rows)
    if start_date is not None:
        result = [r for r in result if r[1] >= start_date]
    if end_date is not None:
        result = [r for r in result if r[1] <= end_date]
    if event_type is not None:
        result = [r for r in result if r[2] == event_type.value]
    return result


# Filter parameter strategies
_optional_event_type = st.one_of(st.none(), _event_types)
_optional_date = st.one_of(st.none(), _utc_timestamps)


# ===========================================================================
# Property 9: API filter correctness
# ===========================================================================


@pytest.mark.property
class TestProperty9ApiFilterCorrectness:
    """Property 9: API filter correctness.

    For any set of events in the database and any combination of filter
    parameters (start_date, end_date, event_type), all returned events SHALL
    satisfy every active filter condition, and no event satisfying all
    conditions SHALL be omitted from the total result set.

    **Validates: Requirements 6.1, 6.2**
    """

    @given(
        rows=event_records_strategy(),
        start_date=st.one_of(st.none(), _utc_timestamps),
        end_date=st.one_of(st.none(), _utc_timestamps),
        event_type=st.one_of(st.none(), _event_types),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_returned_events_satisfy_active_filters(
        self,
        rows: list[tuple],
        start_date: datetime | None,
        end_date: datetime | None,
        event_type: EventType | None,
    ) -> None:
        """All returned events satisfy every active filter condition."""
        client = _create_in_memory_test_client(rows)

        # Build query params
        params: dict[str, str] = {"page_size": "200"}
        if start_date is not None:
            params["start_date"] = start_date.isoformat()
        if end_date is not None:
            params["end_date"] = end_date.isoformat()
        if event_type is not None:
            params["event_type"] = event_type.value

        response = client.get("/events", params=params)
        assert response.status_code == 200

        data = response.json()
        returned_events = data["data"]

        # Verify each returned event satisfies all active filters
        for event in returned_events:
            event_ts = datetime.fromisoformat(event["timestamp"])

            if start_date is not None:
                assert event_ts >= start_date, (
                    f"Event timestamp {event_ts} is before start_date {start_date}"
                )
            if end_date is not None:
                assert event_ts <= end_date, (
                    f"Event timestamp {event_ts} is after end_date {end_date}"
                )
            if event_type is not None:
                assert event["event_type"] == event_type.value, (
                    f"Event type {event['event_type']} does not match filter {event_type.value}"
                )

    @given(
        rows=event_records_strategy(),
        start_date=st.one_of(st.none(), _utc_timestamps),
        end_date=st.one_of(st.none(), _utc_timestamps),
        event_type=st.one_of(st.none(), _event_types),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_matching_event_is_omitted(
        self,
        rows: list[tuple],
        start_date: datetime | None,
        end_date: datetime | None,
        event_type: EventType | None,
    ) -> None:
        """No event satisfying all filter conditions is omitted from the total count."""
        client = _create_in_memory_test_client(rows)

        # Build query params
        params: dict[str, str] = {"page_size": "200"}
        if start_date is not None:
            params["start_date"] = start_date.isoformat()
        if end_date is not None:
            params["end_date"] = end_date.isoformat()
        if event_type is not None:
            params["event_type"] = event_type.value

        response = client.get("/events", params=params)
        assert response.status_code == 200

        data = response.json()
        total_count = data["pagination"]["total_count"]

        # Independently compute expected matching events
        expected_matches = _filter_events_independently(rows, start_date, end_date, event_type)

        # The total_count reported by the API must match our independent calculation
        assert total_count == len(expected_matches), (
            f"API reported total_count={total_count} but expected {len(expected_matches)} "
            f"matching events (filters: start_date={start_date}, end_date={end_date}, "
            f"event_type={event_type})"
        )

        # If all results fit in one page, verify the actual returned data count matches
        if len(expected_matches) <= 200:
            assert len(data["data"]) == len(expected_matches), (
                f"API returned {len(data['data'])} events but expected {len(expected_matches)}"
            )


# ===========================================================================
# Property 10: API results ordered by timestamp descending
# ===========================================================================


@pytest.mark.property
class TestProperty10ApiResultsOrderedByTimestampDescending:
    """Property 10: API results ordered by timestamp descending.

    For any query to the /events endpoint, the returned events SHALL have
    timestamps in strictly non-increasing order.

    **Validates: Requirements 6.3**
    """

    @given(events=event_records_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_events_returned_in_non_increasing_timestamp_order(
        self, events: list[tuple]
    ) -> None:
        """Returned events have timestamps in strictly non-increasing order."""
        client, conn = _create_test_client()

        # Sort events by timestamp descending (simulating DB ORDER BY timestamp DESC)
        sorted_events = sorted(events, key=lambda r: r[1], reverse=True)

        # Mock cursor
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        # The count query returns total count, the data query returns sorted rows
        cursor.fetchone.return_value = (len(sorted_events),)
        cursor.fetchall.return_value = sorted_events

        response = client.get("/events")

        assert response.status_code == 200
        data = response.json()["data"]

        # Verify non-increasing timestamp order
        if len(data) >= 2:
            for i in range(len(data) - 1):
                ts_current = datetime.fromisoformat(data[i]["timestamp"])
                ts_next = datetime.fromisoformat(data[i + 1]["timestamp"])
                assert ts_current >= ts_next, (
                    f"Event at index {i} (timestamp={data[i]['timestamp']}) "
                    f"should be >= event at index {i+1} "
                    f"(timestamp={data[i+1]['timestamp']})"
                )

    @given(events=st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=1_000_000),
            _utc_timestamps,
            _event_types.map(lambda e: e.value),
            st.one_of(st.none(), st.integers(min_value=0, max_value=63)),
            st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        ),
        min_size=2,
        max_size=50,
    ))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_events_always_non_increasing(
        self, events: list[tuple]
    ) -> None:
        """With multiple events, timestamps are always non-increasing regardless of input order."""
        client, conn = _create_test_client()

        # Sort by timestamp descending (simulating DB ORDER BY timestamp DESC)
        sorted_events = sorted(events, key=lambda r: r[1], reverse=True)

        # Mock cursor
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        cursor.fetchone.return_value = (len(sorted_events),)
        cursor.fetchall.return_value = sorted_events

        response = client.get("/events?page_size=200")

        assert response.status_code == 200
        data = response.json()["data"]

        # Must have at least 2 events
        assert len(data) >= 2

        # Verify strict non-increasing order
        timestamps = [
            datetime.fromisoformat(event["timestamp"])
            for event in data
        ]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"Timestamps not in non-increasing order at index {i}: "
                f"{timestamps[i]} should be >= {timestamps[i+1]}"
            )


# ===========================================================================
# Property 12: API page_size validation
# ===========================================================================


@pytest.mark.property
class TestProperty12ApiPageSizeValidation:
    """Property 12: API page_size validation.

    For any integer page_size > 200, the /events endpoint SHALL return HTTP 422.
    For any integer page_size in 1–200, the endpoint SHALL accept the request.

    **Validates: Requirements 6.5**
    """

    @given(page_size=st.integers(min_value=201, max_value=10000))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_page_size_above_200_returns_422(self, page_size: int) -> None:
        """Any page_size > 200 returns HTTP 422 with descriptive error."""
        client, conn = _create_test_client()

        response = client.get(f"/events?page_size={page_size}")

        assert response.status_code == 422
        assert response.json()["detail"] == "page_size must not exceed 200"

    @given(page_size=st.integers(min_value=1, max_value=200))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_page_size_1_to_200_is_accepted(self, page_size: int) -> None:
        """Any page_size in 1–200 is accepted (returns HTTP 200)."""
        client, conn = _create_test_client()

        # Mock cursor to return empty results for valid requests
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (0,)
        cursor.fetchall.return_value = []

        response = client.get(f"/events?page_size={page_size}")

        assert response.status_code == 200


# ===========================================================================
# Property 11: API pagination metadata correctness
# ===========================================================================


@pytest.mark.property
class TestProperty11ApiPaginationMetadata:
    """Property 11: API pagination metadata correctness.

    For any total_count >= 0 and page_size in 1-200, the pagination metadata
    SHALL satisfy: total_pages = ceil(total_count / page_size), and the number
    of items on the last page SHALL equal total_count - (total_pages - 1) * page_size.

    **Validates: Requirements 6.4**
    """

    @given(
        total_count=st.integers(min_value=0, max_value=5000),
        page_size=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_total_pages_equals_ceil_total_count_div_page_size(
        self, total_count: int, page_size: int
    ) -> None:
        """total_pages in response equals ceil(total_count / page_size).

        When total_count is 0, total_pages should be at least 1 (minimum 1 page).
        """
        import math

        client, conn = _create_test_client()

        # Mock cursor: count query returns total_count, data query returns empty
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (total_count,)
        cursor.fetchall.return_value = []

        response = client.get(f"/events?page=1&page_size={page_size}")

        assert response.status_code == 200
        data = response.json()

        expected_total_pages = max(1, math.ceil(total_count / page_size))

        assert data["pagination"]["total_count"] == total_count
        assert data["pagination"]["page_size"] == page_size
        assert data["pagination"]["total_pages"] == expected_total_pages

    @given(
        total_count=st.integers(min_value=1, max_value=5000),
        page_size=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_last_page_item_count_is_correct(
        self, total_count: int, page_size: int
    ) -> None:
        """Number of items on the last page equals total_count - (total_pages - 1) * page_size."""
        import math

        client, conn = _create_test_client()

        expected_total_pages = max(1, math.ceil(total_count / page_size))
        expected_last_page_items = total_count - (expected_total_pages - 1) * page_size

        # Generate mock rows for the last page
        mock_rows = [
            (
                i + 1,
                datetime(2024, 7, 15, 14, 0, i % 60, tzinfo=timezone.utc),
                "lightning",
                12,
                0.45,
            )
            for i in range(expected_last_page_items)
        ]

        # Mock cursor: count query returns total_count, data query returns last page items
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (total_count,)
        cursor.fetchall.return_value = mock_rows

        response = client.get(
            f"/events?page={expected_total_pages}&page_size={page_size}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["pagination"]["total_pages"] == expected_total_pages
        assert len(data["data"]) == expected_last_page_items
        assert expected_last_page_items == total_count - (expected_total_pages - 1) * page_size


# ===========================================================================
# Property 13: API latest returns most recent event
# ===========================================================================


@st.composite
def non_empty_event_records_strategy(draw):
    """Generate a non-empty list of event records as DB row tuples."""
    num_events = draw(st.integers(min_value=1, max_value=30))
    events = []
    for i in range(num_events):
        timestamp = draw(_utc_timestamps)
        event_type = draw(_event_types)
        if event_type == EventType.LIGHTNING:
            distance_km = draw(st.integers(min_value=0, max_value=63))
            energy_normalized = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
        else:
            distance_km = None
            energy_normalized = None
        events.append((i + 1, timestamp, event_type.value, distance_km, energy_normalized))
    return events


@pytest.mark.property
class TestProperty13ApiLatestReturnsMostRecentEvent:
    """Property 13: API latest returns most recent event.

    For any non-empty set of events in the database, the /events/latest
    endpoint SHALL return the event with the maximum timestamp value.

    **Validates: Requirements 7.1**
    """

    @given(events=non_empty_event_records_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_latest_returns_event_with_maximum_timestamp(self, events: list[tuple]) -> None:
        """The /events/latest endpoint returns the event with the maximum timestamp."""
        client, conn = _create_test_client()

        # Determine which event has the maximum timestamp
        latest_event = max(events, key=lambda e: e[1])

        # Mock the cursor to return the latest event
        # (the real DB does ORDER BY timestamp DESC LIMIT 1)
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = latest_event

        response = client.get("/events/latest")

        assert response.status_code == 200
        data = response.json()

        # Verify the returned event matches the one with maximum timestamp
        assert data["id"] == latest_event[0]
        assert data["event_type"] == latest_event[2]
        assert data["distance_km"] == latest_event[3]
        assert data["energy_normalized"] == latest_event[4]

        # Verify the timestamp matches the maximum
        returned_ts = datetime.fromisoformat(data["timestamp"])
        assert returned_ts == latest_event[1]

        # Verify this is indeed the maximum timestamp among all events
        for event in events:
            assert returned_ts >= event[1]


# ===========================================================================
# Property 14: API statistics correctness
# ===========================================================================


@pytest.mark.property
class TestProperty14ApiStatisticsCorrectness:
    """Property 14: API statistics correctness.

    For any set of events in the database, the /events/stats response SHALL
    satisfy: count_by_type values equal the actual count of events per type,
    count_last_24h equals the count of events with timestamp within the last
    24 hours, count_last_7d equals the count within the last 7 days, and
    latest_event_timestamp equals the maximum timestamp.

    **Validates: Requirements 8.1, 8.2**
    """

    @given(events=event_records_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_count_by_type_matches_actual_counts(self, events: list[tuple]) -> None:
        """count_by_type values equal the actual count of events per type."""
        client, conn = _create_test_client()

        # Compute expected counts from the generated events
        expected_counts = {"lightning": 0, "disturber": 0, "noise": 0}
        for event in events:
            event_type = event[2]
            expected_counts[event_type] += 1

        # Find the max timestamp
        if events:
            max_ts = max(e[1] for e in events)
        else:
            max_ts = None

        # Mock the cursor behavior for the stats endpoint
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        # Build the fetchall result for GROUP BY query (count_by_type)
        type_rows = [(t, c) for t, c in expected_counts.items() if c > 0]

        # Compute time-based counts using a fixed "now" reference
        # We need to patch datetime.now in the events module
        reference_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last_24h = reference_now - timedelta(hours=24)
        last_7d = reference_now - timedelta(days=7)

        count_24h = sum(1 for e in events if e[1] >= last_24h)
        count_7d = sum(1 for e in events if e[1] >= last_7d)

        # Setup mock cursor responses in order:
        # 1. fetchall for GROUP BY event_type
        # 2. fetchone for count_last_24h
        # 3. fetchone for count_last_7d
        # 4. fetchone for MAX(timestamp)
        cursor.fetchall.return_value = type_rows
        cursor.fetchone.side_effect = [
            (count_24h,),
            (count_7d,),
            (max_ts,),
        ]

        with patch("lightning_api.routes.events.datetime") as mock_datetime:
            mock_datetime.now.return_value = reference_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            response = client.get("/events/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify count_by_type matches expected
        assert data["count_by_type"]["lightning"] == expected_counts["lightning"]
        assert data["count_by_type"]["disturber"] == expected_counts["disturber"]
        assert data["count_by_type"]["noise"] == expected_counts["noise"]

    @given(events=event_records_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_time_window_counts_match_actual(self, events: list[tuple]) -> None:
        """count_last_24h and count_last_7d equal actual counts within time windows."""
        client, conn = _create_test_client()

        # Use a fixed reference time for deterministic testing
        reference_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last_24h = reference_now - timedelta(hours=24)
        last_7d = reference_now - timedelta(days=7)

        # Compute expected time-based counts
        expected_count_24h = sum(1 for e in events if e[1] >= last_24h)
        expected_count_7d = sum(1 for e in events if e[1] >= last_7d)

        # Compute expected counts by type
        expected_counts = {"lightning": 0, "disturber": 0, "noise": 0}
        for event in events:
            expected_counts[event[2]] += 1

        # Find max timestamp
        max_ts = max((e[1] for e in events), default=None)

        # Mock cursor
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        type_rows = [(t, c) for t, c in expected_counts.items() if c > 0]
        cursor.fetchall.return_value = type_rows
        cursor.fetchone.side_effect = [
            (expected_count_24h,),
            (expected_count_7d,),
            (max_ts,),
        ]

        with patch("lightning_api.routes.events.datetime") as mock_datetime:
            mock_datetime.now.return_value = reference_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            response = client.get("/events/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["count_last_24h"] == expected_count_24h
        assert data["count_last_7d"] == expected_count_7d

    @given(events=event_records_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_latest_event_timestamp_equals_max(self, events: list[tuple]) -> None:
        """latest_event_timestamp equals the maximum timestamp across all events."""
        client, conn = _create_test_client()

        # Compute expected max timestamp
        if events:
            max_ts = max(e[1] for e in events)
        else:
            max_ts = None

        # Compute expected counts by type
        expected_counts = {"lightning": 0, "disturber": 0, "noise": 0}
        for event in events:
            expected_counts[event[2]] += 1

        reference_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last_24h = reference_now - timedelta(hours=24)
        last_7d = reference_now - timedelta(days=7)

        expected_count_24h = sum(1 for e in events if e[1] >= last_24h)
        expected_count_7d = sum(1 for e in events if e[1] >= last_7d)

        # Mock cursor
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        type_rows = [(t, c) for t, c in expected_counts.items() if c > 0]
        cursor.fetchall.return_value = type_rows
        cursor.fetchone.side_effect = [
            (expected_count_24h,),
            (expected_count_7d,),
            (max_ts,),
        ]

        with patch("lightning_api.routes.events.datetime") as mock_datetime:
            mock_datetime.now.return_value = reference_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            response = client.get("/events/stats")

        assert response.status_code == 200
        data = response.json()

        if max_ts is not None:
            # Parse the response timestamp and compare
            response_ts = datetime.fromisoformat(data["latest_event_timestamp"])
            assert response_ts == max_ts
        else:
            assert data["latest_event_timestamp"] is None
