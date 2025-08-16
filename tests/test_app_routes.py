"""
Route tests for app.py.
app.py builds its StorageManager and scheduler at import time, so each test imports a fresh copy inside a temp cwd.
"""

import importlib
import sys

import pytest


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "app", raising=False)
    fresh_app_module = importlib.import_module("app")
    yield fresh_app_module
    fresh_app_module.scheduler.shutdown()


def test_deleting_session_removes_its_scheduled_jobs(app_module):
    client = app_module.app.test_client()
    session_id = app_module.storage.create_session("Demo", "https://example.com", [])
    schedule_response = client.post(
        "/api/schedules", json={"session_id": session_id, "frequency_minutes": 30}
    )
    job_id = f"schedule_{schedule_response.json['schedule_id']}"
    assert app_module.scheduler.scheduler.get_job(job_id) is not None

    client.delete(f"/api/sessions/{session_id}")

    assert app_module.scheduler.scheduler.get_job(job_id) is None


def test_api_does_not_grant_cross_origin_access(app_module):
    client = app_module.app.test_client()

    response = client.get("/api/status", headers={"Origin": "https://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers
