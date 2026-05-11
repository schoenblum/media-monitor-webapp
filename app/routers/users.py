"""User management — admin CRUD + per-user self-service (credentials, webhook key)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminCreateUserResponse,
    CredentialsStatus,
    CredentialsUpdate,
    UserCreate,
    UserOut,
    UserSelfUpdate,
    UserUpdate,
    WebhookKeyResponse,
)
from app.services.crypto import encrypt
from app.services.security import generate_token, hash_password, hash_token


router = APIRouter(prefix="/users", tags=["users"])


def _user_to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        backup_email=u.backup_email,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
        last_login=u.last_login,
        force_password_change=u.force_password_change,
        has_google_key=u.google_api_key_encrypted is not None,
        has_engine_id=u.search_engine_id_encrypted is not None,
        has_webhook_key=u.webhook_api_key_hash is not None,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[UserOut]:
    rows = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return [_user_to_out(u) for u in rows]


@router.post("", response_model=AdminCreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCreateUserResponse:
    existing = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    initial_password = payload.password or generate_token(12)
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(initial_password),
        role=payload.role,
        is_active=True,
        force_password_change=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    # Seed defaults for the new user.
    from app.bootstrap import seed_user_defaults

    await seed_user_defaults(db, user)
    await db.commit()
    return AdminCreateUserResponse(user=_user_to_out(user), initial_password=initial_password)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.is_active is not None:
        if target.id == actor.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )
        target.is_active = payload.is_active
    if payload.role is not None:
        if target.id == actor.id and payload.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot demote your own account.",
            )
        target.role = payload.role
    await db.commit()
    await db.refresh(target)
    return _user_to_out(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID, actor: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> None:
    if user_id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account."
        )
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(target)
    await db.commit()


# ---------------------------------------------------------------------------
# Self-service
# ---------------------------------------------------------------------------


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserSelfUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if payload.email is not None and payload.email.lower() != current.email:
        clash = (
            await db.execute(select(User).where(User.email == payload.email.lower()))
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        current.email = payload.email.lower()
    if payload.backup_email is not None:
        current.backup_email = payload.backup_email.lower()
    await db.commit()
    await db.refresh(current)
    return _user_to_out(current)


@router.put("/me/credentials", response_model=CredentialsStatus)
async def update_credentials(
    payload: CredentialsUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialsStatus:
    current.google_api_key_encrypted = encrypt(payload.google_api_key.strip())
    current.search_engine_id_encrypted = encrypt(payload.search_engine_id.strip())
    await db.commit()
    return CredentialsStatus(has_google_key=True, has_engine_id=True)


@router.delete("/me/credentials", response_model=CredentialsStatus)
async def delete_credentials(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CredentialsStatus:
    current.google_api_key_encrypted = None
    current.search_engine_id_encrypted = None
    await db.commit()
    return CredentialsStatus(has_google_key=False, has_engine_id=False)


@router.get("/me/credentials/status", response_model=CredentialsStatus)
async def credentials_status(current: User = Depends(get_current_user)) -> CredentialsStatus:
    return CredentialsStatus(
        has_google_key=current.google_api_key_encrypted is not None,
        has_engine_id=current.search_engine_id_encrypted is not None,
    )


@router.post("/me/webhook-key", response_model=WebhookKeyResponse)
async def generate_webhook_key(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> WebhookKeyResponse:
    raw = generate_token(24)
    current.webhook_api_key_hash = hash_token(raw)
    await db.commit()
    return WebhookKeyResponse(api_key=raw)


@router.delete("/me/webhook-key", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_webhook_key(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    current.webhook_api_key_hash = None
    await db.commit()
