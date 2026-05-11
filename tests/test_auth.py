"""Smoke tests for auth, bootstrap admin, and credentials encryption."""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_login_bootstrap_admin(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "TestAdminPassword!"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["force_password_change"] is True
    assert data["access_token"]


@pytest.mark.asyncio
async def test_me_requires_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_flow(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "TestAdminPassword!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TestAdminPassword!", "new_password": "BrandNewPwd1!"},
        headers=headers,
    )
    assert r.status_code == 204

    # Old password should now fail.
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "TestAdminPassword!"},
    )
    assert r.status_code == 401

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "BrandNewPwd1!"},
    )
    assert r.status_code == 200
    assert r.json()["force_password_change"] is False
