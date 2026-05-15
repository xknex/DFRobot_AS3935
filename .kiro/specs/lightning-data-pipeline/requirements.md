# Requirements Document

## Introduction

The Lightning Data Pipeline provides two independent services running on a Raspberry Pi Zero 2W: a Data Collector daemon that detects lightning events via the AS3935 sensor and persists them to both a local CSV file and a remote MariaDB database, and a REST API (FastAPI) that serves lightning event data from MariaDB for browser-based dashboards. Both services are managed by systemd and designed for resource-constrained hardware with graceful handling of network failures.

## Glossary

- **Collector_Service**: The long-running daemon process that reads lightning events from the AS3935 sensor and writes records to CSV and MariaDB
- **REST_API**: The FastAPI application that serves lightning event data from MariaDB over HTTP
- **Event_Record**: A single timestamped data entry representing a lightning, disturber, or noise event detected by the sensor
- **CSV_Writer**: The component within the Collector_Service responsible for appending Event_Records to the local CSV file
- **DB_Writer**: The component within the Collector_Service responsible for inserting Event_Records into the remote MariaDB database
- **Write_Buffer**: An in-memory queue that holds Event_Records when the MariaDB connection is unavailable, for later retry
- **MariaDB**: The remote relational database server on the local network that stores Event_Records
- **Config_Loader**: The component that reads configuration from environment variables or a configuration file
- **Health_Endpoint**: The REST_API endpoint that reports service status and connectivity information

## Requirements

### Requirement 1: Sensor Event Detection

**User Story:** As a system operator, I want the Collector_Service to detect all lightning-related events from the AS3935 sensor, so that no events are missed during operation.

#### Acceptance Criteria

1. WHEN the AS3935 sensor raises an interrupt, THE Collector_Service SHALL read the interrupt source and create an Event_Record within 100ms
2. THE Event_Record SHALL contain the following fields: timestamp (ISO 8601 UTC), event_type (lightning, disturber, or noise), distance_km (for lightning events only), and energy_normalized (for lightning events only)
3. WHILE the Collector_Service is running, THE Collector_Service SHALL maintain an active interrupt callback registration with the AS3935 sensor
4. IF the AS3935 sensor becomes unresponsive, THEN THE Collector_Service SHALL log the error and attempt reconnection every 30 seconds

### Requirement 2: CSV Persistence

**User Story:** As a system operator, I want every detected event written to a local CSV file, so that I have a reliable local backup regardless of network availability.

#### Acceptance Criteria

1. WHEN an Event_Record is created, THE CSV_Writer SHALL append a single row to the configured CSV file
2. THE CSV_Writer SHALL use the column order: timestamp, event_type, distance_km, energy_normalized
3. IF the CSV file does not exist, THEN THE CSV_Writer SHALL create the file with a header row before writing the first record
4. THE CSV_Writer SHALL flush each write to disk immediately to prevent data loss on unexpected shutdown
5. IF a CSV write operation fails, THEN THE CSV_Writer SHALL log the error and continue processing subsequent events

### Requirement 3: MariaDB Persistence

**User Story:** As a system operator, I want every detected event inserted into the remote MariaDB database, so that the data is available for querying via the REST API.

#### Acceptance Criteria

1. WHEN an Event_Record is created, THE DB_Writer SHALL insert the record into the MariaDB events table
2. THE DB_Writer SHALL use parameterized queries for all database operations
3. IF the MariaDB connection is unavailable, THEN THE DB_Writer SHALL store the Event_Record in the Write_Buffer
4. WHILE the MariaDB connection is unavailable, THE DB_Writer SHALL attempt reconnection every 10 seconds
5. WHEN the MariaDB connection is restored, THE DB_Writer SHALL flush all records from the Write_Buffer in chronological order
6. THE Write_Buffer SHALL hold a maximum of 10000 records; IF the buffer is full, THEN THE DB_Writer SHALL log a warning and discard the oldest record before adding a new one

### Requirement 4: Service Configuration

**User Story:** As a system operator, I want to configure both services via environment variables or a configuration file, so that I can deploy without modifying source code.

#### Acceptance Criteria

1. THE Config_Loader SHALL read configuration from environment variables with an optional fallback to a TOML configuration file
2. THE Config_Loader SHALL support the following settings: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, CSV_FILE_PATH, SENSOR_I2C_ADDRESS, SENSOR_I2C_BUS, SENSOR_IRQ_PIN, API_HOST, API_PORT
3. IF a required configuration value is missing, THEN THE Config_Loader SHALL raise a descriptive error at startup and prevent the service from starting
4. THE Config_Loader SHALL validate that DB_PORT and API_PORT are valid port numbers in the range 1 to 65535
5. THE Config_Loader SHALL validate that SENSOR_I2C_ADDRESS is one of 0x01, 0x02, or 0x03

### Requirement 5: Collector Service Lifecycle

