"""Docker entrypoint for the Lightning Data Pipeline containers.

Performs first-deployment initialization:
1. Validates all required environment variables with clear error messages
2. Waits for MariaDB to become reachable (with retries)
3. Ensures the database schema exists (creates tables if missing)
4. (Collector only) Validates hardware device access (I2C, GPIO)
5. Starts the requested service (API, Collector, or db-init one-shot)

Usage:
    python docker/entrypoint.py api          # Start the REST API
    python docker/entrypoint.py collector    # Start the Lightning Collector
    python docker/entrypoint.py db-init      # Run schema init and exit
"""

from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lightning.entrypoint")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Required environment variables for database connectivity
REQUIRED_DB_VARS = {
    "LIGHTNING_DB_HOST": "MariaDB host address (e.g., 'mariadb' for Docker, '192.168.1.100' for remote)",
    "LIGHTNING_DB_PORT": "MariaDB port number (e.g., '3306')",
    "LIGHTNING_DB_USER": "MariaDB username for the lightning database",
    "LIGHTNING_DB_PASSWORD": "MariaDB password for the lightning user",
    "LIGHTNING_DB_NAME": "MariaDB database name (e.g., 'lightning_events')",
}

# Additional variables shown for the API service
OPTIONAL_API_VARS = {
    "LIGHTNING_API_HOST": ("API bind address", "0.0.0.0"),
    "LIGHTNING_API_PORT": ("API listen port", "8000"),
    "LIGHTNING_CORS_ORIGINS": ("Allowed CORS origins as JSON list", '["*"]'),
    "LIGHTNING_DB_POOL_SIZE": ("Connection pool size", "5"),
}

# Additional variables shown for the Collector service
OPTIONAL_COLLECTOR_VARS = {
    "LIGHTNING_CSV_FILE_PATH": ("CSV backup file path", "/var/lib/lightning/events.csv"),
    "LIGHTNING_SENSOR_I2C_ADDRESS": ("I2C address (1, 2, or 3 = 0x01, 0x02, 0x03)", "3"),
    "LIGHTNING_SENSOR_I2C_BUS": ("I2C bus number", "1"),
    "LIGHTNING_SENSOR_IRQ_PIN": ("BCM GPIO pin for IRQ", "4"),
    "LIGHTNING_BUFFER_MAX_SIZE": ("Max write buffer size", "10000"),
}

# Retry configuration for database connectivity
DB_MAX_RETRIES = 30
DB_RETRY_INTERVAL_S = 2

# Valid modes
VALID_MODES = ("api", "collector", "db-init")


# ---------------------------------------------------------------------------
# Step 1: Validate environment variables
# ---------------------------------------------------------------------------


