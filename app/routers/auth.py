"""Authentication endpoints — login, change/reset/forgot password, me."""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.user import PasswordResetToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
)
from app.schemas.user import UserOut
from app.services.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
    verify_token,
)


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    token = create_access_token(user.id)
    return LoginResponse(access_token=token, force_password_change=user.force_password_change)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password incorrect")
    current.password_hash = hash_password(payload.new_password)
    current.force_password_change = False
    await db.commit()


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Always returns 202 to avoid leaking which emails are registered.

    Phase 1: prints the reset URL to the application log instead of emailing.
    """
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if user is not None and user.is_active:
        raw_token = generate_token()
        token_row = PasswordResetToken(
            user_id=user.id,
            token_hash=_sha256(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        )
        db.add(token_row)
        await db.commit()
        reset_url = f"{settings.BASE_URL.rstrip('/')}/reset-password?token={raw_token}"
        logger.info("PASSWORD RESET URL for %s — valid 1h:\n  %s", user.email, reset_url)
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> None:
    token_hash = _sha256(payload.token)
    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None or row.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    user = await db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    user.password_hash = hash_password(payload.new_password)
    user.force_password_change = False
    row.used_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current.id,
        email=current.email,
        backup_email=current.backup_email,
        role=current.role,
        is_active=current.is_active,
        created_at=current.created_at,
        last_login=current.last_login,
        force_password_change=current.force_password_change,
        has_google_key=current.google_api_key_encrypted is not None,
        has_engine_id=current.search_engine_id_encrypted is not None,
        has_webhook_key=current.webhook_api_key_hash is not None,
    )
