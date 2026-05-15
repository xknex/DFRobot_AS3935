# Implementation Plan: Lightning Data Pipeline

## Overview

This plan implements the Lightning Data Pipeline as two new services (Collector and REST API) sharing a common library, deployed as systemd units on a Raspberry Pi Zero 2W. Implementation proceeds bottom-up: shared infrastructure first, then the collector service, then the REST API, followed by systemd configuration and testing.

## Tasks

- [x] 1. Set up shared infrastructure (`lightning_common`)
  - [x] 1.1 Create `lightning_common` package with configuration module
    - Create `src/lightning_common/__init__.py`, `src/lightning_common/config.py`
    - Implement `CollectorSettings` and `ApiSettings` using `pydantic-settings` with `TomlConfigSettingsSource`
    - Include env prefix `LIGHTNING_`, TOML fallback, port validation (1–65535), I2C address validation (0x01, 0x02, 0x03)
    - Exclude `db_password` from repr for credential masking
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 12.1_

  - [x] 1.2 Create shared data models
    - Create `src/lightning_common/models.py`
    - Implement `EventType` (StrEnum: lightning, disturber, noise) and `EventRecord` (pydantic BaseModel with timestamp, event_type, distance_km, energy_normalized)
    - Ensure `distance_km` and `energy_normalized` are `None` for non-lightning events
    - _Requirements: 1.2_

  - [x] 1.3 Create database schema helper module
    - Create `src/lightning_common/db.py`
    - Implement `create_tables_if_not_exist()` function with the events table DDL (id, timestamp, event_type, distance_km, energy_normalized) and indexes on timestamp and event_type
    - Implement `get_connection()` helper using the `mariadb` connector
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 2. Implement Collector Service components
  - [x] 2.1 Create CSV writer component
    - Create `src/lightning_collector/__init__.py`, `src/lightning_collector/csv_writer.py`
    - Implement `CsvWriter` class with `__init__(file_path)`, `write(record)`, `close()`
    - Create CSV file with header row if it does not exist
    - Use column order: timestamp, event_type, distance_km, energy_normalized
    - Flush each write to disk immediately
    - Log and continue on write failure
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.2 Create database writer component with write buffer
    - Create `src/lightning_collector/db_writer.py`
    - Implement `DbWriter` class with `collections.deque(maxlen=10000)` as write buffer
    - Implement `write(record)`: insert into MariaDB or buffer if unavailable
    - Implement `flush_buffer()`: flush all buffered records in chronological order
    - Implement `reconnect()`: attempt MariaDB reconnection
    - Use parameterized queries for all inserts
    - Log warning and discard oldest record when buffer is full
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 2.3 Create Pydantic response models
    - Create `src/lightning_api/models.py`
    - Define response models: `EventResponse`, `PaginatedEventsResponse`, `PaginationMeta`, `StatsResponse`, `HealthResponse`
    - _Requirements: 6.4, 8.2, 9.1_

- [ ] 3. Complete Collector Service daemon and tests
  - [-] 3.1 Implement collector daemon main loop
    - Create `src/lightning_collector/collector.py` and `src/lightning_collector/__main__.py`
    - Register interrupt callback with AS3935 sensor via gpiozero
    - On interrupt: read interrupt source, build `EventRecord`, write to CSV then DB
    - Implement reconnection loop (every 10s for DB, every 30s for sensor)
    - Handle SIGTERM: flush CSV, attempt DB buffer flush within 5s, close connections, exit
    - Log configuration (masked credentials) and confirm sensor connectivity on startup
    - _Requirements: 1.1, 1.3, 1.4, 3.4, 5.2, 5.3, 12.2_

  - [-] 3.2 Write property tests for EventRecord construction (Property 1)
    - **Property 1: EventRecord construction correctness**
    - Test that for any interrupt source and valid sensor readings, EventRecord has correct event_type, distance_km/energy_normalized populated only for lightning, and valid UTC timestamp
    - **Validates: Requirements 1.2**

  - [-] 3.3 Write property tests for CSV serialization (Property 2)
    - **Property 2: CSV serialization round-trip**
    - Test that serializing any valid EventRecord to CSV and parsing back produces identical field values in correct column order
    - **Validates: Requirements 2.1, 2.2**

  - [x] 3.4 Write property tests for write buffer ordering (Property 3)
    - **Property 3: Write buffer preserves records in chronological order**
    - Test that flushing the buffer yields records in the same order they were enqueued
    - **Validates: Requirements 3.3, 3.5**

  - [x] 3.5 Write property tests for write buffer bounded size (Property 4)
    - **Property 4: Write buffer bounded size invariant**
    - Test that buffer never exceeds 10000 records and contains only the most recent 10000
    - **Validates: Requirements 3.6**

- [ ] 4. Checkpoint - Verify collector components
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Configuration and credential tests
  - [-] 5.1 Write property tests for configuration env var priority (Property 5)
    - **Property 5: Configuration environment variable priority**
    - Test that env vars override TOML values for any configuration key
    - **Validates: Requirements 4.1**

  - [-] 5.2 Write property tests for missing required field rejection (Property 6)
    - **Property 6: Configuration missing required field rejection**
    - Test that missing any required field raises ValidationError with descriptive message
    - **Validates: Requirements 4.3**

  - [-] 5.3 Write property tests for port validation (Property 7)
    - **Property 7: Configuration port validation**
    - Test that ports are accepted iff in range 1–65535
    - **Validates: Requirements 4.4**

  - [-] 5.4 Write property tests for I2C address validation (Property 8)
    - **Property 8: Configuration I2C address validation**
    - Test that I2C address is accepted iff it is 0x01, 0x02, or 0x03
    - **Validates: Requirements 4.5**

  - [-] 5.5 Write property tests for credential masking (Property 15)
    - **Property 15: Credential masking in log output**
    - Test that formatted log representation never contains the literal password value
    - **Validates: Requirements 12.2, 12.3**

