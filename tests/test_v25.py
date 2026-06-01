"""v2.5 tests — run reaper + cancel, webhook key redesign, notifications,
email export, MultiFernet rotation, path-traversal guard, and any-member
run deletion under affiliation."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_affiliation.py)
# ---------------------------------------------------------------------------


async def _login(client, email="admin@example.com", password="TestAdminPassword!"):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _create_user(client, admin_headers, email, *, role="user"):
    r = await client.post(
        "/api/v1/users", json={"email": email, "role": role}, headers=admin_headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"id": body["user"]["id"], "password": body["initial_password"], "email": email}


async def _login_clear_force(client, email, password):
    h = await _login(client, email, password)
    new_pw = password + "!"
    await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": new_pw},
        headers=h,
    )
    return await _login(client, email, new_pw)


async def _admin_user(db):
    from app.models.user import User

    return (await db.execute(select(User).where(User.email == "admin@example.com"))).scalar_one()


async def _make_run(db, user, *, status, started_at=None, triggered_by=None, results=0, selected=False):
    from app.models.result import Result
    from app.models.run import Run, RunTrigger
    from app.models.search import DEFAULT_SEARCH_CONFIG, Search

    search = Search(user_id=user.id, name="T", is_default=False, config=dict(DEFAULT_SEARCH_CONFIG))
    db.add(search)
    await db.flush()
    run = Run(
        user_id=user.id,
        search_id=search.id,
        university_id=user.university_id,
        triggered_by=triggered_by or RunTrigger.manual,
        status=status,
        started_at=started_at or datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()
    for i in range(results):
        db.add(
            Result(
                run_id=run.id, outlet_name="", title=f"t{i}", url=f"https://x.test/{uuid4()}",
                display_source="", snippet="", date_extracted="", keyword_used="",
                search_lang="", detected_lang="en", detected_lang_name="English",
                is_selected=selected,
            )
        )
    await db.commit()
    return run, search


# ---------------------------------------------------------------------------
# Health check now touches the DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_ok(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Run reaper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reap_orphaned_runs_fails_all_in_progress(client, session_factory):
    from app.models.run import RunStatus
    from app.services.search_engine import reap_orphaned_runs

    async with session_factory() as db:
        admin = await _admin_user(db)
        pend, _ = await _make_run(db, admin, status=RunStatus.pending)
        runn, _ = await _make_run(db, admin, status=RunStatus.running)
        done, _ = await _make_run(db, admin, status=RunStatus.complete)

    n = await reap_orphaned_runs()
    assert n == 2

    async with session_factory() as db:
        from app.models.run import Run
        assert (await db.get(Run, pend.id)).status == RunStatus.failed
        assert (await db.get(Run, runn.id)).status == RunStatus.failed
        # A completed run is untouched.
        assert (await db.get(Run, done.id)).status == RunStatus.complete


@pytest.mark.asyncio
async def test_reap_stuck_runs_only_fails_old(client, session_factory):
    from app.models.run import Run, RunStatus
    from app.services.search_engine import STUCK_RUN_THRESHOLD_MINUTES, reap_stuck_runs

    now = datetime.now(timezone.utc)
    async with session_factory() as db:
        admin = await _admin_user(db)
        old, _ = await _make_run(
            db, admin, status=RunStatus.running,
            started_at=now - timedelta(minutes=STUCK_RUN_THRESHOLD_MINUTES + 5),
        )
        fresh, _ = await _make_run(
            db, admin, status=RunStatus.running, started_at=now - timedelta(minutes=1),
        )

    n = await reap_stuck_runs()
    assert n == 1
    async with session_factory() as db:
        assert (await db.get(Run, old.id)).status == RunStatus.failed
        assert (await db.get(Run, fresh.id)).status == RunStatus.running


# ---------------------------------------------------------------------------
# Cancel endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_run(client, session_factory):
    from app.models.run import RunStatus

    h = await _login(client)
    async with session_factory() as db:
        admin = await _admin_user(db)
        run, _ = await _make_run(db, admin, status=RunStatus.running)

    r = await client.post(f"/api/v1/runs/{run.id}/cancel", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "failed"
    assert "cancelled" in r.json()["error_message"].lower()

    # Cancelling a finished run is rejected.
    async with session_factory() as db:
        admin = await _admin_user(db)
        done, _ = await _make_run(db, admin, status=RunStatus.complete)
    r = await client.post(f"/api/v1/runs/{done.id}/cancel", headers=h)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Webhook key redesign
# ---------------------------------------------------------------------------


def test_webhook_key_helpers():
    from app.services.security import (
        generate_webhook_key,
        split_webhook_key,
        verify_webhook_secret,
    )

    full, key_id, secret_hash = generate_webhook_key()
    assert full == f"{key_id}.{full.split('.', 1)[1]}"
    parsed = split_webhook_key(full)
    assert parsed is not None and parsed[0] == key_id
    assert verify_webhook_secret(parsed[1], secret_hash)
    assert not verify_webhook_secret("wrong", secret_hash)
    assert split_webhook_key("nodot") is None
    assert split_webhook_key("") is None


@pytest.mark.asyncio
async def test_webhook_auth_uses_new_key_format(client):
    h = await _login(client)
    key = (await client.post("/api/v1/users/me/webhook-key", headers=h)).json()["api_key"]
    assert "." in key

    search_id = (await client.get("/api/v1/searches", headers=h)).json()[0]["id"]

    # Valid key passes auth → blocked only by the missing-credentials guard (400).
    r = await client.post(
        "/api/v1/webhook/run", json={"search_id": search_id}, headers={"X-API-Key": key}
    )
    assert r.status_code == 400, r.text
    assert "credential" in r.json()["detail"].lower()

    # Wrong secret, valid-looking format → 401.
    key_id = key.split(".", 1)[0]
    r = await client.post(
        "/api/v1/webhook/run",
        json={"search_id": search_id},
        headers={"X-API-Key": f"{key_id}.totally-wrong-secret"},
    )
    assert r.status_code == 401

    # Malformed (no key_id) → 401.
    r = await client.post(
        "/api/v1/webhook/run", json={"search_id": search_id}, headers={"X-API-Key": "garbage"}
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_config_round_trips(client):
    h = await _login(client)
    search = (await client.get("/api/v1/searches", headers=h)).json()[0]
    cfg = search["config"]
    cfg["notify"] = {"enabled": True, "email": "alerts@example.com"}
    r = await client.put(
        f"/api/v1/searches/{search['id']}",
        json={"name": search["name"], "config": cfg},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["config"]["notify"] == {"enabled": True, "email": "alerts@example.com"}


@pytest.mark.asyncio
async def test_maybe_notify_fires_for_scheduled_not_manual(client, session_factory, monkeypatch):
    import app.services.email as email_mod
    from app.models.run import RunStatus, RunTrigger
    from app.services.search_engine import _maybe_notify

    sent: list[dict] = []

    async def fake_send(*, to, search_name, run_id, hit_count, samples):
        sent.append({"to": to, "count": hit_count})
        return True

    monkeypatch.setattr(email_mod, "send_run_notification", fake_send)

    async with session_factory() as db:
        admin = await _admin_user(db)
        # Scheduled run with notify enabled + 2 results → fires.
        run, search = await _make_run(
            db, admin, status=RunStatus.complete, triggered_by=RunTrigger.scheduled, results=2
        )
        search.config = {**search.config, "notify": {"enabled": True, "email": ""}}
        await db.commit()
        await _maybe_notify(db, run, search, admin)
    assert len(sent) == 1
    assert sent[0]["count"] == 2
    assert sent[0]["to"] == admin.email  # blank → owner login email

    # Manual run never notifies, even with results + notify enabled.
    sent.clear()
    async with session_factory() as db:
        admin = await _admin_user(db)
        run, search = await _make_run(
            db, admin, status=RunStatus.complete, triggered_by=RunTrigger.manual, results=2
        )
        search.config = {**search.config, "notify": {"enabled": True, "email": "x@y.test"}}
        await db.commit()
        await _maybe_notify(db, run, search, admin)
    assert sent == []


# ---------------------------------------------------------------------------
# Email export of selected hits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_export_sends_when_selected(client, session_factory, monkeypatch):
    import app.services.email as email_mod
    from app.models.run import RunStatus

    captured: list[dict] = []

    async def fake_send_export(to, csv_bytes, filename, count):
        captured.append({"to": to, "count": count, "bytes": csv_bytes})
        return True

    monkeypatch.setattr(email_mod, "send_export_email", fake_send_export)

    h = await _login(client)
    async with session_factory() as db:
        admin = await _admin_user(db)
        run, _ = await _make_run(db, admin, status=RunStatus.complete, results=2, selected=True)

    r = await client.post(
        "/api/v1/runs/export-email",
        json={"run_ids": [str(run.id)], "email": "dest@example.com"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["sent"] is True
    assert captured and captured[0]["to"] == "dest@example.com"
    assert captured[0]["count"] == 2


@pytest.mark.asyncio
async def test_email_export_rejects_when_nothing_selected(client, session_factory):
    from app.models.run import RunStatus

    h = await _login(client)
    async with session_factory() as db:
        admin = await _admin_user(db)
        run, _ = await _make_run(db, admin, status=RunStatus.complete, results=2, selected=False)

    r = await client.post(
        "/api/v1/runs/export-email",
        json={"run_ids": [str(run.id)], "email": "dest@example.com"},
        headers=h,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# MultiFernet
# ---------------------------------------------------------------------------


def test_crypto_round_trip_and_rotate():
    from app.services.crypto import decrypt, encrypt, rotate_token

    token = encrypt("super-secret-google-key")
    assert decrypt(token) == "super-secret-google-key"
    rotated = rotate_token(token)
    assert decrypt(rotated) == "super-secret-google-key"


def test_multifernet_reads_old_key():
    """A token encrypted under an older key still decrypts when that key is
    listed in FERNET_KEYS alongside a new primary."""
    from cryptography.fernet import Fernet, MultiFernet

    old = Fernet.generate_key()
    new = Fernet.generate_key()
    old_token = Fernet(old).encrypt(b"creds")
    # Primary = new, fallback = old (the order crypto._build_fernet produces).
    mf = MultiFernet([Fernet(new), Fernet(old)])
    assert mf.decrypt(old_token) == b"creds"


# ---------------------------------------------------------------------------
# SPA catch-all path traversal guard
# ---------------------------------------------------------------------------


def test_static_root_containment_predicate():
    """The guard used in spa_catchall must reject paths that escape STATIC_DIR."""
    from app.main import STATIC_DIR

    root = STATIC_DIR.resolve()
    escaped = (STATIC_DIR / "../../etc/passwd").resolve()
    assert not escaped.is_relative_to(root)
    inside = (STATIC_DIR / "assets/app.js").resolve()
    assert inside.is_relative_to(root)


@pytest.mark.asyncio
async def test_traversal_request_does_not_leak_files(client):
    r = await client.get("/..%2f..%2f..%2fetc%2fpasswd")
    # Never serves the file: either the SPA shell / 503 (no build in tests),
    # but certainly not passwd contents.
    assert "root:" not in r.text


# ---------------------------------------------------------------------------
# Any university member can delete a run (v2.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_any_member_can_delete_run(client, session_factory):
    from app.models.run import Run, RunStatus
    from app.models.user import User

    admin = await _login(client)
    uni = (
        await client.post("/api/v1/universities", json={"name": "Kobe"}, headers=admin)
    ).json()
    alice = await _create_user(client, admin, "alice@example.com")
    bob = await _create_user(client, admin, "bob@example.com")
    for u in (alice, bob):
        await client.patch(
            f"/api/v1/users/{u['id']}",
            json={"set_university": True, "university_id": uni["id"]},
            headers=admin,
        )

    # Forge a run owned by Alice under the university.
    async with session_factory() as db:
        alice_u = (
            await db.execute(select(User).where(User.email == "alice@example.com"))
        ).scalar_one()
        run, _ = await _make_run(db, alice_u, status=RunStatus.complete)

    # Bob (same university) can delete Alice's run.
    bob_h = await _login_clear_force(client, bob["email"], bob["password"])
    r = await client.delete(f"/api/v1/runs/{run.id}", headers=bob_h)
    assert r.status_code == 204, r.text
    async with session_factory() as db:
        assert await db.get(Run, run.id) is None


# ---------------------------------------------------------------------------
# Admin database backup (v2.6)
# ---------------------------------------------------------------------------


def test_backup_encrypt_decrypt_roundtrip():
    from app.services.backup import decrypt_bytes, encrypt_bytes

    blob = encrypt_bytes(b"PGDMP-fake-dump-bytes", "s3cret-passphrase")
    assert blob[:6] == b"MMBK1\n"
    assert decrypt_bytes(blob, "s3cret-passphrase") == b"PGDMP-fake-dump-bytes"
    with pytest.raises(Exception):
        decrypt_bytes(blob, "wrong-passphrase")


@pytest.mark.asyncio
async def test_backup_status_requires_admin(client):
    admin = await _login(client)
    info = await _create_user(client, admin, "plainuser@example.com")
    h = await _login_clear_force(client, info["email"], info["password"])
    assert (await client.get("/api/v1/backups/status", headers=h)).status_code == 403
    assert (await client.post("/api/v1/backups/prepare", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_backup_status_download_and_prune(client, tmp_path, monkeypatch):
    from app.config import get_settings
    from app.services.backup import encrypt_bytes

    s = get_settings()
    monkeypatch.setattr(s, "BACKUP_DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(s, "BACKUP_PASSPHRASE", "test-pass")
    (tmp_path / "media_monitor_20260101T000000Z.dump.enc").write_bytes(
        encrypt_bytes(b"the-dump", "test-pass")
    )

    h = await _login(client)
    body = (await client.get("/api/v1/backups/status", headers=h)).json()
    assert body["configured"] is True and body["available"] is True
    assert body["latest"]["filename"].endswith(".dump.enc")

    r = await client.get("/api/v1/backups/download", headers=h)
    assert r.status_code == 200
    assert r.content[:6] == b"MMBK1\n"

    # Download prunes the prepared file(s).
    assert (await client.get("/api/v1/backups/status", headers=h)).json()["available"] is False
    assert (await client.get("/api/v1/backups/download", headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_backup_prepare_requires_passphrase(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "BACKUP_PASSPHRASE", None)
    h = await _login(client)
    assert (await client.post("/api/v1/backups/prepare", headers=h)).status_code == 400


@pytest.mark.asyncio
async def test_prepare_backup_skips_off_postgres(client, tmp_path, monkeypatch):
    from app.config import get_settings
    from app.services.backup import prepare_backup

    s = get_settings()
    monkeypatch.setattr(s, "BACKUP_PASSPHRASE", "x")
    monkeypatch.setattr(s, "BACKUP_DOWNLOAD_DIR", str(tmp_path))
    res = await prepare_backup()
    assert res["ok"] is False and "PostgreSQL" in res["reason"]


@pytest.mark.asyncio
async def test_outsider_cannot_delete_run(client, session_factory):
    from app.models.run import Run, RunStatus
    from app.models.user import User

    admin = await _login(client)
    uni = (
        await client.post("/api/v1/universities", json={"name": "Kobe"}, headers=admin)
    ).json()
    member = await _create_user(client, admin, "member@example.com")
    outsider = await _create_user(client, admin, "outsider@example.com")
    await client.patch(
        f"/api/v1/users/{member['id']}",
        json={"set_university": True, "university_id": uni["id"]},
        headers=admin,
    )

    async with session_factory() as db:
        member_u = (
            await db.execute(select(User).where(User.email == "member@example.com"))
        ).scalar_one()
        run, _ = await _make_run(db, member_u, status=RunStatus.complete)

    outsider_h = await _login_clear_force(client, outsider["email"], outsider["password"])
    r = await client.delete(f"/api/v1/runs/{run.id}", headers=outsider_h)
    assert r.status_code == 404
    async with session_factory() as db:
        assert await db.get(Run, run.id) is not None
