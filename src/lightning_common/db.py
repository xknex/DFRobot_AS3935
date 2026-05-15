"""Database schema and connection helpers for the Lightning Data Pipeline.

Provides functions to establish MariaDB connections and ensure the required
schema (events table with indexes) exists.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import mariadb

if TYPE_CHECKING:
    from lightning_common.config import CollectorSettings

logger = logging.getLogger(__name__)

_CREATE_EVENTS_TABLE = """\
CREATE TABLE IF NOT EXISTS events (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    event_type ENUM('lightning', 'disturber', 'noise') NOT NULL,
    distance_km INT DEFAULT NULL,
    energy_normalized FLOAT DEFAULT NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def get_connection(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> mariadb.Connection:
    """Create and return a MariaDB connection.

    Parameters
    ----------
    host : str
        Database server hostname or IP address.
    port : int
        Database server port.
    user : str
        Database username.
    password : str
        Database password.
    database : str
        Name of the database to connect to.

    Returns
    -------
    mariadb.Connection
        An active MariaDB connection.

    Raises
    ------
    mariadb.Error
        If the connection cannot be established.
    """
    try:
        conn = mariadb.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        logger.info("Connected to MariaDB at %s:%d/%s", host, port, database)
        return conn
    except mariadb.Error:
        logger.exception(
            "Failed to connect to MariaDB at %s:%d/%s", host, port, database
        )
        raise


def get_connection_from_settings(settings: CollectorSettings) -> mariadb.Connection:
    """Create a MariaDB connection using a CollectorSettings instance.

    Parameters
    ----------
    settings : CollectorSettings
        Configuration object containing database connection parameters.

    Returns
    -------
    mariadb.Connection
        An active MariaDB connection.
    """
    return get_connection(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )


def create_tables_if_not_exist(conn: mariadb.Connection) -> None:
    """Create the events table and indexes if they do not already exist.

    Executes the DDL statement to create the events table with columns:
    - id: auto-increment primary key
    - timestamp: DATETIME NOT NULL
    - event_type: ENUM('lightning', 'disturber', 'noise') NOT NULL
    - distance_km: nullable INT
    - energy_normalized: nullable FLOAT

    Indexes created:
    - idx_timestamp on the timestamp column
    - idx_event_type on the event_type column

    Parameters
    ----------
    conn : mariadb.Connection
        An active MariaDB connection.

    Raises
    ------
    mariadb.Error
        If the DDL execution fails.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_EVENTS_TABLE)
        conn.commit()
        logger.info("Ensured events table and indexes exist")
    except mariadb.Error:
        logger.exception("Failed to create events table")
        raise
    finally:
        cursor.close()
