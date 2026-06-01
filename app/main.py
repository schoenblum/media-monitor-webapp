"""FastAPI application entrypoint.

Mounts:
- API v1 routers under ``/api/v1/*``
- Health check at ``/api/v1/health``
- Static frontend build at ``/`` (catch-all → ``index.html`` for client routes)
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.database import SessionLocal
from app.routers import (
    auth,
    backups,
    languages,
    outlets,
    runs,
    searches,
    universities,
    users,
    webhook,
)
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.search_engine import reap_orphaned_runs


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("media-monitor")

settings = get_settings()

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401
    await bootstrap_admin()
    # Fail any run left pending/running by a previous process before the
    # scheduler can fire — a fresh worker can't have anything legitimately
    # executing yet, so those rows are orphans from a deploy restart / crash.
    await reap_orphaned_runs()
    # Start APScheduler from the lifespan rather than module import so the
    # test suite (which never enters the lifespan) doesn't spin up a real
    # scheduler. Both Uvicorn workers boot a scheduler; single-firing is
    # guarded inside the fire function with a Postgres advisory lock.
    await start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler()


app = FastAPI(
    title="Media Monitor",
    version="2.6.0",
    lifespan=lifespan,
    # Auto-generated OpenAPI docs are disabled so the app's internal structure
    # is not exposed to the public. Developers can still introspect via the
    # source on GitHub, or by running the app locally and visiting /docs there.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/api/v1/health", tags=["health"])
async def health():
    """Liveness + DB reachability. Returns 503 if the database is unreachable
    so an uptime monitor / load balancer can detect a degraded instance."""
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        logger.exception("Health check failed: database unreachable")
        return JSONResponse({"status": "degraded", "detail": "database unreachable"}, status_code=503)
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(searches.router, prefix="/api/v1")
app.include_router(outlets.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")
app.include_router(languages.router, prefix="/api/v1")
app.include_router(universities.router, prefix="/api/v1")
app.include_router(backups.router, prefix="/api/v1")


# Mount the SPA build (if present). All non-API GETs that don't match a file fall
# back to index.html so client-side routes work after a hard refresh.
INDEX_FILE = STATIC_DIR / "index.html"

if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{full_path:path}")
async def spa_catchall(full_path: str, request: Request):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    # Resolve and confirm the target stays inside STATIC_DIR before serving it,
    # so a crafted path (e.g. "../../.env") can't escape the static root and
    # read arbitrary files. Anything outside falls through to the SPA shell.
    static_root = STATIC_DIR.resolve()
    target = (STATIC_DIR / full_path).resolve()
    if full_path and target.is_file() and target.is_relative_to(static_root):
        return FileResponse(target)
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return JSONResponse(
        {
            "detail": (
                "Frontend not built yet. Run `cd frontend && npm install && npm run build` "
                "then copy `dist/*` to `app/static/`."
            )
        },
        status_code=503,
    )
