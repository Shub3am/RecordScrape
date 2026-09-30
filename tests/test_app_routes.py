"""
Route tests for app.py.
app.py builds its StorageManager, browser worker and scheduler at import time, so each test imports a fresh copy inside a temp cwd.
"""

import dataclasses
import importlib
import sys
from urllib.parse import urlparse

import pytest

from tests.fixture_proxy import serve_authenticating_proxy
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
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("RECORDSCRAPE_DATA_DIR", str(tmp_path / "data"))
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


def test_api_on_the_loopback_default_needs_no_token(app_module):
    client = app_module.app.test_client()

    assert client.get("/api/status").status_code == 200


@pytest.mark.parametrize(
    "authorization_headers",
    [{}, {"Authorization": "Bearer wrong-token"}],
    ids=["no-token", "wrong-token"],
)
def test_api_with_a_token_refuses_requests_without_it(app_module, authorization_headers):
    app_module.SERVER_SETTINGS = dataclasses.replace(app_module.SERVER_SETTINGS, api_token="s3cret")
    client = app_module.app.test_client()

    response = client.get("/api/status", headers=authorization_headers)

    assert response.status_code == 401
    assert response.json == {"error": "Missing or wrong API token"}


def test_api_with_a_token_serves_requests_carrying_it(app_module):
    app_module.SERVER_SETTINGS = dataclasses.replace(app_module.SERVER_SETTINGS, api_token="s3cret")
    client = app_module.app.test_client()

    api_response = client.get("/api/status", headers={"Authorization": "Bearer s3cret"})
    dashboard_response = client.get("/")

    assert api_response.status_code == 200
    assert dashboard_response.status_code == 200


def test_the_database_lives_in_the_configured_data_dir(app_module, tmp_path):
    assert (tmp_path / "data" / "scraper.db").exists()
    assert not (tmp_path / "scraper.db").exists()


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


@pytest.mark.parametrize("typed_name", ["", "   "], ids=["empty", "whitespace"])
def test_a_session_saved_without_a_name_is_named_after_its_host(
    app_module, fixture_site_url, typed_name
):
    client = app_module.app.test_client()

    client.post("/api/sessions/start", json={"url": f"{fixture_site_url}/products"})
    stop_response = client.post("/api/sessions/stop", json={"name": typed_name})

    saved_session = client.get(f"/api/sessions/{stop_response.json['session_id']}").json
    assert saved_session["name"] == urlparse(fixture_site_url).hostname


@pytest.mark.parametrize("picker_route", ["rows", "next-button", "infinite-scroll"])
def test_picker_without_a_recording_is_refused(app_module, picker_route):
    client = app_module.app.test_client()

    picker_response = client.post(f"/api/sessions/{picker_route}")

    assert picker_response.status_code == 400
    assert picker_response.json["error"] == "No active recording"


def test_pagination_needs_rows_then_goes_into_the_saved_table(app_module, fixture_site_url):
    client = app_module.app.test_client()
    client.post("/api/sessions/start", json={"url": f"{fixture_site_url}/products"})

    next_button_before_rows = client.post("/api/sessions/next-button")
    infinite_scroll_before_rows = client.post("/api/sessions/infinite-scroll")
    # Stands in for the rows the picker would send after two clicks in the browser.
    picked_row_table = {"rowSelector": "li", "rowFallbackSelectors": [], "columns": []}
    app_module.current_recorder.row_table = picked_row_table
    next_button_response = client.post("/api/sessions/next-button")
    infinite_scroll_response = client.post("/api/sessions/infinite-scroll")
    stop_response = client.post("/api/sessions/stop", json={"name": "Feed"})

    assert next_button_before_rows.status_code == 400
    assert next_button_before_rows.json["error"] == "Select rows first"
    assert infinite_scroll_before_rows.status_code == 400
    assert infinite_scroll_before_rows.json["error"] == "Select rows first"
    assert next_button_response.json["success"] is True
    assert infinite_scroll_response.json["success"] is True
    saved_session = client.get(f"/api/sessions/{stop_response.json['session_id']}").json
    assert saved_session["table"] == {
        **picked_row_table,
        "pagination": {"mode": "infiniteScroll", "maxScrolls": 10},
    }


@pytest.mark.parametrize(
    "requested_backend, recording_backend",
    [("patchright", "patchright"), ("cloakbrowser", "patchright")],
    ids=["records-on-its-own-backend", "cloakbrowser-records-on-patchright"],
)
def test_recording_saves_the_browser_settings_it_was_started_with(
    app_module, fixture_site_url, requested_backend, recording_backend
):
    client = app_module.app.test_client()
    browser_settings = {"backend": requested_backend, "proxy": None, "humanize": False}

    client.post(
        "/api/sessions/start",
        json={"url": f"{fixture_site_url}/products", "browser": {"backend": requested_backend}},
    )
    backend_while_recording = app_module.current_recorder.browser_config.backend
    stop_response = client.post("/api/sessions/stop", json={"name": "Products"})

    assert backend_while_recording == recording_backend
    saved_session = client.get(f"/api/sessions/{stop_response.json['session_id']}").json
    assert saved_session["browser"] == browser_settings


@pytest.mark.parametrize(
    "browser_settings, expected_error",
    [
        ({"backend": "chromium", "humanize": True}, "Invalid browser settings"),
        (
            {"backend": "chromium", "proxy": "http://${UNSET_PROXY_PASS}@proxy.test:8080"},
            "UNSET_PROXY_PASS",
        ),
    ],
    ids=["humanize-on-chromium", "proxy-env-var-not-set"],
)
def test_recording_with_unusable_browser_settings_fails_and_stays_idle(
    app_module, fixture_site_url, browser_settings, expected_error, monkeypatch
):
    monkeypatch.delenv("UNSET_PROXY_PASS", raising=False)
    client = app_module.app.test_client()

    start_response = client.post(
        "/api/sessions/start",
        json={"url": f"{fixture_site_url}/products", "browser": browser_settings},
    )

    assert start_response.status_code == 400
    assert expected_error in start_response.json["error"]
    assert client.get("/api/status").json["recording"] is False


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


