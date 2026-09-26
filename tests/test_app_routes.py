"""
Route tests for app.py.
app.py builds its StorageManager, browser worker and scheduler at import time, so each test imports a fresh copy inside a temp cwd.
"""

import dataclasses
import importlib
import sys

import pytest

from tests.fixture_site import find_closed_local_port, serve_fixture_pages

FIXTURE_PAGES = {
    "/products": '<title>Products</title><h2 class="name">Shoe</h2><h2 class="name">Hat</h2>',
}


@pytest.fixture(scope="module")
def fixture_site_url():
    with serve_fixture_pages(FIXTURE_PAGES) as site_url:
        yield site_url


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "app", raising=False)
    fresh_app_module = importlib.import_module("app")
    # Recording opens a visible window by design; tests have no screen to show it on.
    fresh_app_module.BROWSER_CONFIG = dataclasses.replace(
        fresh_app_module.BROWSER_CONFIG, headless=True
    )
    yield fresh_app_module
    fresh_app_module.scheduler.shutdown()
    fresh_app_module.browser_worker.stop()


def test_deleting_session_removes_its_scheduled_jobs(app_module):
    client = app_module.app.test_client()
    session_id = app_module.storage.create_session("Demo", "https://example.com", [])
    schedule_response = client.post(
        "/api/schedules", json={"session_id": session_id, "frequency_minutes": 30}
    )
    schedule_id = schedule_response.json["schedule_id"]
    assert app_module.scheduler.get_job_status(schedule_id) is not None

    client.delete(f"/api/sessions/{session_id}")

    assert app_module.scheduler.get_job_status(schedule_id) is None


def test_api_does_not_grant_cross_origin_access(app_module):
    client = app_module.app.test_client()

    response = client.get("/api/status", headers={"Origin": "https://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers


def test_recording_through_the_api_saves_the_session(app_module, fixture_site_url):
    client = app_module.app.test_client()
    start_url = f"{fixture_site_url}/products"

    start_response = client.post("/api/sessions/start", json={"url": start_url})
    status_while_recording = client.get("/api/status").json["recording"]
    selector_response = client.post("/api/sessions/selector")
    row_picker_response = client.post("/api/sessions/rows")
    stop_response = client.post("/api/sessions/stop", json={"name": "Products"})

    assert start_response.json["success"] is True
    assert status_while_recording is True
    assert selector_response.json["success"] is True
    assert row_picker_response.json["success"] is True
    assert client.get("/api/status").json["recording"] is False
    saved_session = client.get(f"/api/sessions/{stop_response.json['session_id']}").json
    assert saved_session["name"] == "Products"
    assert saved_session["url"] == start_url
    assert saved_session["actions"][0]["type"] == "navigate"
    assert saved_session["selectors"] == []
    assert saved_session["table"] is None


def test_row_picker_without_a_recording_is_refused(app_module):
    client = app_module.app.test_client()

    row_picker_response = client.post("/api/sessions/rows")

    assert row_picker_response.status_code == 400
    assert row_picker_response.json["error"] == "No active recording"


def test_recording_an_unreachable_url_fails_and_stays_idle(app_module):
    client = app_module.app.test_client()
    unreachable_url = f"http://127.0.0.1:{find_closed_local_port()}/"

    start_response = client.post("/api/sessions/start", json={"url": unreachable_url})

    assert start_response.status_code == 400
    assert "ERR_CONNECTION_REFUSED" in start_response.json["error"]
    assert client.get("/api/status").json["recording"] is False


def test_manual_replay_extracts_and_saves_rows(app_module, fixture_site_url):
    client = app_module.app.test_client()
    picked_elements = [{"selector": "h2.name", "fallbackSelectors": [], "attribute": "textContent"}]
    session_id = app_module.storage.create_session(
        "Products", f"{fixture_site_url}/products", [], picked_elements
    )

    replay_response = client.post(f"/api/sessions/{session_id}/replay", json={"headless": True})

    assert replay_response.json["success"] is True
    assert replay_response.json["items_count"] == 2
    saved_rows = client.get(f"/api/data/{session_id}").json[0]["data"]
    assert [row["value"] for row in saved_rows] == ["Shoe", "Hat"]
    assert client.get(f"/api/sessions/{session_id}").json["run_count"] == 1


def test_exported_flow_imports_as_an_equal_session(app_module):
    client = app_module.app.test_client()
    recorded_actions = [
        {"type": "navigate", "url": "https://shop.example/search", "timestamp": 1.0},
        {"type": "click", "selector": "#apply", "fallbackSelectors": ["button"], "timestamp": 2.0},
    ]
    picked_elements = [{"selector": "h1", "fallbackSelectors": [], "attribute": "textContent"}]
    session_id = app_module.storage.create_session(
        'Shoe "prices"', "https://shop.example/search", recorded_actions, picked_elements
    )

    export_response = client.get(f"/api/sessions/{session_id}/flow")
    import_response = client.post("/api/flows", json=export_response.json)

    assert (
        'filename="Shoe \\"prices\\".flow.json"' in export_response.headers["Content-Disposition"]
    )
    imported_session = client.get(f"/api/sessions/{import_response.json['session_id']}").json
    assert imported_session["name"] == 'Shoe "prices"'
    assert imported_session["url"] == "https://shop.example/search"
    assert imported_session["actions"] == [
        {"type": "click", "selector": "#apply", "fallbackSelectors": ["button"]}
    ]
    assert imported_session["selectors"] == picked_elements


def test_exporting_a_missing_session_is_not_found(app_module):
    client = app_module.app.test_client()

    assert client.get("/api/sessions/999/flow").status_code == 404


@pytest.mark.parametrize(
    "uploaded_text, named_problem",
    [
        (
            (
                '{"formatVersion": 2, "name": "Future", "startUrl": "https://shop.example/search",'
                ' "steps": [], "pickedElements": []}'
            ),
            "formatVersion",
        ),
        ("not a flow file", "Invalid JSON"),
    ],
    ids=["newer-version", "not-json"],
)
def test_importing_an_invalid_flow_is_refused_without_saving(
    app_module, uploaded_text, named_problem
):
    client = app_module.app.test_client()

    import_response = client.post("/api/flows", data=uploaded_text, content_type="application/json")

    assert import_response.status_code == 400
    assert named_problem in import_response.json["error"]
    assert client.get("/api/sessions").json == []
