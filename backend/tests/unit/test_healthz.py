from datetime import date
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import admin as admin_module
from app.main import create_app
from app.pipeline.daily import DailyResult


def _fake_result() -> DailyResult:
    import uuid

    return DailyResult(
        run_id=uuid.uuid4(),
        publish_date=date(2026, 5, 3),
        total_articles=18,
        rejected_count=0,
        section_counts={},
    )


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_admin_generate_runs_pipeline_in_local(monkeypatch) -> None:
    fake = AsyncMock(return_value=_fake_result())
    monkeypatch.setattr(admin_module, "run_daily", fake)
    client = TestClient(create_app())
    response = client.post("/admin/generate", json={"publish_date": "2026-05-03"})
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["total_articles"] == 18


def test_admin_generate_rejects_bad_token_when_set(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_DEV_TOKEN", "secret123")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        fake = AsyncMock(return_value=_fake_result())
        monkeypatch.setattr(admin_module, "run_daily", fake)
        client = TestClient(create_app())
        bad = client.post(
            "/admin/generate",
            json={"publish_date": "2026-05-03"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert bad.status_code == 401
    finally:
        monkeypatch.delenv("ADMIN_DEV_TOKEN", raising=False)
        get_settings.cache_clear()


def test_admin_generate_accepts_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_DEV_TOKEN", "secret456")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        fake = AsyncMock(return_value=_fake_result())
        monkeypatch.setattr(admin_module, "run_daily", fake)
        client = TestClient(create_app())
        response = client.post(
            "/admin/generate",
            json={"publish_date": "2026-05-03"},
            headers={"Authorization": "Bearer secret456"},
        )
        assert response.status_code == 200
    finally:
        monkeypatch.delenv("ADMIN_DEV_TOKEN", raising=False)
        get_settings.cache_clear()
