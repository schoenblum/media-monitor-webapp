"""First-run bootstrap — seed admin account, default outlets, and university language."""
import logging
import uuid

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


async def seed_user_defaults(db: AsyncSession, user: User) -> None:
    """Seed the default outlet library, a university language entry, and a default Search."""
    existing = (
        await db.execute(select(Outlet.id).where(Outlet.user_id == user.id).limit(1))
    ).first()
    if existing is not None:
        return

    # Seed outlets
    outlet_objs: list[Outlet] = []
    for seed in DEFAULT_OUTLETS:
        outlet_objs.append(
            Outlet(
                user_id=user.id,
                name=seed["name"],
                domain=seed["domain"],
                category=seed.get("category"),
                keyword_langs=list(seed["keyword_langs"]),
                is_active=True,
            )
        )
    db.add_all(outlet_objs)
    await db.flush()

    # Seed default English university language
    en_lang = UniversityLanguage(
        user_id=user.id,
        iso_code="en",
        language_label="English",
        university_name="Kobe University",
    )
    db.add(en_lang)
    await db.flush()

    # Build outlet IDs list
    outlet_ids = [str(o.id) for o in outlet_objs]

    # Create a default Search with the new config format
    config = dict(DEFAULT_SEARCH_CONFIG)
    config["university_name"] = {
        "enabled": True,
        "language_ids": [str(en_lang.id)],
    }
    config["outlets"] = {
        "enabled": True,
        "outlet_ids": outlet_ids,
    }

    search = Search(
        user_id=user.id,
        name="Kobe University (default)",
        is_default=True,
        config=config,
    )
    db.add(search)


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