def test_manual_replay_applies_its_run_options(app_module, fixture_site_url):
    client = app_module.app.test_client()
    picked_elements = [{"selector": "h2.name", "fallbackSelectors": [], "attribute": "textContent"}]
    session_id = app_module.storage.create_session(
        "Products", f"{fixture_site_url}/products", [], picked_elements
    )

    replay_response = client.post(
        f"/api/sessions/{session_id}/replay", json={"headless": True, "max_rows": 1}
    )

    assert replay_response.json["items_count"] == 1
    assert client.get(f"/api/data/{session_id}").json[0]["data"][0]["value"] == "Shoe"


@pytest.mark.parametrize(
    "replay_body",
    [{"max_rows": 0}, {"max_pages": "many"}, {"max_items": 5}],
    ids=["zero", "not-a-number", "unknown"],
)
def test_manual_replay_with_invalid_run_options_is_refused(app_module, replay_body):
    client = app_module.app.test_client()
    session_id = app_module.storage.create_session("Demo", "https://example.com", [])

    replay_response = client.post(f"/api/sessions/{session_id}/replay", json=replay_body)

    assert replay_response.status_code == 400
    assert replay_response.json["error"].startswith("Invalid run options")
    assert client.get(f"/api/data/{session_id}").json == []


def test_failed_manual_replay_is_saved_as_a_failed_run(app_module):
    client = app_module.app.test_client()
    unreachable_url = f"http://127.0.0.1:{find_closed_local_port()}/"
    session_id = app_module.storage.create_session("Down", unreachable_url, [])

    replay_response = client.post(f"/api/sessions/{session_id}/replay", json={"headless": True})

    assert replay_response.json["success"] is False
    failed_run = client.get(f"/api/data/{session_id}").json[0]
    assert failed_run["status"] == "failed"
    assert "ERR_CONNECTION_REFUSED" in failed_run["error"]
    assert failed_run["triggered_by"] == "manual"
    assert failed_run["duration_ms"] >= 0
    assert client.get(f"/api/sessions/{session_id}").json["run_count"] == 1


def test_scheduled_run_is_saved_with_its_trigger(app_module, fixture_site_url):
    picked_elements = [{"selector": "h2.name", "fallbackSelectors": [], "attribute": "textContent"}]
    session_id = app_module.storage.create_session(
        "Products", f"{fixture_site_url}/products", [], picked_elements
    )
    schedule_id = app_module.storage.create_schedule(session_id, 60)

    app_module.scheduler._run_scraping_job(session_id, schedule_id)

    scheduled_run = app_module.storage.get_session_data(session_id)[0]
    assert scheduled_run["status"] == "success"
    assert scheduled_run["triggered_by"] == "schedule"
    assert [row["value"] for row in scheduled_run["data"]] == ["Shoe", "Hat"]


def test_manual_replay_runs_through_the_sessions_proxy(app_module, fixture_site_url):
    client = app_module.app.test_client()
    picked_elements = [{"selector": "h2.name", "fallbackSelectors": [], "attribute": "textContent"}]

    with serve_authenticating_proxy("ana", "hunter2", {"shop.test": fixture_site_url}) as proxy:
        browser_settings = {
            "backend": "patchright",
            "proxy": f"http://ana:hunter2@{proxy.address}",
            "humanize": False,
        }
        session_id = app_module.storage.create_session(
            "Products", "http://shop.test/products", [], picked_elements, browser=browser_settings
        )
        replay_response = client.post(f"/api/sessions/{session_id}/replay", json={"headless": True})

    assert replay_response.json["success"] is True
    assert replay_response.json["items_count"] == 2
    assert "http://shop.test/products" in proxy.authenticated_urls


@pytest.mark.parametrize(
    "export_format, expected_mimetype",
    [("csv", "text/csv"), ("json", "application/json"), ("jsonl", "application/jsonl")],
)
def test_extraction_downloads_in_each_format(app_module, export_format, expected_mimetype):
    client = app_module.app.test_client()
    shoe_records = [{"name": "Shoe", "price": "$40"}]
    session_id = app_module.storage.create_session("Cards", "https://shop.example", [])
    data_id = app_module.storage.save_run(session_id, shoe_records)

    export_response = client.get(f"/api/data/{data_id}/export?format={export_format}")

    assert export_response.get_data(as_text=True) == app_module.EXPORT_FORMATS[
        export_format
    ].write_records(shoe_records)
    assert export_response.mimetype == expected_mimetype
    assert export_response.headers["Content-Disposition"] == (
        f"attachment; filename=Cards-{data_id}.{export_format}"
    )


def test_exporting_missing_data_or_an_unknown_format_is_refused(app_module):
    client = app_module.app.test_client()
    session_id = app_module.storage.create_session("Cards", "https://shop.example", [])
    data_id = app_module.storage.save_run(session_id, [])

    missing_response = client.get(f"/api/data/{data_id + 1}/export?format=csv")
    unknown_format_response = client.get(f"/api/data/{data_id}/export?format=xlsx")

    assert missing_response.status_code == 404
    assert unknown_format_response.status_code == 400
    assert unknown_format_response.json["error"] == "Format must be one of: csv, json, jsonl"


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
