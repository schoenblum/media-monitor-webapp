"""First-run bootstrap — seed admin account, default outlets, and university language.

Affiliation-aware seeding rules (revision_brief_v2.2.md §8.6):

1. **Unaffiliated new user** — seed a private default library + EN language
   entry + a default Search, exactly as in v2.1.
2. **New user joining an affiliation with existing shared definitions** —
   do *not* re-seed Languages or Outlets (they inherit the shared pool).
   A personal default Search is still created, pre-pointing to the shared
   language and any outlets.
3. **First user of a brand-new affiliation** — seed Languages and Outlets
   into the university's shared pool (``university_id`` set), so the
   affiliation starts populated. A personal default Search is also created.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.models.language import UniversityLanguage
from app.models.outlet import Outlet
from app.models.search import DEFAULT_SEARCH_CONFIG, Search
from app.models.user import User, UserRole
from app.services.default_outlets import DEFAULT_OUTLETS
from app.services.security import hash_password


logger = logging.getLogger(__name__)
settings = get_settings()


async def _affiliation_has_outlets(db: AsyncSession, university_id) -> bool:
    if university_id is None:
        return False
    row = (
        await db.execute(
            select(Outlet.id).where(Outlet.university_id == university_id).limit(1)
        )
    ).first()
    return row is not None


async def _affiliation_default_language(
    db: AsyncSession, university_id
) -> UniversityLanguage | None:
    if university_id is None:
        return None
    return (
        await db.execute(
            select(UniversityLanguage)
            .where(UniversityLanguage.university_id == university_id)
            .order_by(UniversityLanguage.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def seed_user_defaults(db: AsyncSession, user: User) -> None:
    """Seed defaults for ``user`` per the affiliation rules in this module's docstring."""
    # If the user already has personal data, do nothing (idempotent).
    existing_personal = (
        await db.execute(
            select(Outlet.id)
            .where(Outlet.user_id == user.id, Outlet.university_id.is_(None))
            .limit(1)
        )
    ).first()
    if existing_personal is not None:
        return

    affiliation_id = user.university_id
    affiliation_has_outlets = await _affiliation_has_outlets(db, affiliation_id)
    inherit_only = affiliation_id is not None and affiliation_has_outlets

    if inherit_only:
        # Case 2: joining an affiliation that already has shared definitions.
        # Don't re-seed; build a default Search pointing at the shared pool.
        en_lang = (
            await db.execute(
                select(UniversityLanguage).where(
                    UniversityLanguage.university_id == affiliation_id,
                    UniversityLanguage.iso_code == "en",
                )
            )
        ).scalar_one_or_none() or await _affiliation_default_language(db, affiliation_id)

        outlets = (
            await db.execute(
                select(Outlet).where(Outlet.university_id == affiliation_id)
            )
        ).scalars().all()
    else:
        # Case 1 (unaffiliated) and Case 3 (first user of a new affiliation):
        # seed Languages and Outlets, owned by user, scoped to affiliation if any.
        outlets = []
        for seed in DEFAULT_OUTLETS:
            o = Outlet(
                user_id=user.id,
                university_id=affiliation_id,
                name=seed["name"],
                domain=seed["domain"],
                category=seed.get("category"),
                keyword_langs=list(seed["keyword_langs"]),
                is_active=True,
            )
            db.add(o)
            outlets.append(o)
        await db.flush()

        en_lang = UniversityLanguage(
            user_id=user.id,
            university_id=affiliation_id,
            iso_code="en",
            university_name="Kobe University",
        )
        db.add(en_lang)
        await db.flush()

    # Personal default Search is created in every case so the user has
    # somewhere to start. The ID references point at whichever pool was used.
    config = dict(DEFAULT_SEARCH_CONFIG)
    config["university_name"] = {
        "enabled": True,
        "language_ids": [str(en_lang.id)] if en_lang is not None else [],
        "pages": 1,
    }
    config["outlets"] = {
        "enabled": True,
        "outlet_ids": [str(o.id) for o in outlets],
    }

    db.add(
        Search(
            user_id=user.id,
            name="Kobe University (default)",
            is_default=True,
            config=config,
        )
    )


async def bootstrap_admin() -> None:
    """Create the bootstrap admin if no admin user exists. Idempotent."""
    async with SessionLocal() as db:
        exists = (
            await db.execute(select(User).where(User.role == UserRole.admin).limit(1))
        ).scalar_one_or_none()
        if exists is not None:
            return

        email = settings.BOOTSTRAP_ADMIN_EMAIL.lower()
        clash = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if clash is not None:
            clash.role = UserRole.admin
            clash.is_active = True
            await db.commit()
            logger.info("Promoted existing user %s to admin", email)
            return

        admin = User(
            email=email,
            password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            role=UserRole.admin,
            is_active=True,
            force_password_change=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        await seed_user_defaults(db, admin)
        await db.commit()
        logger.warning(
            "Admin account created — email=%s — change this password immediately on first login.",
            email,
        )
