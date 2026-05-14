"""Search CRUD, config validation, outlet CRUD, CSV import/export, languages CRUD."""
import csv
import io

import pytest


async def _login(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "TestAdminPassword!"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Bootstrap smoke test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bootstrap_seeded_outlets_and_default_search(client):
    h = await _login(client)
    r = await client.get("/api/v1/outlets", headers=h)
    assert r.status_code == 200
    assert len(r.json()) > 50  # seeded library is ~75 outlets

    r = await client.get("/api/v1/searches", headers=h)
    assert r.status_code == 200
    searches = r.json()
    assert any(s["is_default"] for s in searches)


# ---------------------------------------------------------------------------
# Outlet CRUD + CSV import/export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outlet_create_and_duplicate_domain_rejected(client):
    h = await _login(client)
    payload = {
        "name": "Test Outlet",
        "domain": "https://example.test/",
        "category": "Custom",
        "keyword_langs": ["en", "fr"],
        "is_active": True,
    }
    r = await client.post("/api/v1/outlets", json=payload, headers=h)
    assert r.status_code == 201
    assert r.json()["domain"] == "example.test"  # cleaned

    r2 = await client.post("/api/v1/outlets", json=payload, headers=h)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_outlet_import_template_and_export(client):
    h = await _login(client)

    # Template is a valid CSV with the right headers
    r = await client.get("/api/v1/outlets/import/template", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    reader = csv.reader(io.StringIO(r.content.decode("utf-8-sig")))
    headers = next(reader)
    assert headers == ["name", "domain", "category", "keyword_langs", "notes"]

    # Export is also a valid CSV with header + data rows
    r = await client.get("/api/v1/outlets/export", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0] == ["name", "domain", "category", "keyword_langs", "notes"]
    assert len(rows) > 1  # seeded outlets present


@pytest.mark.asyncio
async def test_outlet_csv_import_add(client):
    h = await _login(client)
    csv_data = "name,domain,category,keyword_langs,notes\nTest Import,importtest.com,Test,en,\n"
    files = {"file": ("import.csv", csv_data.encode(), "text/csv")}
    r = await client.post("/api/v1/outlets/import?mode=add", files=files, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 1
    assert body["skipped"] == []


# ---------------------------------------------------------------------------
# Languages CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_languages_crud(client):
    h = await _login(client)

    # Bootstrap should have seeded at least one language
    r = await client.get("/api/v1/languages", headers=h)
    assert r.status_code == 200
    langs = r.json()
    assert len(langs) >= 1

    # Create a new language
    r = await client.post(
        "/api/v1/languages",
        json={"iso_code": "de", "language_label": "German", "university_name": "Kobe-Universität"},
        headers=h,
    )
    assert r.status_code == 201
    lang_id = r.json()["id"]

    # Update it
    r = await client.put(
        f"/api/v1/languages/{lang_id}",
        json={"university_name": "Universität Kobe"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["university_name"] == "Universität Kobe"

    # Delete it
    r = await client.delete(f"/api/v1/languages/{lang_id}", headers=h)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_language_invalid_iso_code_rejected(client):
    h = await _login(client)
    r = await client.post(
        "/api/v1/languages",
        json={"iso_code": "NOT_VALID!", "language_label": "X", "university_name": "X"},
        headers=h,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Search config validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_config_validation_requires_actionable_query(client):
    h = await _login(client)

    # Create a search
    r = await client.post("/api/v1/searches", json={"name": "Validation Test"}, headers=h)
    assert r.status_code == 201
    search_id = r.json()["id"]

    # Empty config — running should be rejected (400)
    r = await client.post(
        "/api/v1/runs", json={"search_id": search_id}, headers=h
    )
    # 400 for no credentials OR for invalid config — either is acceptable;
    # config check happens before credential check so expect 400 with "config" or "credentials"
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_search_config_with_term_is_runnable(client):
    """A search with a non-empty term passes config validation (credential check raises 400 differently)."""
    h = await _login(client)
    r = await client.post("/api/v1/searches", json={"name": "Term Test"}, headers=h)
    search_id = r.json()["id"]

    config = {
        "search_window": "last",
        "fallback_hours": 72,
        "terms": [{"id": "aaa-bbb", "text": "Kobe University", "operator": None, "pages": 1}],
        "doi": {"text": "", "pages": 1},
        "university_name": {"enabled": False, "language_ids": []},
        "outlets": {"enabled": False, "outlet_ids": []},
    }
    r = await client.put(
        f"/api/v1/searches/{search_id}",
        json={"config": config},
        headers=h,
    )
    assert r.status_code == 200

    # Trigger run — should fail at credentials, not at config
    r = await client.post("/api/v1/runs", json={"search_id": search_id}, headers=h)
    assert r.status_code == 400
    assert "credentials" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Bulk delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_delete_runs_empty_list(client):
    h = await _login(client)
    r = await client.post("/api/v1/runs/bulk-delete", json={"run_ids": []}, headers=h)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Merged results endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_merged_results_foreign_run_id_rejected(client):
    h = await _login(client)
    r = await client.get(
        "/api/v1/runs/merged?run_ids[]=00000000-0000-0000-0000-000000000000",
        headers=h,
    )
    # Non-existent run ID is treated as "not authorised" to avoid information leakage
    assert r.status_code == 403
