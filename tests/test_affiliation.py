"""University affiliation (Item 8) tests.

Covers the scoping rules from ``revision_brief_v2.2.md`` §8.2 and the
snapshot rule from §8.3.
"""
import pytest


async def _login(client, email: str, password: str):
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _bootstrap_admin_login(client):
    return await _login(client, "admin@example.com", "TestAdminPassword!")


async def _create_user(client, admin_headers, email: str, *, role: str = "user") -> dict:
    r = await client.post(
        "/api/v1/users",
        json={"email": email, "role": role},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"id": body["user"]["id"], "password": body["initial_password"], "email": email}


async def _login_and_clear_force_change(client, email: str, password: str) -> dict:
    h = await _login(client, email, password)
    # New users are forced to change password on first login; clear the flag
    # by changing it to itself + a suffix.
    new_pw = password + "!"
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": new_pw},
        headers=h,
    )
    assert r.status_code in (200, 204), r.text
    return await _login(client, email, new_pw)


# ---------------------------------------------------------------------------
# University CRUD + admin guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_university_crud_admin_only(client):
    admin = await _bootstrap_admin_login(client)
    # Admin can create
    r = await client.post(
        "/api/v1/universities", json={"name": "Kobe Uni"}, headers=admin
    )
    assert r.status_code == 201, r.text
    uni_id = r.json()["id"]
    assert r.json()["member_count"] == 0

    # Duplicate name rejected
    r = await client.post(
        "/api/v1/universities", json={"name": "Kobe Uni"}, headers=admin
    )
    assert r.status_code == 409

    # Admin can list + rename + delete
    r = await client.get("/api/v1/universities", headers=admin)
    assert r.status_code == 200
    assert any(u["id"] == uni_id for u in r.json())

    r = await client.put(
        f"/api/v1/universities/{uni_id}", json={"name": "Kobe University"}, headers=admin
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Kobe University"

    # Non-admin user gets 403
    info = await _create_user(client, admin, "u1@example.com")
    h = await _login_and_clear_force_change(client, info["email"], info["password"])
    r = await client.get("/api/v1/universities", headers=h)
    assert r.status_code == 403
    r = await client.post(
        "/api/v1/universities", json={"name": "Sneaky"}, headers=h
    )
    assert r.status_code == 403

    # Cleanup
    r = await client.delete(f"/api/v1/universities/{uni_id}", headers=admin)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Shared Languages and Outlets scoping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_affiliated_members_share_languages_and_outlets(client):
    admin = await _bootstrap_admin_login(client)
    uni = (
        await client.post(
            "/api/v1/universities", json={"name": "Kobe University"}, headers=admin
        )
    ).json()
    uni_id = uni["id"]

    # Create two users and assign both to the same university
    a = await _create_user(client, admin, "alice@example.com")
    b = await _create_user(client, admin, "bob@example.com")
    for u in (a, b):
        r = await client.patch(
            f"/api/v1/users/{u['id']}",
            json={"set_university": True, "university_id": uni_id},
            headers=admin,
        )
        assert r.status_code == 200, r.text

    a_h = await _login_and_clear_force_change(client, a["email"], a["password"])
    b_h = await _login_and_clear_force_change(client, b["email"], b["password"])

    # Alice adds a German language entry. Bob should see it.
    r = await client.post(
        "/api/v1/languages",
        json={"iso_code": "de", "university_name": "Kobe-Universität"},
        headers=a_h,
    )
    assert r.status_code == 201, r.text
    de_id = r.json()["id"]

    r = await client.get("/api/v1/languages", headers=b_h)
    iso_codes = {row["iso_code"] for row in r.json()}
    assert "de" in iso_codes, "Bob should see Alice's German entry via shared pool"

    # Bob can edit it (last-write-wins)
    r = await client.put(
        f"/api/v1/languages/{de_id}",
        json={"university_name": "Universität Kobe"},
        headers=b_h,
    )
    assert r.status_code == 200

    # Alice adds a fresh outlet (one not in the default seed library) —
    # Bob should see it via the shared pool.
    r = await client.post(
        "/api/v1/outlets",
        json={
            "name": "Fictional Daily",
            "domain": "fictional-test.example",
            "category": "Test",
            "keyword_langs": ["en"],
            "is_active": True,
        },
        headers=a_h,
    )
    assert r.status_code == 201, r.text
    r = await client.get("/api/v1/outlets", headers=b_h)
    domains = {o["domain"] for o in r.json()}
    assert "fictional-test.example" in domains


@pytest.mark.asyncio
async def test_unaffiliated_users_do_not_see_university_data(client):
    admin = await _bootstrap_admin_login(client)
    uni = (
        await client.post(
            "/api/v1/universities", json={"name": "Kobe University"}, headers=admin
        )
    ).json()
    uni_id = uni["id"]

    member = await _create_user(client, admin, "member@example.com")
    outsider = await _create_user(client, admin, "outsider@example.com")
    await client.patch(
        f"/api/v1/users/{member['id']}",
        json={"set_university": True, "university_id": uni_id},
        headers=admin,
    )

    member_h = await _login_and_clear_force_change(client, member["email"], member["password"])
    outsider_h = await _login_and_clear_force_change(
        client, outsider["email"], outsider["password"]
    )

    # Member adds a fresh outlet inside the university
    r = await client.post(
        "/api/v1/outlets",
        json={
            "name": "Secret Member Outlet",
            "domain": "secret-uni-only.example",
            "category": "Test",
            "keyword_langs": ["en"],
            "is_active": True,
        },
        headers=member_h,
    )
    assert r.status_code == 201, r.text
    r = await client.get("/api/v1/outlets", headers=outsider_h)
    domains = {o["domain"] for o in r.json()}
    assert (
        "secret-uni-only.example" not in domains
    ), "Outsider must not see university-scoped outlet"


# ---------------------------------------------------------------------------
# API credentials stay private even across affiliated members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credentials_remain_private_across_members(client):
    admin = await _bootstrap_admin_login(client)
    uni = (
        await client.post(
            "/api/v1/universities", json={"name": "Kobe University"}, headers=admin
        )
    ).json()
    a = await _create_user(client, admin, "a@example.com")
    b = await _create_user(client, admin, "b@example.com")
    for u in (a, b):
        await client.patch(
            f"/api/v1/users/{u['id']}",
            json={"set_university": True, "university_id": uni["id"]},
            headers=admin,
        )

    a_h = await _login_and_clear_force_change(client, a["email"], a["password"])
    b_h = await _login_and_clear_force_change(client, b["email"], b["password"])

    # Alice sets credentials
    r = await client.put(
        "/api/v1/users/me/credentials",
        json={"google_api_key": "alice-key", "search_engine_id": "alice-cx"},
        headers=a_h,
    )
    assert r.status_code == 200
    # Bob has none — affiliation does NOT propagate credentials
    r = await client.get("/api/v1/users/me/credentials/status", headers=b_h)
    body = r.json()
    assert body["has_google_key"] is False
    assert body["has_engine_id"] is False


# ---------------------------------------------------------------------------
# Run snapshot rule and shared run visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_snapshot_stays_with_university_on_reassignment(client):
    admin = await _bootstrap_admin_login(client)
    uni_a = (
        await client.post(
            "/api/v1/universities", json={"name": "Uni A"}, headers=admin
        )
    ).json()
    uni_b = (
        await client.post(
            "/api/v1/universities", json={"name": "Uni B"}, headers=admin
        )
    ).json()

    user = await _create_user(client, admin, "snap@example.com")
    await client.patch(
        f"/api/v1/users/{user['id']}",
        json={"set_university": True, "university_id": uni_a["id"]},
        headers=admin,
    )

    user_h = await _login_and_clear_force_change(client, user["email"], user["password"])

    # Create a search and forge a run row directly (no Google call) via the DB.
    # We use the trigger endpoint instead — it returns 400 because credentials
    # are missing, so we insert a Run via a tiny detour: use SessionLocal.
    from sqlalchemy import select
    from uuid import UUID
    import app.database as database_module
    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.search import DEFAULT_SEARCH_CONFIG, Search
    from app.models.user import User

    async with database_module.SessionLocal() as db:
        owner = (
            await db.execute(select(User).where(User.email == "snap@example.com"))
        ).scalar_one()
        search = Search(
            user_id=owner.id, name="Test", is_default=True, config=dict(DEFAULT_SEARCH_CONFIG)
        )
        db.add(search)
        await db.flush()
        run = Run(
            user_id=owner.id,
            search_id=search.id,
            university_id=owner.university_id,
            triggered_by=RunTrigger.manual,
            status=RunStatus.complete,
        )
        db.add(run)
        await db.commit()
        run_id = run.id
        original_uni_id = run.university_id

    assert str(original_uni_id) == uni_a["id"]

    # Move the user to Uni B
    r = await client.patch(
        f"/api/v1/users/{user['id']}",
        json={"set_university": True, "university_id": uni_b["id"]},
        headers=admin,
    )
    assert r.status_code == 200

    # Run's snapshotted university_id must NOT have moved
    async with database_module.SessionLocal() as db:
        from app.models.run import Run as RunModel
        re_fetched = await db.get(RunModel, run_id)
        assert str(re_fetched.university_id) == uni_a["id"]

    # The user, now in Uni B, cannot see their old run in run history
    r = await client.get("/api/v1/runs", headers=user_h)
    assert r.status_code == 200
    visible_ids = {x["id"] for x in r.json()}
    assert str(run_id) not in visible_ids


@pytest.mark.asyncio
async def test_duplicate_runs_into_new_university(client):
    """Admin offers the optional history-duplication step on reassignment (§8.3)."""
    admin = await _bootstrap_admin_login(client)
    uni = (
        await client.post(
            "/api/v1/universities", json={"name": "Uni"}, headers=admin
        )
    ).json()

    user = await _create_user(client, admin, "dup@example.com")
    # User starts unaffiliated, has a personal run with snapshot university_id=None

    from sqlalchemy import select
    import app.database as database_module
    from app.models.result import Result
    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.search import DEFAULT_SEARCH_CONFIG, Search
    from app.models.user import User

    async with database_module.SessionLocal() as db:
        owner = (
            await db.execute(select(User).where(User.email == "dup@example.com"))
        ).scalar_one()
        search = Search(
            user_id=owner.id, name="Test", is_default=True, config=dict(DEFAULT_SEARCH_CONFIG)
        )
        db.add(search)
        await db.flush()
        run = Run(
            user_id=owner.id,
            search_id=search.id,
            university_id=None,
            triggered_by=RunTrigger.manual,
            status=RunStatus.complete,
        )
        db.add(run)
        await db.flush()
        db.add(
            Result(
                run_id=run.id,
                outlet_name="Web",
                title="A",
                url="https://example.com/a",
                display_source="example.com",
                snippet="",
                date_extracted="",
                keyword_used="",
                search_lang="",
                detected_lang="en",
                detected_lang_name="English",
                is_selected=False,
            )
        )
        await db.commit()

    # Now assign user, then duplicate runs
    await client.patch(
        f"/api/v1/users/{user['id']}",
        json={"set_university": True, "university_id": uni["id"]},
        headers=admin,
    )
    r = await client.post(
        "/api/v1/universities/duplicate-runs",
        json={"user_id": user["id"], "target_university_id": uni["id"]},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["runs_copied"] == 1
    assert rep["results_copied"] == 1

    # User, now affiliated, sees the duplicated run in their (shared) history.
    user_h = await _login_and_clear_force_change(client, user["email"], user["password"])
    r = await client.get("/api/v1/runs", headers=user_h)
    visible = r.json()
    uni_runs = [x for x in visible if x["university_id"] == uni["id"]]
    assert len(uni_runs) == 1


# ---------------------------------------------------------------------------
# Unaffiliated path unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unaffiliated_user_sees_their_own_seeds(client):
    """A brand-new unaffiliated user gets the default outlet library + EN entry."""
    admin = await _bootstrap_admin_login(client)
    info = await _create_user(client, admin, "solo@example.com")
    h = await _login_and_clear_force_change(client, info["email"], info["password"])

    r = await client.get("/api/v1/outlets", headers=h)
    assert r.status_code == 200
    assert len(r.json()) > 50, "default outlet library was not seeded"

    r = await client.get("/api/v1/languages", headers=h)
    assert any(row["iso_code"] == "en" for row in r.json())


@pytest.mark.asyncio
async def test_me_includes_affiliation(client):
    admin = await _bootstrap_admin_login(client)
    uni = (
        await client.post(
            "/api/v1/universities", json={"name": "Kobe University"}, headers=admin
        )
    ).json()
    user = await _create_user(client, admin, "info@example.com")
    await client.patch(
        f"/api/v1/users/{user['id']}",
        json={"set_university": True, "university_id": uni["id"]},
        headers=admin,
    )
    h = await _login_and_clear_force_change(client, user["email"], user["password"])
    r = await client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["university_id"] == uni["id"]
    assert body["university_name"] == "Kobe University"
