"""Structured logging for the Lens engine (stdout + optional file).

Kept deliberately small: the desktop shell redirects sidecar stdout to a log
file itself (log-to-file, NOT piped — piped stdout can hang on buffer-size
limits), so the engine only needs to emit well-formed lines.
"""
from __future__ import annotations

import logging
import os
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_CONFIGURED = False


def setup_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = (level or os.environ.get("LENS_LOG_LEVEL", "INFO")).upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(lvl)
    # Quieten the noisier third-party loggers in local-first operation.
    for noisy in ("httpx", "httpcore", "uvicorn.access", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
