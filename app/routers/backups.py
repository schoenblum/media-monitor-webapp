"""Admin database backup — status, on-demand prepare, and download (v2.6).

See app/services/backup.py for the artifact format and rationale. All routes
require an admin. Download streams the latest encrypted backup and then prunes
every prepared file from the server (the operator keeps the copy locally).
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response

from app.config import get_settings
from app.deps import require_admin
from app.models.user import User
from app.services import backup as backup_svc


router = APIRouter(prefix="/backups", tags=["backups"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def backup_status(_: User = Depends(require_admin)) -> dict:
    """Latest prepared backup (if any) plus whether the feature is configured."""
    configured = bool(get_settings().BACKUP_PASSPHRASE)
    info = backup_svc.latest_backup_info()
    return {
        "configured": configured,
        "available": info is not None,
        "latest": info,
    }


@router.post("/prepare", status_code=status.HTTP_202_ACCEPTED)
async def prepare_now(
    background: BackgroundTasks, _: User = Depends(require_admin)
) -> dict:
    """Prepare a backup now (in addition to the weekly job)."""
    if not get_settings().BACKUP_PASSPHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BACKUP_PASSPHRASE is not configured on the server.",
        )
    background.add_task(backup_svc.prepare_backup)
    return {"detail": "Backup is being prepared. Refresh in a moment."}


@router.get("/download")
async def download_backup(_: User = Depends(require_admin)) -> Response:
    """Return the latest encrypted backup, then prune all prepared files.

    The file is read into memory first (backups are small), then every prepared
    file is removed from the server before the bytes are returned — honouring
    the "download then delete (incl. other pending)" requirement deterministically.
    """
    path = backup_svc.latest_backup_path()
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No backup is ready. Use 'Prepare now' first.",
        )
    data = path.read_bytes()
    filename = path.name
    removed = backup_svc.prune_all_prepared()
    logger.info("Backup downloaded (%s); pruned %d prepared file(s)", filename, removed)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
