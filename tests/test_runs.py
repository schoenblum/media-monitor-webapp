"""Tests for the run lifecycle — date extractor, run trigger guard, CSV export."""
import csv
import io

import pytest

from app.services.date_extractor import extract_date


async def _login(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "TestAdminPassword!"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_date_extractor_handles_common_formats():
    assert extract_date("Published 12 March 2026 by …") == "2026/03/12"
    assert extract_date("March 12, 2026 — story") == "2026/03/12"
    assert extract_date("2026-03-12 byline") == "2026/03/12"
    assert extract_date("2026/03/12 17:00") == "2026/03/12"
    assert extract_date("no date here") == ""
    assert extract_date("") == ""


@pytest.mark.asyncio
async def test_trigger_run_requires_credentials(client):
    h = await _login(client)
    # Find the seeded default search.
    searches = (await client.get("/api/v1/searches", headers=h)).json()
    default = next(s for s in searches if s["is_default"])

    r = await client.post(
        "/api/v1/runs", json={"search_id": default["id"]}, headers=h
    )
    assert r.status_code == 400
    assert "credentials" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_csv_export_empty_runs(client):
    """Hits a clean error when run_ids do not belong to the user — sanity check."""
    h = await _login(client)
    r = await client.get(
        "/api/v1/runs/export?run_ids[]=00000000-0000-0000-0000-000000000000",
        headers=h,
    )
    assert r.status_code == 403
