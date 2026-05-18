"""One-shot CLI to ensure DB schema exists and verify connectivity.

Usage (via module):
    python -m lightning_common.cli_db_apply

Reads DB parameters from environment variables used across the project:
    - LIGHTNING_DB_HOST
    - LIGHTNING_DB_PORT
    - LIGHTNING_DB_USER
    - LIGHTNING_DB_PASSWORD
    - LIGHTNING_DB_NAME
Prints a concise result and exits non-zero on failure.
"""
from __future__ import annotations

import os
import sys

from lightning_common.db import create_tables_if_not_exist, get_connection


def main() -> None:
    host = os.getenv("LIGHTNING_DB_HOST")
    port = int(os.getenv("LIGHTNING_DB_PORT", "3306"))
    user = os.getenv("LIGHTNING_DB_USER")
    password = os.getenv("LIGHTNING_DB_PASSWORD")
    database = os.getenv("LIGHTNING_DB_NAME")

    missing = [
        name
        for name, val in (
            ("LIGHTNING_DB_HOST", host),
            ("LIGHTNING_DB_PORT", str(port)),
            ("LIGHTNING_DB_USER", user),
            ("LIGHTNING_DB_PASSWORD", password),
            ("LIGHTNING_DB_NAME", database),
        )
        if not val
    ]
    if missing:
        print(f"DB ERROR: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    try:
        conn = get_connection(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        create_tables_if_not_exist(conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM events")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"DB OK: schema ensured; rows={count}")
    except Exception as exc:  # pragma: no cover - used in systemd one-shot
        print(f"DB ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