- [ ] 6. Implement REST API (`lightning_api`)
  - [x] 6.1 Create FastAPI application factory and dependencies
    - Create `src/lightning_api/__init__.py`, `src/lightning_api/__main__.py`, `src/lightning_api/app.py`
    - Implement `create_app()` factory with CORS middleware (configurable origins)
    - Create `src/lightning_api/dependencies.py` with `get_db_connection()` dependency using `mariadb.ConnectionPool`
    - Log configuration (masked credentials) and confirm DB connectivity on startup
    - Handle SIGTERM: close DB pool, exit cleanly within 5s
    - _Requirements: 10.1, 10.4, 10.5, 12.3_

  - [x] 6.2 Implement events routes
    - Create `src/lightning_api/routes/__init__.py`, `src/lightning_api/routes/events.py`
    - Implement `GET /events` with pagination (page, page_size) and filters (start_date, end_date, event_type)
    - Validate page_size ≤ 200 (return 422 if exceeded), default page=1, page_size=50
    - Return results ordered by timestamp descending with pagination metadata (total_count, page, page_size, total_pages)
    - Implement `GET /events/latest` returning most recent event or 404 if none exist
    - Implement `GET /events/stats` returning count_by_type, count_last_24h, count_last_7d, latest_event_timestamp
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 8.1, 8.2, 8.3_

  - [x] 6.3 Implement health route
    - Create `src/lightning_api/routes/health.py`
    - Implement `GET /health` returning status, database connectivity, and uptime
    - Return HTTP 200 with "healthy" when DB is connected
    - Return HTTP 503 with "degraded" and error description when DB is unavailable
    - _Requirements: 9.1, 9.2, 9.3_

- [ ] 7. Checkpoint - Verify API core implementation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. REST API property tests
  - [~] 8.1 Write property tests for API filter correctness (Property 9)
    - **Property 9: API filter correctness**
    - Test that for any set of events and filter parameters, all returned events satisfy every active filter and no matching event is omitted
    - **Validates: Requirements 6.1, 6.2**

  - [~] 8.2 Write property tests for API ordering (Property 10)
    - **Property 10: API results ordered by timestamp descending**
    - Test that returned events have timestamps in strictly non-increasing order
    - **Validates: Requirements 6.3**

  - [~] 8.3 Write property tests for API pagination metadata (Property 11)
    - **Property 11: API pagination metadata correctness**
    - Test that total_pages = ceil(total_count / page_size) and last page item count is correct
    - **Validates: Requirements 6.4**

  - [~] 8.4 Write property tests for API page_size validation (Property 12)
    - **Property 12: API page_size validation**
    - Test that page_size > 200 returns 422 and page_size 1–200 is accepted
    - **Validates: Requirements 6.5**

  - [~] 8.5 Write property tests for API latest event (Property 13)
    - **Property 13: API latest returns most recent event**
    - Test that /events/latest returns the event with maximum timestamp
    - **Validates: Requirements 7.1**

  - [~] 8.6 Write property tests for API statistics (Property 14)
    - **Property 14: API statistics correctness**
    - Test that stats response counts match actual event counts per type and time window
    - **Validates: Requirements 8.1, 8.2**

- [ ] 9. Systemd service files
  - [~] 9.1 Create systemd unit file for Collector Service
    - Create `systemd/lightning-collector.service`
    - Configure: `ExecStart=python -m lightning_collector`, `Restart=on-failure`, `RestartSec=5`, `WantedBy=multi-user.target`
    - Include environment file reference for credentials
    - _Requirements: 5.1, 5.4_

  - [~] 9.2 Create systemd unit file for REST API
    - Create `systemd/lightning-api.service`
    - Configure: `ExecStart=python -m lightning_api`, `Restart=on-failure`, `RestartSec=5`, `WantedBy=multi-user.target`
    - Include environment file reference for credentials
    - _Requirements: 10.2, 10.3_

- [ ] 10. Update project configuration and documentation
  - [~] 10.1 Update `pyproject.toml` with new dependencies and packages
    - Add dependencies: `fastapi`, `uvicorn[standard]`, `mariadb`, `pydantic-settings`, `tomli` (for Python <3.11 fallback if needed)
    - Add new packages to `[tool.setuptools.packages.find]`
    - Add `integration` marker to pytest markers
    - _Requirements: 4.1, 10.1_

  - [~] 10.2 Update README with pipeline documentation
    - Document new services, configuration options, systemd setup, and API endpoints
    - Include example `lightning.toml` configuration file
    - _Requirements: 4.2_

- [~] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with pydantic, FastAPI, and the official `mariadb` connector as specified in the design
- All property tests use Hypothesis (already in project test dependencies)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["3.1", "5.1", "5.2", "5.3", "5.4", "5.5"] },
    { "id": 1, "tasks": ["3.2", "3.3", "3.4", "3.5"] },
    { "id": 2, "tasks": ["6.1"] },
    { "id": 3, "tasks": ["6.2", "6.3"] },
    { "id": 4, "tasks": ["8.1", "8.2", "8.3", "8.4", "8.5", "8.6"] },
    { "id": 5, "tasks": ["9.1", "9.2", "10.1", "10.2"] }
  ]
}
```
