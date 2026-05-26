"""Tests for the run lifecycle — date extractor, run trigger guard, CSV export."""
import csv
import io
from pathlib import Path

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


def test_search_engine_never_writes_legacy_web_outlet_name():
    """Guard for the v2.4 item 2 invariant.

    Pre-v2.2, bare (no site:) searches stored ``outlet_name = "Web"`` on each
    Result row. v2.2 switched the sentinel to ``""`` and v2.4 migration 0007
    backfilled the historical rows. This test documents that the engine source
    no longer mentions the legacy literal anywhere, so the dataset stays
    consistent without a second renaming round.
    """
    src = Path("app/services/search_engine.py").read_text(encoding="utf-8")
    assert '"Web"' not in src and "'Web'" not in src, (
        "search_engine.py must not write the legacy 'Web' outlet_name sentinel — "
        "use '' (empty string) instead and let the UI derive the host from the URL."
    )


@pytest.mark.asyncio
async def test_csv_export_empty_runs(client):
    """Hits a clean error when run_ids do not belong to the user — sanity check."""
    h = await _login(client)
    r = await client.get(
        "/api/v1/runs/export?run_ids[]=00000000-0000-0000-0000-000000000000",
        headers=h,
    )
    assert r.status_code == 403
