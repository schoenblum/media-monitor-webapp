"""First-run bootstrap — seed admin account and default outlets per user."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.models.outlet import Outlet, SearchOutletLink
from app.models.search import Search, SearchTerm
from app.models.user import User, UserRole
from app.services.default_outlets import (
    DEFAULT_KEYWORDS,
    DEFAULT_LANGUAGE_PAGES,
    DEFAULT_OUTLETS,
)
from app.services.security import hash_password


logger = logging.getLogger(__name__)
settings = get_settings()


async def seed_user_defaults(db: AsyncSession, user: User) -> None:
    """Seed the default outlet library and one ready-to-run Search for a new user."""
    # Skip if the user already has outlets.
    existing = (
        await db.execute(select(Outlet.id).where(Outlet.user_id == user.id).limit(1))
    ).first()
    if existing is not None:
        return

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

    # Create a default Search using the default keywords + pages-per-language.
    search = Search(user_id=user.id, name="Kobe University (default)", is_default=True)
    db.add(search)
    await db.flush()
    for lang, term in DEFAULT_KEYWORDS.items():
        pages = DEFAULT_LANGUAGE_PAGES.get(lang, 0)
        if not pages:
            continue
        db.add(
            SearchTerm(
                search_id=search.id,
                language_code=lang,
                term=term,
                pages=pages,
                is_enabled=True,
            )
        )
    # Link every seeded outlet to the default search.
    for o in outlet_objs:
        db.add(SearchOutletLink(search_id=search.id, outlet_id=o.id))


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
            # Promote the existing user to admin.
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
