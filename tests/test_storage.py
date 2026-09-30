"""
Characterization tests for StorageManager.
They pin the current behaviour so the storage move in later milestones cannot change it silently.
"""

import sqlite3

import pytest

from vpr.storage import StorageManager

CARD_TABLE = {
    "rowSelector": "ul > li.card",
    "rowFallbackSelectors": [],
    "columns": [
        {"name": "name", "selector": "h2", "fallbackSelectors": [], "attribute": "textContent"}
    ],
}

PROXIED_PATCHRIGHT = {
    "backend": "patchright",
    "proxy": "http://proxy.example:8080",
    "humanize": False,
}


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


def test_session_round_trips_its_row_table(storage):
    with_table_id = storage.create_session("Cards", "https://example.com", [], [], CARD_TABLE)
    without_table_id = storage.create_session("Plain", "https://example.com", [])

    assert storage.get_session(with_table_id)["table"] == CARD_TABLE
    assert storage.get_session(without_table_id)["table"] is None


def test_session_round_trips_its_browser_settings(storage):
    with_browser_id = storage.create_session(
        "Proxied", "https://example.com", [], browser=PROXIED_PATCHRIGHT
    )
    without_browser_id = storage.create_session("Plain", "https://example.com", [])

    assert storage.get_session(with_browser_id)["browser"] == PROXIED_PATCHRIGHT
    assert storage.get_session(without_browser_id)["browser"] is None


def test_database_from_before_added_columns_gains_them_and_keeps_sessions(tmp_path):
    db_path = tmp_path / "old.db"
    old_database = sqlite3.connect(db_path)
    old_database.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            actions TEXT NOT NULL,
            selectors TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_run TIMESTAMP,
            run_count INTEGER DEFAULT 0
        )
    """)
    old_database.execute(
        "INSERT INTO sessions (name, url, actions) VALUES ('Old', 'https://example.com', '[]')"
    )
    old_database.commit()
    old_database.close()

    storage = StorageManager(db_path=str(db_path))

    new_session_id = storage.create_session(
        "New", "https://example.com", [], [], CARD_TABLE, PROXIED_PATCHRIGHT
    )

    sessions_by_name = {session["name"]: session for session in storage.get_all_sessions()}
    old_session = sessions_by_name["Old"]
    assert old_session["table"] is None
    assert old_session["browser"] is None
    assert storage.get_session(new_session_id)["browser"] == PROXIED_PATCHRIGHT


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


def test_get_schedule_ids_for_session_returns_only_that_session(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    other_session_id = storage.create_session("Other", "https://other.example", [])
    first_schedule_id = storage.create_schedule(session_id, 15)
    second_schedule_id = storage.create_schedule(session_id, 60)
    storage.create_schedule(other_session_id, 15)

    schedule_ids = storage.get_schedule_ids_for_session(session_id)

    assert sorted(schedule_ids) == [first_schedule_id, second_schedule_id]


def test_extracted_data_round_trips_per_session(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    rows = [
        {"selector": "h1", "value": "Hello", "attribute": "textContent", "index": 0, "tag": "h1"}
    ]

    storage.save_run(session_id, rows)
    session_data = storage.get_session_data(session_id)
    all_data = storage.get_all_data()

    assert session_data[0]["data"] == rows
    assert all_data[0]["session_name"] == "Demo"
    assert all_data[0]["data"] == rows


def test_extracted_data_says_whether_its_session_has_a_row_table(storage):
    with_table_id = storage.create_session("Cards", "https://example.com", [], [], CARD_TABLE)
    without_table_id = storage.create_session("Plain", "https://example.com", [])
    storage.save_run(with_table_id, [{"name": "Shoe"}])
    storage.save_run(without_table_id, [])

    has_table_by_session = {
        extraction["session_id"]: extraction["has_table"] for extraction in storage.get_all_data()
    }

    assert has_table_by_session == {with_table_id: True, without_table_id: False}
    assert storage.get_session_data(with_table_id)[0]["has_table"] is True
    assert storage.get_session_data(without_table_id)[0]["has_table"] is False


def test_get_extraction_returns_one_run_with_its_session_name(storage):
    session_id = storage.create_session("Cards", "https://example.com", [], [], CARD_TABLE)
    storage.save_run(session_id, [{"name": "Shoe"}])
    data_id = storage.save_run(session_id, [{"name": "Hat"}])

    extraction = storage.get_extraction(data_id)

    assert extraction["session_name"] == "Cards"
    assert extraction["data"] == [{"name": "Hat"}]
    assert storage.get_extraction(data_id + 1) is None


def test_runs_saved_before_run_history_read_as_untimed_counted_successes(tmp_path):
    db_path = tmp_path / "old.db"
    StorageManager(db_path=str(db_path))
    old_database = sqlite3.connect(db_path)
    old_database.execute("DROP TABLE extracted_data")
    old_database.execute("""
        CREATE TABLE extracted_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    old_database.execute(
        "INSERT INTO sessions (name, url, actions) VALUES ('Old', 'https://example.com', '[]')"
    )
    old_database.execute(
        """INSERT INTO extracted_data (session_id, data) VALUES (1, '[{"name": "Shoe"}, {"name": "Hat"}]')"""
    )
    old_database.commit()
    old_database.close()

    storage = StorageManager(db_path=str(db_path))

    old_run = storage.get_extraction(1)
    assert old_run["status"] == "success"
    assert old_run["duration_ms"] is None
    assert old_run["triggered_by"] is None
    assert storage.get_run_summaries()[0]["items_count"] == 2