**User Story:** As a system operator, I want the Collector_Service to run as a systemd service with automatic restart, so that lightning detection continues reliably without manual intervention.

#### Acceptance Criteria

1. THE Collector_Service SHALL provide a systemd unit file configured with Restart=on-failure and RestartSec=5
2. WHEN the Collector_Service receives a SIGTERM signal, THE Collector_Service SHALL flush pending CSV writes, attempt to flush the Write_Buffer to MariaDB within 5 seconds, close all connections, and exit cleanly
3. WHEN the Collector_Service starts, THE Collector_Service SHALL log its configuration (excluding credentials) and confirm sensor connectivity
4. THE Collector_Service SHALL provide a systemd unit file configured with WantedBy=multi-user.target for automatic start on boot

### Requirement 6: REST API Event Listing

**User Story:** As a dashboard developer, I want to query lightning events with pagination and filtering, so that I can display event history efficiently.

#### Acceptance Criteria

1. WHEN a GET request is made to /events, THE REST_API SHALL return a paginated list of Event_Records from MariaDB
2. THE REST_API SHALL support query parameters: page (default 1), page_size (default 50, maximum 200), start_date (ISO 8601), end_date (ISO 8601), and event_type (lightning, disturber, or noise)
3. THE REST_API SHALL return results ordered by timestamp descending
4. THE REST_API SHALL include pagination metadata in the response: total_count, page, page_size, and total_pages
5. IF page_size exceeds 200, THEN THE REST_API SHALL return HTTP 422 with a descriptive error message

### Requirement 7: REST API Latest Event

**User Story:** As a dashboard developer, I want to retrieve the most recent event quickly, so that I can display real-time status.

#### Acceptance Criteria

1. WHEN a GET request is made to /events/latest, THE REST_API SHALL return the most recent Event_Record from MariaDB
2. IF no events exist in the database, THEN THE REST_API SHALL return HTTP 404 with a descriptive message

### Requirement 8: REST API Statistics

**User Story:** As a dashboard developer, I want summary statistics about lightning events, so that I can display aggregated information on the dashboard.

#### Acceptance Criteria

1. WHEN a GET request is made to /events/stats, THE REST_API SHALL return summary statistics from MariaDB
2. THE REST_API SHALL include in the statistics response: count_by_type (lightning, disturber, noise), count_last_24h, count_last_7d, and latest_event_timestamp
3. IF no events exist in the database, THEN THE REST_API SHALL return zero counts and a null latest_event_timestamp

### Requirement 9: REST API Health Check

**User Story:** As a system operator, I want a health check endpoint, so that I can monitor the API service status and database connectivity.

#### Acceptance Criteria

1. WHEN a GET request is made to /health, THE REST_API SHALL return the service status, database connectivity status, and service uptime
2. WHILE the MariaDB connection is healthy, THE Health_Endpoint SHALL return HTTP 200 with status "healthy"
3. WHILE the MariaDB connection is unavailable, THE Health_Endpoint SHALL return HTTP 503 with status "degraded" and include the error description

### Requirement 10: REST API Service Configuration

**User Story:** As a system operator, I want the REST API to run as a systemd service with CORS enabled, so that browser-based dashboards can access the data reliably.

#### Acceptance Criteria

1. THE REST_API SHALL enable CORS with configurable allowed origins (default: all origins)
2. THE REST_API SHALL provide a systemd unit file configured with Restart=on-failure and RestartSec=5
3. THE REST_API SHALL provide a systemd unit file configured with WantedBy=multi-user.target for automatic start on boot
4. WHEN the REST_API starts, THE REST_API SHALL log its configuration (excluding credentials) and confirm database connectivity
5. WHEN the REST_API receives a SIGTERM signal, THE REST_API SHALL close database connections and exit cleanly within 5 seconds

### Requirement 11: Database Schema

**User Story:** As a system operator, I want a well-defined database schema, so that both the Collector_Service and REST_API interact with a consistent data structure.

#### Acceptance Criteria

1. THE MariaDB events table SHALL contain columns: id (auto-increment primary key), timestamp (DATETIME with UTC timezone), event_type (ENUM of lightning, disturber, noise), distance_km (nullable INTEGER), and energy_normalized (nullable FLOAT)
2. THE MariaDB events table SHALL have an index on the timestamp column for efficient range queries
3. THE MariaDB events table SHALL have an index on the event_type column for efficient filtering
4. THE Collector_Service SHALL create the events table and indexes on first startup if they do not exist

### Requirement 12: Security and Credentials

**User Story:** As a system operator, I want credentials managed securely, so that database access is protected.

#### Acceptance Criteria

1. THE Config_Loader SHALL read database credentials exclusively from environment variables or a configuration file with restricted file permissions (0600)
2. THE Collector_Service SHALL log configuration values at startup but SHALL mask credential values in all log output
3. THE REST_API SHALL log configuration values at startup but SHALL mask credential values in all log output
