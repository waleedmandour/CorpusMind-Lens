"""Sidecar entrypoint (PyInstaller target in the release pipeline).

Kept trivial: parse host/port from settings and serve the app.

Absolute imports only: the release pipeline runs this file as the PyInstaller
entry script (top-level module, no package context), where relative imports
would fail. Under ``python -m lens_engine`` both styles work; absolute is the
one style that works in both contexts.
"""
from __future__ import annotations

from lens_engine.config import get_settings
from lens_engine.logging import setup_logging
from lens_engine.main import app

import uvicorn


def main() -> None:
    setup_logging()
    s = get_settings()
    # Pass the app object directly — a "module:app" string would make uvicorn
    # import it dynamically at boot, which PyInstaller's static analysis
    # cannot see (documented sidecar pitfall).
    uvicorn.run(app, host=s.host, port=s.port, log_config=None)


if __name__ == "__main__":
    main()