def validate_environment(mode: str) -> dict[str, str]:
    """Validate that all required environment variables are set.

    Returns a dict of variable name -> value for the required DB vars.
    Exits with code 1 and clear instructions if any are missing.
    """
    logger.info("=" * 70)
    logger.info("LIGHTNING DATA PIPELINE — Container Initialization")
    logger.info("=" * 70)
    logger.info("Mode: %s", mode)
    logger.info("-" * 70)
    logger.info("Step 1/4: Validating environment variables...")

    missing: list[tuple[str, str]] = []
    values: dict[str, str] = {}

    for var, description in REQUIRED_DB_VARS.items():
        val = os.environ.get(var, "").strip()
        if not val:
            missing.append((var, description))
        else:
            values[var] = val

    if missing:
        logger.error("")
        logger.error("╔══════════════════════════════════════════════════════════════════╗")
        logger.error("║  MISSING REQUIRED ENVIRONMENT VARIABLES                         ║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        for var, description in missing:
            logger.error("║  %-20s — %s", var, description)
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        logger.error("║  HOW TO FIX:                                                    ║")
        logger.error("║  1. Copy .env.sample to .env                                    ║")
        logger.error("║  2. Fill in the missing values listed above                     ║")
        logger.error("║  3. Restart the container: docker compose up -d                 ║")
        logger.error("╚══════════════════════════════════════════════════════════════════╝")
        logger.error("")
        sys.exit(1)

    # Log resolved configuration (mask password)
    password = values["LIGHTNING_DB_PASSWORD"]
    masked = password[0] + "***" + password[-1] if len(password) > 2 else "***"

    logger.info("  LIGHTNING_DB_HOST     = %s", values["LIGHTNING_DB_HOST"])
    logger.info("  LIGHTNING_DB_PORT     = %s", values["LIGHTNING_DB_PORT"])
    logger.info("  LIGHTNING_DB_USER     = %s", values["LIGHTNING_DB_USER"])
    logger.info("  LIGHTNING_DB_PASSWORD = %s", masked)
    logger.info("  LIGHTNING_DB_NAME     = %s", values["LIGHTNING_DB_NAME"])

    if mode == "api":
        logger.info("")
        logger.info("  API settings (defaults shown if not set):")
        for var, (desc, default) in OPTIONAL_API_VARS.items():
            val = os.environ.get(var, default)
            logger.info("  %-24s = %s", var, val)

    if mode == "collector":
        logger.info("")
        logger.info("  Collector settings (defaults shown if not set):")
        for var, (desc, default) in OPTIONAL_COLLECTOR_VARS.items():
            val = os.environ.get(var, default)
            logger.info("  %-30s = %s", var, val)

    logger.info("")
    logger.info("  ✓ All required environment variables are set")
    return values


# ---------------------------------------------------------------------------
# Step 2: Validate hardware device access (Collector only)
# ---------------------------------------------------------------------------


def validate_hardware_devices() -> None:
    """Check that required hardware devices are accessible inside the container.

    Verifies:
    - /dev/i2c-{bus} exists and is readable/writable
    - /dev/gpiochip0 (or /dev/gpiomem) exists for GPIO edge detection

    Exits with code 1 and clear instructions if devices are missing.
    """
    logger.info("-" * 70)
    logger.info("Step 2/4: Validating hardware device access...")

    i2c_bus = os.environ.get("LIGHTNING_SENSOR_I2C_BUS", "1")
    i2c_device = f"/dev/i2c-{i2c_bus}"

    errors: list[tuple[str, str, list[str]]] = []

    # Check I2C device
    if not os.path.exists(i2c_device):
        errors.append((
            f"I2C device '{i2c_device}' not found",
            "The I2C bus device is not passed through to the container.",
            [
                f"Ensure 'devices: [\"{i2c_device}:{i2c_device}\"]' is in docker-compose.yml",
                "Ensure I2C is enabled on the host: sudo raspi-config → Interface Options → I2C",
                "Ensure the i2c-dev kernel module is loaded: sudo modprobe i2c-dev",
                f"Verify the device exists on the host: ls -la {i2c_device}",
            ],
        ))
    elif not os.access(i2c_device, os.R_OK | os.W_OK):
        errors.append((
            f"I2C device '{i2c_device}' exists but is not readable/writable",
            "The container user lacks permissions to access the I2C bus.",
            [
                "Add the 'i2c' group to the container: group_add: [\"i2c\"]",
                "Or run the collector container with: privileged: true",
                f"Check host permissions: ls -la {i2c_device}",
            ],
        ))

    # Check GPIO device (gpiochip0 for lgpio/gpiozero, or gpiomem for legacy)
    gpio_chip = "/dev/gpiochip0"
    gpio_mem = "/dev/gpiomem"

    has_gpio_chip = os.path.exists(gpio_chip)
    has_gpio_mem = os.path.exists(gpio_mem)

    if not has_gpio_chip and not has_gpio_mem:
        errors.append((
            "GPIO device not found (checked /dev/gpiochip0 and /dev/gpiomem)",
            "No GPIO character device is passed through to the container.",
            [
                "Add GPIO devices to docker-compose.yml:",
                f"  devices:",
                f"    - /dev/gpiochip0:/dev/gpiochip0",
                f"    - /dev/gpiomem:/dev/gpiomem",
                "Or run the collector container with: privileged: true",
                "Verify devices exist on the host: ls -la /dev/gpio*",
            ],
        ))
    else:
        # Check permissions on whichever exists
        gpio_device = gpio_chip if has_gpio_chip else gpio_mem
        if not os.access(gpio_device, os.R_OK | os.W_OK):
            errors.append((
                f"GPIO device '{gpio_device}' exists but is not readable/writable",
                "The container user lacks permissions to access GPIO.",
                [
                    "Add the 'gpio' group to the container: group_add: [\"gpio\"]",
                    "Or run the collector container with: privileged: true",
                    f"Check host permissions: ls -la {gpio_device}",
                ],
            ))

    if errors:
        logger.error("")
        logger.error("╔══════════════════════════════════════════════════════════════════╗")
        logger.error("║  HARDWARE DEVICE ACCESS FAILED                                  ║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        for problem, explanation, fixes in errors:
            logger.error("║")
            logger.error("║  ✗ %s", problem)
            logger.error("║    %s", explanation)
            logger.error("║")
            logger.error("║    HOW TO FIX:")
            for fix in fixes:
                logger.error("║      %s", fix)
        logger.error("║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        logger.error("║  IMPORTANT: The collector requires physical access to the       ║")
        logger.error("║  Raspberry Pi's I2C bus and GPIO pins. The Docker container     ║")
        logger.error("║  must run on the Pi with device passthrough configured.         ║")
        logger.error("║                                                                 ║")
        logger.error("║  Minimal docker-compose.yml for the collector:                  ║")
        logger.error("║    lightning-collector:                                          ║")
        logger.error("║      devices:                                                   ║")
        logger.error("║        - /dev/i2c-1:/dev/i2c-1                                  ║")
        logger.error("║        - /dev/gpiochip0:/dev/gpiochip0                          ║")
        logger.error("║        - /dev/gpiomem:/dev/gpiomem                              ║")
        logger.error("║      group_add: [\"i2c\", \"gpio\"]                                 ║")
        logger.error("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)

    logger.info("  ✓ I2C device: %s (accessible)", i2c_device)
    gpio_found = gpio_chip if has_gpio_chip else gpio_mem
    logger.info("  ✓ GPIO device: %s (accessible)", gpio_found)
    logger.info("")


# ---------------------------------------------------------------------------
# Step 3: Wait for MariaDB to be reachable
# ---------------------------------------------------------------------------


def wait_for_database(values: dict[str, str], step_num: int = 3) -> None:
    """Wait for MariaDB to accept connections, with retries.

    Exits with code 1 and clear instructions if the database is unreachable
    after all retries are exhausted.
    """
    logger.info("-" * 70)
    logger.info("Step %d/4: Waiting for MariaDB to be reachable...", step_num)
    logger.info(
        "  Target: %s:%s (database: %s, user: %s)",
        values["LIGHTNING_DB_HOST"],
        values["LIGHTNING_DB_PORT"],
        values["LIGHTNING_DB_NAME"],
        values["LIGHTNING_DB_USER"],
    )

    # Import mariadb here so validation errors are reported first
    try:
        import mariadb
    except ImportError:
        logger.error("")
        logger.error("╔══════════════════════════════════════════════════════════════════╗")
        logger.error("║  MISSING DEPENDENCY: mariadb Python package                     ║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        logger.error("║  The 'mariadb' package is not installed in this container.      ║")
        logger.error("║  This indicates a broken Docker image build.                    ║")
        logger.error("║                                                                 ║")
        logger.error("║  HOW TO FIX:                                                    ║")
        logger.error("║  Rebuild the image: docker compose build --no-cache             ║")
        logger.error("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)

    host = values["LIGHTNING_DB_HOST"]
    port = int(values["LIGHTNING_DB_PORT"])
    user = values["LIGHTNING_DB_USER"]
    password = values["LIGHTNING_DB_PASSWORD"]
    database = values["LIGHTNING_DB_NAME"]

    last_error: str = ""
    for attempt in range(1, DB_MAX_RETRIES + 1):
        try:
            conn = mariadb.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
            )
            conn.close()
            logger.info(
                "  ✓ MariaDB is reachable (connected on attempt %d/%d)",
                attempt,
                DB_MAX_RETRIES,
            )
            return
        except mariadb.Error as exc:
            last_error = str(exc)
            # Provide specific guidance based on error type
            if attempt == 1:
                logger.info(
                    "  Waiting for MariaDB... (attempt %d/%d)",
                    attempt,
                    DB_MAX_RETRIES,
                )
            elif attempt % 5 == 0:
                logger.warning(
                    "  Still waiting for MariaDB... (attempt %d/%d, last error: %s)",
                    attempt,
                    DB_MAX_RETRIES,
                    last_error,
                )
            time.sleep(DB_RETRY_INTERVAL_S)

    # All retries exhausted
    logger.error("")
    logger.error("╔══════════════════════════════════════════════════════════════════╗")
    logger.error("║  DATABASE CONNECTION FAILED                                     ║")
    logger.error("╠══════════════════════════════════════════════════════════════════╣")
    logger.error("║  Could not connect to MariaDB after %d attempts (%ds total).",
                 DB_MAX_RETRIES, DB_MAX_RETRIES * DB_RETRY_INTERVAL_S)
    logger.error("║")
    logger.error("║  Last error: %s", last_error)
    logger.error("║")
    logger.error("║  POSSIBLE CAUSES & FIXES:")
    logger.error("║")

    if "Access denied" in last_error:
        logger.error("║  → Wrong credentials. Check LIGHTNING_DB_USER and")
        logger.error("║    LIGHTNING_DB_PASSWORD in your .env file.")
        logger.error("║    Ensure they match MARIADB_USER / MARIADB_PASSWORD.")
    elif "Unknown database" in last_error:
        logger.error("║  → Database '%s' does not exist.", database)
        logger.error("║    Ensure LIGHTNING_DB_NAME matches MARIADB_DATABASE in .env.")
        logger.error("║    The MariaDB container creates it automatically on first start.")
    elif "Can't connect" in last_error or "Connection refused" in last_error:
        logger.error("║  → MariaDB is not running or not reachable at %s:%d.", host, port)
        logger.error("║    Check that the 'mariadb' service is running:")
        logger.error("║      docker compose ps mariadb")
        logger.error("║      docker compose logs mariadb")
        logger.error("║    If using an external DB, verify LIGHTNING_DB_HOST and")
        logger.error("║    LIGHTNING_DB_PORT are correct and the host is reachable.")
    elif "Name or service not known" in last_error or "getaddrinfo" in last_error:
        logger.error("║  → DNS resolution failed for host '%s'.", host)
        logger.error("║    If running in Docker Compose, use the service name 'mariadb'.")
        logger.error("║    If using an external DB, verify the hostname is correct.")
    else:
        logger.error("║  → Verify your .env file settings:")
        logger.error("║      LIGHTNING_DB_HOST=%s", host)
        logger.error("║      LIGHTNING_DB_PORT=%d", port)
        logger.error("║      LIGHTNING_DB_USER=%s", user)
        logger.error("║      LIGHTNING_DB_NAME=%s", database)
        logger.error("║    Ensure the MariaDB container is healthy:")
        logger.error("║      docker compose ps")

    logger.error("║")
    logger.error("╚══════════════════════════════════════════════════════════════════╝")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 4: Ensure database schema exists
# ---------------------------------------------------------------------------


def ensure_schema(values: dict[str, str], step_num: int = 4) -> None:
    """Create the events table and indexes if they don't exist.

    Exits with code 1 and clear instructions on failure.
    """
    logger.info("-" * 70)
    logger.info("Step %d/4: Ensuring database schema exists...", step_num)

    import mariadb

    host = values["LIGHTNING_DB_HOST"]
    port = int(values["LIGHTNING_DB_PORT"])
    user = values["LIGHTNING_DB_USER"]
    password = values["LIGHTNING_DB_PASSWORD"]
    database = values["LIGHTNING_DB_NAME"]

    try:
        conn = mariadb.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except mariadb.Error as exc:
        logger.error("")
        logger.error("╔══════════════════════════════════════════════════════════════════╗")
        logger.error("║  SCHEMA INIT FAILED — Cannot connect to database                ║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        logger.error("║  Error: %s", exc)
        logger.error("║  This is unexpected since the connection check passed.          ║")
        logger.error("║  The database may have gone down between checks.                ║")
        logger.error("║  Restart the stack: docker compose restart                      ║")
        logger.error("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)

    create_table_sql = """\
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

    try:
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        conn.commit()

        # Verify the table exists and report row count
        cursor.execute("SELECT COUNT(*) FROM events")
        row_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        logger.info("  ✓ Table 'events' exists (current rows: %d)", row_count)
        logger.info("")
        logger.info("=" * 70)
        logger.info("  INITIALIZATION COMPLETE — All checks passed")
        logger.info("=" * 70)
        logger.info("")

    except mariadb.Error as exc:
        logger.error("")
        logger.error("╔══════════════════════════════════════════════════════════════════╗")
        logger.error("║  SCHEMA CREATION FAILED                                         ║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        logger.error("║  Error: %s", exc)
        logger.error("║")
        logger.error("║  POSSIBLE CAUSES & FIXES:")
        logger.error("║  → The user '%s' may lack CREATE TABLE privileges.", user)
        logger.error("║    Grant permissions:")
        logger.error("║      GRANT ALL ON %s.* TO '%s'@'%%';", database, user)
        logger.error("║    Or use the MariaDB root user for initial setup.")
        logger.error("║")
        logger.error("║  → If using a managed database, ensure the database '%s'", database)
        logger.error("║    exists and the user has DDL permissions.")
        logger.error("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 5: Start the requested service
# ---------------------------------------------------------------------------


def start_api() -> None:
    """Start the Lightning REST API via uvicorn."""
    logger.info("Starting Lightning REST API service...")
    logger.info("")

    # Replace the current process with the API
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "lightning_api"],
    )


def start_collector() -> None:
    """Start the Lightning Collector daemon."""
    logger.info("Starting Lightning Collector service...")
    logger.info("")

    # Replace the current process with the collector
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "lightning_collector"],
    )


# ---------------------------------------------------------------------------
# CSV directory setup
# ---------------------------------------------------------------------------


def ensure_csv_directory() -> None:
    """Ensure the CSV output directory exists and is writable."""
    csv_path = os.environ.get("LIGHTNING_CSV_FILE_PATH", "/var/lib/lightning/events.csv")
    csv_dir = os.path.dirname(csv_path)

    if not csv_dir:
        return

    if not os.path.isdir(csv_dir):
        try:
            os.makedirs(csv_dir, exist_ok=True)
            logger.info("  ✓ Created CSV directory: %s", csv_dir)
        except OSError as exc:
            logger.error("")
            logger.error("╔══════════════════════════════════════════════════════════════════╗")
            logger.error("║  CSV DIRECTORY CREATION FAILED                                  ║")
            logger.error("╠══════════════════════════════════════════════════════════════════╣")
            logger.error("║  Cannot create directory: %s", csv_dir)
            logger.error("║  Error: %s", exc)
            logger.error("║")
            logger.error("║  HOW TO FIX:")
            logger.error("║  Add a volume mount in docker-compose.yml:")
            logger.error("║    volumes:")
            logger.error("║      - lightning_csv:/var/lib/lightning")
            logger.error("║  Or set LIGHTNING_CSV_FILE_PATH to a writable location.")
            logger.error("╚══════════════════════════════════════════════════════════════════╝")
            sys.exit(1)
    elif not os.access(csv_dir, os.W_OK):
        logger.error("")
        logger.error("╔══════════════════════════════════════════════════════════════════╗")
        logger.error("║  CSV DIRECTORY NOT WRITABLE                                     ║")
        logger.error("╠══════════════════════════════════════════════════════════════════╣")
        logger.error("║  Directory exists but is not writable: %s", csv_dir)
        logger.error("║")
        logger.error("║  HOW TO FIX:")
        logger.error("║  Ensure the volume is mounted with correct ownership:")
        logger.error("║    volumes:")
        logger.error("║      - lightning_csv:/var/lib/lightning")
        logger.error("║  Or change LIGHTNING_CSV_FILE_PATH to a writable path.")
        logger.error("╚══════════════════════════════════════════════════════════════════╝")
        sys.exit(1)
    else:
        logger.info("  ✓ CSV directory writable: %s", csv_dir)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------


def main() -> None:
    """Entrypoint dispatcher."""
    if len(sys.argv) < 2:
        print(
            "Usage: python docker/entrypoint.py <mode>\n"
            "  Modes:\n"
            "    api        — Run initialization then start the REST API\n"
            "    collector  — Run initialization then start the Collector daemon\n"
            "    db-init    — Run initialization only (schema setup) then exit\n"
        )
        sys.exit(1)

    mode = sys.argv[1].lower().strip()

    if mode not in VALID_MODES:
        logger.error(
            "Unknown mode: '%s'. Valid modes: %s",
            mode,
            ", ".join(VALID_MODES),
        )
        sys.exit(1)

    # Step 1: Validate environment
    values = validate_environment(mode)

    # Step 2: Hardware validation (collector only)
    if mode == "collector":
        validate_hardware_devices()
        ensure_csv_directory()
        # Steps 3 & 4 use adjusted numbering for collector
        wait_for_database(values, step_num=3)
        ensure_schema(values, step_num=4)
    else:
        # For api/db-init, skip hardware check (steps 2/3 become 3/4 visually)
        wait_for_database(values, step_num=2)
        ensure_schema(values, step_num=3)

    # Dispatch based on mode
    if mode == "db-init":
        logger.info("db-init complete. Exiting.")
        sys.exit(0)
    elif mode == "api":
        start_api()
    elif mode == "collector":
        start_collector()


if __name__ == "__main__":
    main()
