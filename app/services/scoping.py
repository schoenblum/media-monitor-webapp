"""Affiliation-aware scoping helpers (Item 8).

Languages, Outlets, and run-history reads are *shared* across members of a
university. Searches, encrypted Google credentials, and webhook keys stay
**per-user** regardless of affiliation. See ``revision_brief_v2.2.md`` §8.2.

The two helpers below are deliberately tiny so callers stay readable.
``shared_read_filter`` returns the WHERE clause for *reads* of shared
resources; ``shared_write_owner`` returns the ``university_id`` to stamp onto
newly-created shared rows (which still also carry the creator's ``user_id``
for audit and ON-DELETE behaviour).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_

from app.models.user import User


def shared_read_filter(model: Any, user: User):
    """SQLAlchemy WHERE clause for reading a *shared* resource.

    Shared resources are ``UniversityLanguage``, ``Outlet``, and ``Run``. The
    rule:

    - Affiliated user → see all rows where ``university_id == user.university_id``.
    - Unaffiliated user → see rows where ``user_id == user.id``.

    For affiliated users we deliberately *do not* fall back to their
    pre-affiliation user-owned rows. That keeps each university's run history
    cleanly attributable to "runs performed under this affiliation". If a
    member wants their personal pre-affiliation data brought in, the admin
    runs the "duplicate user's run history into the new university" flow
    (§8.3).
    """
    if user.university_id is not None:
        return model.university_id == user.university_id
    return and_(model.user_id == user.id, model.university_id.is_(None))


def shared_write_owner(user: User) -> UUID | None:
    """Return the ``university_id`` value to set on a newly-created shared row.

    Returns ``None`` for unaffiliated users so the row stays user-private.
    """
    return user.university_id


def can_modify_shared_row(row: Any, user: User) -> bool:
    """True when ``user`` is allowed to mutate ``row`` of a shared resource.

    Any member of the row's university can mutate it (§8.2: last-write-wins).
    Unaffiliated users can only mutate their own user-private rows.
    """
    if user.university_id is not None:
        return row.university_id == user.university_id
    return row.user_id == user.id and row.university_id is None
