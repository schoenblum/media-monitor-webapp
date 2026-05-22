"""User management — admin CRUD + per-user self-service (credentials, webhook key)."""
import copy
import uuid
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models.language import UniversityLanguage
from app.models.outlet import Outlet
from app.models.result import Result
from app.models.run import Run
from app.models.search import Search
from app.models.university import University
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminCreateUserResponse,
    CredentialsStatus,
    CredentialsUpdate,
    DuplicateUserRequest,
    UserCreate,
    UserOut,
    UserSelfUpdate,
    UserUpdate,
    WebhookKeyResponse,
)
from app.services.crypto import encrypt
from app.services.email import send_welcome_email
from app.services.security import generate_token, hash_password, hash_token


router = APIRouter(prefix="/users", tags=["users"])
settings = get_settings()


def _smtp_configured() -> bool:
    """Cheap synchronous check — no network I/O."""
    s = get_settings()
    return bool(s.SMTP_HOST and s.SMTP_FROM)


def _user_to_out(u: User, *, university_name: str | None = None) -> UserOut:
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
        university_id=u.university_id,
        university_name=university_name,
    )


async def _name_for(
    db: AsyncSession, university_id: UUID | None
) -> str | None:
    if university_id is None:
        return None
    uni = await db.get(University, university_id)
    return uni.name if uni else None


