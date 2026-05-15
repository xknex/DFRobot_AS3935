"""Entry point for the Lightning REST API service.

Usage: python -m lightning_api
"""

from __future__ import annotations

import logging

import uvicorn

from lightning_common.config import ApiSettings
from lightning_api.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    """Load settings and start the uvicorn server."""
    settings = ApiSettings()
    app = create_app(settings)

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
