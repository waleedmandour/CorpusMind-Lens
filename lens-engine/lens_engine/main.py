"""CorpusMind Lens engine — FastAPI application factory.

Headless engine, multiple shells (§8): the same service powers the PWA, the
Tauri desktop sidecar, and self-hosted Docker deployments. Every route lives
under ``/api/v1``. Background ingestion runs on an asyncio worker pool so a
large upload never freezes request handling (the parent shipped a regression
here once — synchronous Pillow/Tesseract/numpy analysis on the request
thread froze the whole engine during batch ingest; §13 mandates against
repeating it).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, PRODUCT_NAME
from .config import get_settings
from .logging import get_logger, setup_logging
from .storage.store import Store

log = get_logger(__name__)

# Single shared store + background queue, initialised at startup.
store: Store | None = None
_ingest_queue: asyncio.Queue[str] | None = None
_workers: list[asyncio.Task] = None  # type: ignore[assignment]


def get_store() -> Store:
    global store
    if store is None:
        settings = get_settings()
        store = Store(settings.data_dir / "lens.sqlite3")
    return store


def get_ingest_queue() -> asyncio.Queue[str]:
    global _ingest_queue
    if _ingest_queue is None:
        _ingest_queue = asyncio.Queue()
    return _ingest_queue


def enqueue_ingest(image_id: str) -> None:
    get_ingest_queue().put_nowait(image_id)


async def _ingest_worker(worker_id: int, q: "asyncio.Queue[str]") -> None:
    """Background image-analysis worker (§13: async processing is mandatory).
    The queue is created fresh per app lifespan (asyncio primitives are
    loop-bound; reusing one across shells hangs silently)."""
    from .vision.pipeline import analyse_image_full

    log.info("ingest_worker_started", extra={"worker": worker_id})
    while True:
        image_id = await q.get()
        s = get_store()
        try:
            img = s.get_image(image_id)
            if img is None:
                continue
            s.update_image(image_id, status="processing")
            result = await analyse_image_full(img)
            s.update_image(
                image_id,
                status="ready",
                width=result["width"],
                height=result["height"],
                format=result["format"],
                size_bytes=result["size_bytes"],
                meta=result["meta"],
            )
            log.info("image_ready", extra={"image": image_id})
        except Exception as e:  # per-image error isolation (§9.18)
            try:
                s.update_image(image_id, status="error", error=str(e)[:500])
            except Exception:
                pass
            log.warning("image_failed", extra={"image": image_id, "error": str(e)})
        finally:
            q.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _workers, _ingest_queue
    setup_logging()
    settings = get_settings()
    settings.ensure_dirs()
    get_store()
    _ingest_queue = asyncio.Queue()          # fresh loop-bound queue per shell
    _workers = [asyncio.create_task(_ingest_worker(i, _ingest_queue)) for i in range(2)]
    log.info("engine_started", extra={"version": __version__, "product": PRODUCT_NAME})
    yield
    for t in _workers:
        t.cancel()
    _ingest_queue = None                     # drop the loop-bound queue on exit
    log.info("engine_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CorpusMind Lens Engine",
        version=__version__,
        description="Local-first visual & multimodal corpus analysis.",
        lifespan=lifespan,
    )
    # PWA (localhost dev) + desktop shell (tauri://) origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:4173", "http://127.0.0.1:4173",
            "tauri://localhost", "http://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .api.errors import CompanionUnavailableError, ConsentRequiredError

    @app.exception_handler(ConsentRequiredError)
    async def _consent_handler(_req, exc: ConsentRequiredError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(CompanionUnavailableError)
    async def _companion_handler(_req, exc: CompanionUnavailableError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

    # Routers are imported defensively so the engine boots (health + projects +
    # storage) even while later-phase modules are absent — the phase-boundary
    # commits each stay runnable (§15 build discipline).
    import importlib

    from .api import health, projects

    registered = [health.router, projects.router]
    for mod_name, attr_names in (
        ("imagesets", ["router"]),
        ("images", ["router"]),
        ("annotations", ["router"]),
        ("analysis", ["router"]),
        ("detection", ["router"]),
        ("vision_ai", ["alignment_router", "visual_grammar_router", "discourse_router"]),
        ("discourse", ["router"]),
        ("battery", ["router"]),
        ("compare", ["router"]),
        ("ocrtools", ["router"]),
        ("local_models", ["router"]),
        ("semantic", ["router"]),
        ("export", ["router"]),
        ("assistant", ["router"]),
        ("companion", ["router"]),
        ("settings_router", ["router"]),
        ("social", ["router"]),
    ):
        try:
            mod = importlib.import_module(f"lens_engine.api.{mod_name}")
            for attr in attr_names:
                registered.append(getattr(mod, attr))
        except ImportError as e:
            # The message itself carries module+error: the standard log
            # format does not render `extra` fields, and an operator tailing
            # the sidecar's log file must see *why* a router is missing.
            log.warning("router_not_registered %s: %s", mod_name, e)

    for r in registered:
        app.include_router(r, prefix="/api/v1")

    return app


app = create_app()
