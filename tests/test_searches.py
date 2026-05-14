"""Search CRUD, config validation, outlet CRUD, CSV import/export, languages CRUD + CSV."""
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

    r = await client.get("/api/v1/outlets/import/template", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    reader = csv.reader(io.StringIO(r.content.decode("utf-8-sig")))
    headers = next(reader)
    assert headers == ["name", "domain", "category", "keyword_langs", "notes"]

    r = await client.get("/api/v1/outlets/export", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0] == ["name", "domain", "category", "keyword_langs", "notes"]
    assert len(rows) > 1


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


@pytest.mark.asyncio
async def test_outlet_import_preview_and_commit(client):
    h = await _login(client)
    # Add a baseline outlet so we can test the duplicate path
    await client.post(
        "/api/v1/outlets",
        json={"name": "Existing Outlet", "domain": "dupe.example", "keyword_langs": []},
        headers=h,
    )

    csv_data = (
        "name,domain,category,keyword_langs,notes\n"
        "New Outlet,newoutlet.example,News,en,\n"
        "Updated Outlet,dupe.example,News,fr,\n"
    )
    files = {"file": ("import.csv", csv_data.encode(), "text/csv")}
    r = await client.post("/api/v1/outlets/import/preview", files=files, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["new_rows"]) == 1
    assert body["new_rows"][0]["domain"] == "newoutlet.example"
    assert len(body["duplicate_rows"]) == 1
    assert body["duplicate_rows"][0]["domain"] == "dupe.example"

    # Commit: add the new row, replace the duplicate
    existing_id = body["duplicate_rows"][0]["existing_id"]
    commit_payload = {
        "mode": "add",
        "items": [
            {
                "name": "New Outlet",
                "domain": "newoutlet.example",
                "category": "News",
                "keyword_langs": ["en"],
            },
            {
                "name": "Updated Outlet",
                "domain": "dupe.example",
                "category": "News",
                "keyword_langs": ["fr"],
                "replace_existing_id": existing_id,
            },
        ],
    }
    r = await client.post("/api/v1/outlets/import/commit", json=commit_payload, headers=h)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["added"] == 1
    assert report["replaced"] == 1


@pytest.mark.asyncio
async def test_outlet_bulk_delete(client):
    h = await _login(client)
    # Create two outlets
    r1 = await client.post(
        "/api/v1/outlets",
        json={"name": "BD1", "domain": "bd1.example", "keyword_langs": []},
        headers=h,
    )
    r2 = await client.post(
        "/api/v1/outlets",
        json={"name": "BD2", "domain": "bd2.example", "keyword_langs": []},
        headers=h,
    )
    ids = [r1.json()["id"], r2.json()["id"]]

    r = await client.post(
        "/api/v1/outlets/bulk-delete", json={"outlet_ids": ids}, headers=h
    )
    assert r.status_code == 204

    r = await client.get("/api/v1/outlets", headers=h)
    domains = [o["domain"] for o in r.json()]
    assert "bd1.example" not in domains
    assert "bd2.example" not in domains


# ---------------------------------------------------------------------------
# Languages CRUD + CSV
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_languages_crud(client):
    h = await _login(client)

    r = await client.get("/api/v1/languages", headers=h)
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.post(
        "/api/v1/languages",
        json={"iso_code": "de", "university_name": "Kobe-Universität"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    lang_id = r.json()["id"]
    assert r.json()["iso_code"] == "de"

    # Duplicate ISO rejected
    r2 = await client.post(
        "/api/v1/languages",
        json={"iso_code": "DE", "university_name": "X"},
        headers=h,
    )
    assert r2.status_code == 409

    r = await client.put(
        f"/api/v1/languages/{lang_id}",
        json={"university_name": "Universität Kobe"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["university_name"] == "Universität Kobe"

    r = await client.delete(f"/api/v1/languages/{lang_id}", headers=h)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_language_invalid_iso_code_rejected(client):
    h = await _login(client)
    r = await client.post(
        "/api/v1/languages",
        json={"iso_code": "NOT_VALID!", "university_name": "X"},
        headers=h,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_language_csv_template_and_export(client):
    h = await _login(client)
    r = await client.get("/api/v1/languages/import/template", headers=h)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0] == ["iso_code", "university_name"]
    # Template ISO codes uppercase
    assert rows[1][0] == "EN"

    r = await client.get("/api/v1/languages/export", headers=h)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0] == ["iso_code", "university_name"]


@pytest.mark.asyncio
async def test_language_csv_preview_invalid_and_duplicate(client):
    h = await _login(client)
    csv_data = (
        "iso_code,university_name\n"
        "EN,New Kobe University\n"     # duplicate (seeded English)
        "FR,Université de Kobe\n"      # new + valid
        "XYZ,Bogus Language\n"          # invalid ISO
    )
    files = {"file": ("langs.csv", csv_data.encode(), "text/csv")}
    r = await client.post("/api/v1/languages/import/preview", files=files, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["new_rows"]) == 1
    assert body["new_rows"][0]["iso_code"] == "fr"
    assert len(body["duplicate_rows"]) == 1
    assert body["duplicate_rows"][0]["iso_code"] == "en"
    assert len(body["invalid_iso_rows"]) == 1
    assert body["invalid_iso_rows"][0]["raw_iso"] == "XYZ"


@pytest.mark.asyncio
async def test_language_csv_commit_replace(client):
    h = await _login(client)
    commit_payload = {
        "mode": "replace",
        "items": [
            {"iso_code": "EN", "university_name": "Kobe University"},
            {"iso_code": "DE", "university_name": "Universität Kobe"},
        ],
    }
    r = await client.post("/api/v1/languages/import/commit", json=commit_payload, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 2

    r = await client.get("/api/v1/languages", headers=h)
    iso_codes = {row["iso_code"] for row in r.json()}
    assert iso_codes == {"en", "de"}


@pytest.mark.asyncio
async def test_language_bulk_delete(client):
    h = await _login(client)
    r1 = await client.post(
        "/api/v1/languages",
        json={"iso_code": "es", "university_name": "Universidad de Kobe"},
        headers=h,
    )
    r2 = await client.post(
        "/api/v1/languages",
        json={"iso_code": "it", "university_name": "Università di Kobe"},
        headers=h,
    )
    ids = [r1.json()["id"], r2.json()["id"]]

    r = await client.post(
        "/api/v1/languages/bulk-delete", json={"language_ids": ids}, headers=h
    )
    assert r.status_code == 204

    r = await client.get("/api/v1/languages", headers=h)
    iso_codes = {row["iso_code"] for row in r.json()}
    assert "es" not in iso_codes
    assert "it" not in iso_codes


# ---------------------------------------------------------------------------
# Search config validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_config_validation_requires_actionable_query(client):
    h = await _login(client)
    r = await client.post("/api/v1/searches", json={"name": "Validation Test"}, headers=h)
    assert r.status_code == 201
    search_id = r.json()["id"]

    r = await client.post("/api/v1/runs", json={"search_id": search_id}, headers=h)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_search_config_with_term_is_runnable(client):
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
        f"/api/v1/searches/{search_id}", json={"config": config}, headers=h
    )
    assert r.status_code == 200

    r = await client.post("/api/v1/runs", json={"search_id": search_id}, headers=h)
    assert r.status_code == 400
    assert "credentials" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Bulk delete + merged results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_delete_runs_empty_list(client):
    h = await _login(client)
    r = await client.post("/api/v1/runs/bulk-delete", json={"run_ids": []}, headers=h)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_merged_results_foreign_run_id_rejected(client):
    h = await _login(client)
    r = await client.get(
        "/api/v1/runs/merged?run_ids[]=00000000-0000-0000-0000-000000000000",
        headers=h,
    )
    assert r.status_code == 403
