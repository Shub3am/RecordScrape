"""
Characterization tests for StorageManager.
They pin the current behaviour so the storage move in later milestones cannot change it silently.
"""

import pytest

from vpr.storage import StorageManager


@pytest.fixture
def storage(tmp_path):
    return StorageManager(db_path=str(tmp_path / "test.db"))


def test_create_session_round_trips_actions_and_selectors(storage):
    actions = [{"type": "click", "selector": "#go"}]
    selectors = [{"selector": "h1", "tagName": "H1", "attribute": "textContent"}]

    session_id = storage.create_session("Demo", "https://example.com", actions, selectors)
    session = storage.get_session(session_id)

    assert session["name"] == "Demo"
    assert session["url"] == "https://example.com"
    assert session["actions"] == actions
    assert session["selectors"] == selectors
    assert session["run_count"] == 0
    assert session["last_run"] is None


def test_session_without_selectors_returns_empty_list(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])

    assert storage.get_session(session_id)["selectors"] == []


def test_get_missing_session_returns_none(storage):
    assert storage.get_session(999) is None


def test_update_session_run_increments_count_and_sets_last_run(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])

    storage.update_session_run(session_id)
    storage.update_session_run(session_id)
    session = storage.get_session(session_id)

    assert session["run_count"] == 2
    assert session["last_run"] is not None


def test_get_all_sessions_returns_every_session(storage):
    storage.create_session("First", "https://a.example", [])
    storage.create_session("Second", "https://b.example", [])

    names = {session["name"] for session in storage.get_all_sessions()}

    assert names == {"First", "Second"}


def test_schedule_joins_session_name_and_url(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])

    schedule_id = storage.create_schedule(session_id, 15)
    schedule = storage.get_schedule(schedule_id)

    assert schedule["session_id"] == session_id
    assert schedule["session_name"] == "Demo"
    assert schedule["session_url"] == "https://example.com"
    assert schedule["frequency_minutes"] == 15
    assert schedule["enabled"] is True
    assert schedule["next_run"] is not None


def test_update_schedule_changes_frequency_and_enabled(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    schedule_id = storage.create_schedule(session_id, 15)

    storage.update_schedule(schedule_id, frequency_minutes=60, enabled=False)
    schedule = storage.get_schedule(schedule_id)

    assert schedule["frequency_minutes"] == 60
    assert schedule["enabled"] is False


def test_delete_schedule_removes_it(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    schedule_id = storage.create_schedule(session_id, 15)

    storage.delete_schedule(schedule_id)

    assert storage.get_schedule(schedule_id) is None


def test_extracted_data_round_trips_per_session(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    rows = [
        {"selector": "h1", "value": "Hello", "attribute": "textContent", "index": 0, "tag": "h1"}
    ]

    storage.save_extracted_data(session_id, rows)
    session_data = storage.get_session_data(session_id)
    all_data = storage.get_all_data()

    assert session_data[0]["data"] == rows
    assert all_data[0]["session_name"] == "Demo"
    assert all_data[0]["data"] == rows


def test_delete_session_cascades_to_schedules_and_data(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    schedule_id = storage.create_schedule(session_id, 15)
    storage.save_extracted_data(session_id, [{"value": "Hello"}])

    storage.delete_session(session_id)

    assert storage.get_schedule(schedule_id) is None
    assert storage.get_session_data(session_id) == []