def test_failed_run_round_trips_its_outcome(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])

    data_id = storage.save_run(
        session_id,
        [],
        status="failed",
        error="net::ERR_CONNECTION_REFUSED",
        duration_ms=1250,
        triggered_by="schedule",
    )
    failed_run = storage.get_extraction(data_id)

    assert failed_run["data"] == []
    assert failed_run["status"] == "failed"
    assert failed_run["error"] == "net::ERR_CONNECTION_REFUSED"
    assert failed_run["duration_ms"] == 1250
    assert failed_run["triggered_by"] == "schedule"
    assert storage.get_all_data()[0]["status"] == "failed"
    assert storage.get_session_data(session_id)[0]["error"] == "net::ERR_CONNECTION_REFUSED"


def test_run_summaries_count_items_newest_first_without_data(storage):
    session_id = storage.create_session("Cards", "https://example.com", [])
    storage.save_run(session_id, [{"name": "Shoe"}, {"name": "Hat"}], duration_ms=900)
    failed_id = storage.save_run(session_id, [], status="failed", error="Timeout")

    summaries = storage.get_run_summaries()

    assert summaries[0]["id"] == failed_id
    assert [summary["items_count"] for summary in summaries] == [0, 2]
    assert summaries[1]["session_name"] == "Cards"
    assert summaries[1]["duration_ms"] == 900
    assert "data" not in summaries[0]


def test_run_stats_count_only_the_recent_window(storage):
    session_id = storage.create_session("Cards", "https://example.com", [])
    storage.save_run(session_id, [{"name": "Shoe"}, {"name": "Hat"}])
    storage.save_run(session_id, [], status="failed", error="Timeout")
    old_run_id = storage.save_run(session_id, [{"name": "Old"}])
    database = sqlite3.connect(storage.db_path)
    database.execute(
        "UPDATE extracted_data SET extracted_at = datetime('now', '-25 hours') WHERE id = ?",
        (old_run_id,),
    )
    database.commit()
    database.close()

    stats = storage.get_run_stats(since_hours=24)

    assert stats == {"runs": 2, "failed_runs": 1, "items_extracted": 2}


def test_delete_session_cascades_to_schedules_and_data(storage):
    session_id = storage.create_session("Demo", "https://example.com", [])
    schedule_id = storage.create_schedule(session_id, 15)
    storage.save_run(session_id, [{"value": "Hello"}])

    storage.delete_session(session_id)

    assert storage.get_schedule(schedule_id) is None
    assert storage.get_session_data(session_id) == []
