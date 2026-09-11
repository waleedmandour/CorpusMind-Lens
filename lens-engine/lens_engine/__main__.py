"""Sidecar entrypoint (PyInstaller target in the release pipeline).

Kept trivial: parse host/port from settings and serve the app.
"""
from __future__ import annotations

import uvicorn

from .config import get_settings
from .logging import setup_logging


def main() -> None:
    setup_logging()
    s = get_settings()
    uvicorn.run("lens_engine.main:app", host=s.host, port=s.port, log_config=None)


if __name__ == "__main__":
    main()
