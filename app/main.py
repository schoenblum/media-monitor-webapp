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

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.routers import auth, outlets, runs, searches, users, webhook


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("media-monitor")

settings = get_settings()

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401
    await bootstrap_admin()
    yield


app = FastAPI(title="Media Monitor", version="1.0.0", lifespan=lifespan)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(searches.router, prefix="/api/v1")
app.include_router(outlets.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")


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
    target = STATIC_DIR / full_path
    if full_path and target.is_file():
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