@router.get("", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[UserOut]:
    rows = (
        await db.execute(
            select(User, University.name)
            .outerjoin(University, University.id == User.university_id)
            .order_by(User.created_at.desc())
        )
    ).all()
    return [_user_to_out(u, university_name=name) for u, name in rows]


@router.post("", response_model=AdminCreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    background: BackgroundTasks,
    actor: User = Depends(require_admin),
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

    from app.bootstrap import seed_user_defaults
    await seed_user_defaults(db, user)
    await db.commit()

    # Hand the email send off to a background task so SMTP latency or timeouts
    # never block the HTTP response. `email_sent` here reflects whether the
    # delivery was *scheduled* (i.e. SMTP is configured) — the admin can still
    # see the initial password in the response and share it manually.
    email_will_send = _smtp_configured()
    if email_will_send:
        background.add_task(
            send_welcome_email,
            to=user.email,
            initial_password=initial_password,
            app_url=settings.BASE_URL,
        )

    return AdminCreateUserResponse(
        user=_user_to_out(user),
        initial_password=initial_password,
        email_sent=email_will_send,
    )


@router.post("/{user_id}/duplicate", response_model=AdminCreateUserResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_user(
    user_id: UUID,
    payload: DuplicateUserRequest,
    background: BackgroundTasks,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCreateUserResponse:
    """Clone a user's searches, university languages, and run history into a new account."""
    source = await db.get(User, user_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source user not found")

    new_email = payload.email.lower()
    clash = (
        await db.execute(select(User).where(User.email == new_email))
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    initial_password = generate_token(12)
    new_user = User(
        email=new_email,
        password_hash=hash_password(initial_password),
        role=source.role,
        is_active=True,
        force_password_change=True,
        # Google creds intentionally left blank
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # --- Copy university languages ---
    src_langs = (
        await db.execute(
            select(UniversityLanguage).where(UniversityLanguage.user_id == source.id)
        )
    ).scalars().all()

    lang_id_map: dict[str, str] = {}
    for lang in src_langs:
        new_lang = UniversityLanguage(
            user_id=new_user.id,
            iso_code=lang.iso_code,
            university_name=lang.university_name,
        )
        db.add(new_lang)
        await db.flush()
        lang_id_map[str(lang.id)] = str(new_lang.id)

    # --- Copy outlets ---
    src_outlets = (
        await db.execute(select(Outlet).where(Outlet.user_id == source.id))
    ).scalars().all()

    outlet_id_map: dict[str, str] = {}
    for o in src_outlets:
        new_outlet = Outlet(
            user_id=new_user.id,
            name=o.name,
            domain=o.domain,
            category=o.category,
            keyword_langs=list(o.keyword_langs or []),
            is_active=o.is_active,
        )
        db.add(new_outlet)
        await db.flush()
        outlet_id_map[str(o.id)] = str(new_outlet.id)

    # --- Copy searches (with config remapping) ---
    src_searches = (
        await db.execute(select(Search).where(Search.user_id == source.id))
    ).scalars().all()

    search_id_map: dict[str, str] = {}
    for s in src_searches:
        new_config = _remap_config(s.config or {}, lang_id_map, outlet_id_map)
        new_search = Search(
            user_id=new_user.id,
            name=s.name,
            is_default=s.is_default,
            config=new_config,
        )
        db.add(new_search)
        await db.flush()
        search_id_map[str(s.id)] = str(new_search.id)

    # --- Copy runs + results ---
    src_runs = (
        await db.execute(select(Run).where(Run.user_id == source.id))
    ).scalars().all()

    for run in src_runs:
        new_search_id_str = search_id_map.get(str(run.search_id))
        if new_search_id_str is None:
            continue
        new_run = Run(
            user_id=new_user.id,
            search_id=uuid.UUID(new_search_id_str),
            triggered_by=run.triggered_by,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            api_calls_used=run.api_calls_used,
            error_message=run.error_message,
        )
        db.add(new_run)
        await db.flush()

        src_results = (
            await db.execute(select(Result).where(Result.run_id == run.id))
        ).scalars().all()
        for r in src_results:
            db.add(
                Result(
                    run_id=new_run.id,
                    outlet_name=r.outlet_name,
                    title=r.title,
                    url=r.url,
                    display_source=r.display_source,
                    snippet=r.snippet,
                    date_extracted=r.date_extracted,
                    keyword_used=r.keyword_used,
                    search_lang=r.search_lang,
                    detected_lang=r.detected_lang,
                    detected_lang_name=r.detected_lang_name,
                    is_selected=r.is_selected,
                )
            )

    await db.commit()

    email_will_send = _smtp_configured()
    if email_will_send:
        background.add_task(
            send_welcome_email,
            to=new_user.email,
            initial_password=initial_password,
            app_url=settings.BASE_URL,
        )

    return AdminCreateUserResponse(
        user=_user_to_out(new_user),
        initial_password=initial_password,
        email_sent=email_will_send,
    )


def _remap_config(config: dict, lang_id_map: dict, outlet_id_map: dict) -> dict:
    """Return a copy of config with all referenced IDs updated to new ones."""
    new_config = copy.deepcopy(config)
    uni = new_config.get("university_name", {})
    if isinstance(uni.get("language_ids"), list):
        uni["language_ids"] = [
            lang_id_map.get(lid, lid) for lid in uni["language_ids"]
        ]
    outlets = new_config.get("outlets", {})
    if isinstance(outlets.get("outlet_ids"), list):
        outlets["outlet_ids"] = [
            outlet_id_map.get(oid, oid) for oid in outlets["outlet_ids"]
        ]
    return new_config


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
    # Affiliation assign / move / unaffiliate. We require an explicit
    # ``set_university`` flag so the caller can disambiguate "clear" (null)
    # from "no change" (field absent). Per §8.3 existing runs do NOT migrate
    # — they keep their snapshotted university_id.
    if payload.set_university:
        if payload.university_id is not None:
            uni = await db.get(University, payload.university_id)
            if uni is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target university not found",
                )
        old_university_id = target.university_id
        target.university_id = payload.university_id
        await db.flush()
        # On assignment *into* a university, adopt the user's existing
        # personal Languages and Outlets into the new shared pool — but
        # only where they do not conflict with rows already shared by the
        # university. Conflicting personals stay user-private (and become
        # invisible to the user while affiliated, which is fine; they can
        # still be retrieved by un-affiliating).
        if (
            payload.university_id is not None
            and old_university_id != payload.university_id
        ):
            await _adopt_personal_into_university(db, target.id, payload.university_id)
    await db.commit()
    await db.refresh(target)
    name = await _name_for(db, target.university_id)
    return _user_to_out(target, university_name=name)


async def _adopt_personal_into_university(
    db: AsyncSession, user_id: UUID, university_id: UUID
) -> None:
    """Adopt non-conflicting personal Languages/Outlets into the target university.

    Implements the assignment-time data carry-over described in
    ``revision_brief_v2.2.md`` §8.6 ("first user of a new university") in a
    way that also handles the "joining an existing university" case
    gracefully: rows whose iso_code or domain already exists in the shared
    pool are left as user-private orphans rather than failing the
    assignment with a uniqueness violation.
    """
    # Languages
    personal_langs = (
        await db.execute(
            select(UniversityLanguage).where(
                UniversityLanguage.user_id == user_id,
                UniversityLanguage.university_id.is_(None),
            )
        )
    ).scalars().all()
    if personal_langs:
        existing_isos = {
            iso
            for (iso,) in (
                await db.execute(
                    select(UniversityLanguage.iso_code).where(
                        UniversityLanguage.university_id == university_id
                    )
                )
            ).all()
        }
        for row in personal_langs:
            if row.iso_code not in existing_isos:
                row.university_id = university_id
                existing_isos.add(row.iso_code)

    # Outlets
    personal_outlets = (
        await db.execute(
            select(Outlet).where(
                Outlet.user_id == user_id, Outlet.university_id.is_(None)
            )
        )
    ).scalars().all()
    if personal_outlets:
        existing_domains = {
            d
            for (d,) in (
                await db.execute(
                    select(Outlet.domain).where(Outlet.university_id == university_id)
                )
            ).all()
        }
        for row in personal_outlets:
            if row.domain not in existing_domains:
                row.university_id = university_id
                existing_domains.add(row.domain)

    await db.flush()


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
