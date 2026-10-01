"""
Storage Manager for Visual Data Scraper
Handles SQLite database operations for sessions, schedules, and extracted data.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

RUN_HISTORY_COLUMNS = {
    "status": "TEXT NOT NULL DEFAULT 'success'",
    "error": "TEXT",
    "duration_ms": "INTEGER",
    "triggered_by": "TEXT",
    "items_count": "INTEGER",
}


def next_run_from_now(frequency_minutes: int) -> str:
    """The next run time, in the server's local time, as the text the dashboard parses."""
    # Written as text because sqlite3's default datetime adapter is deprecated since Python 3.12.
    # isoformat(" ") is what that adapter wrote, so stored values keep one format. The time stays
    # naive server local time because the dashboard parses next_run as local time.
    return (datetime.now() + timedelta(minutes=frequency_minutes)).isoformat(" ")  # noqa: DTZ005


def run_outcome_fields(row: sqlite3.Row) -> dict:
    """The fields every run read carries besides its data: how it ended, how long it took and what started it."""
    return {
        "status": row["status"],
        "error": row["error"],
        "duration_ms": row["duration_ms"],
        "triggered_by": row["triggered_by"],
    }


class StorageManager:
    """Manages all database operations for the scraper."""

    def __init__(self, db_path: str = "scraper.db"):
        """Initialize storage manager with database path."""
        self.db_path = db_path
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with foreign keys enforced."""
        conn = sqlite3.connect(self.db_path)
        # SQLite ships with foreign keys off per connection, so ON DELETE CASCADE is inert without this.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = self._connect()
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                actions TEXT NOT NULL,
                selectors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run TIMESTAMP,
                run_count INTEGER DEFAULT 0,
                row_table TEXT,
                browser_settings TEXT
            )
        """)

        # Databases created before these columns lack them; CREATE TABLE IF NOT EXISTS skips them.
        session_columns = {column[1] for column in cursor.execute("PRAGMA table_info(sessions)")}
        for added_column in ("row_table", "browser_settings"):
            if added_column not in session_columns:
                cursor.execute(f"ALTER TABLE sessions ADD COLUMN {added_column} TEXT")

        # Schedules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                frequency_minutes INTEGER NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                next_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)

        # Extracted data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracted_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)

        # The run history columns are only ever added here, so new and old databases get the same ones.
        # Runs saved before run history only ever succeeded, so the status default fits them.
        run_columns = {column[1] for column in cursor.execute("PRAGMA table_info(extracted_data)")}
        for added_column, column_type in RUN_HISTORY_COLUMNS.items():
            if added_column not in run_columns:
                cursor.execute(
                    f"ALTER TABLE extracted_data ADD COLUMN {added_column} {column_type}"
                )
        if "items_count" not in run_columns:
            cursor.execute("UPDATE extracted_data SET items_count = json_array_length(data)")

        # The dashboard polls run stats and the run list, both ordered or filtered by extracted_at.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS extracted_data_by_time ON extracted_data (extracted_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS extracted_data_by_session_time"
            " ON extracted_data (session_id, extracted_at)"
        )

        conn.commit()
        conn.close()

    # ==================== SESSION OPERATIONS ====================

    def create_session(
        self,
        name: str,
        url: str,
        actions: list[dict],
        selectors: list[dict] | None = None,
        table: dict | None = None,
        browser: dict | None = None,
    ) -> int:
        """Create a new session recording. browser None means the app's default browser."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO sessions (name, url, actions, selectors, row_table, browser_settings)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                url,
                json.dumps(actions),
                json.dumps(selectors) if selectors else None,
                json.dumps(table) if table else None,
                json.dumps(browser) if browser else None,
            ),
        )

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return session_id

    def get_session(self, session_id: int) -> dict | None:
        """Get a session by ID."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "actions": json.loads(row["actions"]),
                "selectors": json.loads(row["selectors"]) if row["selectors"] else [],
                "table": json.loads(row["row_table"]) if row["row_table"] else None,
                "browser": json.loads(row["browser_settings"]) if row["browser_settings"] else None,
                "created_at": row["created_at"],
                "last_run": row["last_run"],
                "run_count": row["run_count"],
            }
        return None

    def get_all_sessions(self) -> list[dict]:
        """Get all sessions."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sessions.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "url": row["url"],
                    "actions": json.loads(row["actions"]),
                    "selectors": json.loads(row["selectors"]) if row["selectors"] else [],
                    "table": json.loads(row["row_table"]) if row["row_table"] else None,
                    "browser": json.loads(row["browser_settings"])
                    if row["browser_settings"]
                    else None,
                    "created_at": row["created_at"],
                    "last_run": row["last_run"],
                    "run_count": row["run_count"],
                }
            )

        return sessions

    def update_session(self, session_id: int, name: str | None = None, table: dict | None = None):
        """Rename a session, replace its row table, or both."""
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if table is not None:
            updates.append("row_table = ?")
            params.append(json.dumps(table))

        if updates:
            conn = self._connect()
            conn.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", (*params, session_id)
            )
            conn.commit()
            conn.close()

    def update_session_run(self, session_id: int):
        """Update session last run time and increment run count."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE sessions 
            SET last_run = CURRENT_TIMESTAMP, run_count = run_count + 1
            WHERE id = ?
        """,
            (session_id,),
        )

        conn.commit()
        conn.close()

    def delete_session(self, session_id: int):
        """Delete a session and all related data."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

        conn.commit()
        conn.close()

    # ==================== SCHEDULE OPERATIONS ====================

    def create_schedule(self, session_id: int, frequency_minutes: int) -> int:
        """Create a new schedule for a session."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO schedules (session_id, frequency_minutes, next_run)
            VALUES (?, ?, ?)
        """,
            (session_id, frequency_minutes, next_run_from_now(frequency_minutes)),
        )

        schedule_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return schedule_id

    def get_schedule(self, schedule_id: int) -> dict | None:
        """Get a schedule by ID."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT s.*, sess.name as session_name, sess.url as session_url
            FROM schedules s
            JOIN sessions sess ON s.session_id = sess.id
            WHERE s.id = ?
        """,
            (schedule_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row["id"],
                "session_id": row["session_id"],
                "session_name": row["session_name"],
                "session_url": row["session_url"],
                "frequency_minutes": row["frequency_minutes"],
                "enabled": bool(row["enabled"]),
                "next_run": row["next_run"],
                "created_at": row["created_at"],
            }
        return None

    def get_all_schedules(self) -> list[dict]:
        """Get all schedules."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.*, sess.name as session_name, sess.url as session_url
            FROM schedules s
            JOIN sessions sess ON s.session_id = sess.id
            ORDER BY s.created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        schedules = []
        for row in rows:
            schedules.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "session_name": row["session_name"],
                    "session_url": row["session_url"],
                    "frequency_minutes": row["frequency_minutes"],
                    "enabled": bool(row["enabled"]),
                    "next_run": row["next_run"],
                    "created_at": row["created_at"],
                }
            )

        return schedules

    def get_schedule_ids_for_session(self, session_id: int) -> list[int]:
        """Get the ids of every schedule that replays a session."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM schedules WHERE session_id = ?", (session_id,))
        schedule_ids = [row[0] for row in cursor.fetchall()]

        conn.close()
        return schedule_ids

    def update_schedule(
        self, schedule_id: int, frequency_minutes: int | None = None, enabled: bool | None = None
    ):
        """Update a schedule."""
        conn = self._connect()
        cursor = conn.cursor()

        updates = []
        params = []

        if frequency_minutes is not None:
            updates.append("frequency_minutes = ?")
            params.append(frequency_minutes)

            updates.append("next_run = ?")
            params.append(next_run_from_now(frequency_minutes))

        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)

        if updates:
            params.append(schedule_id)
            query = f"UPDATE schedules SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

        conn.close()

    def delete_schedule(self, schedule_id: int):
        """Delete a schedule."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))

        conn.commit()
        conn.close()

    def update_schedule_next_run(self, schedule_id: int):
        """Update the next run time for a schedule."""
        schedule = self.get_schedule(schedule_id)
        if schedule:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE schedules SET next_run = ? WHERE id = ?",
                (next_run_from_now(schedule["frequency_minutes"]), schedule_id),
            )
            conn.commit()
            conn.close()

    # ==================== DATA OPERATIONS ====================

    def save_run(
        self,
        session_id: int,
        data: Any,
        status: str = "success",
        error: str | None = None,
        duration_ms: int | None = None,
        triggered_by: str | None = None,
    ) -> int:
        """Save one run of a session. A failed run has status "failed", its error and data []."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO extracted_data (session_id, data, status, error, duration_ms, triggered_by, items_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (session_id, json.dumps(data), status, error, duration_ms, triggered_by, len(data)),
        )

        data_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return data_id

    def get_session_data(self, session_id: int, limit: int = 10) -> list[dict]:
        """Get extracted data for a session."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT ed.*, s.row_table IS NOT NULL as has_table
            FROM extracted_data ed
            JOIN sessions s ON ed.session_id = s.id
            WHERE ed.session_id = ?
            ORDER BY ed.extracted_at DESC
            LIMIT ?
        """,
            (session_id, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        data_list = []
        for row in rows:
            data_list.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "data": json.loads(row["data"]),
                    "has_table": bool(row["has_table"]),
                    "extracted_at": row["extracted_at"],
                    **run_outcome_fields(row),
                }
            )

        return data_list

    def get_extraction(self, data_id: int) -> dict | None:
        """Get one extraction with its session's name."""
        return self._read_one_extraction("WHERE ed.id = ?", (data_id,))

    def get_latest_successful_extraction(self, session_id: int) -> dict | None:
        """Get a session's newest successful run with its session's name, or None if it has none."""
        return self._read_one_extraction(
            "WHERE ed.session_id = ? AND ed.status = 'success' ORDER BY ed.extracted_at DESC, ed.id DESC",
            (session_id,),
        )

    def _read_one_extraction(self, filter_and_order_sql: str, filter_values: tuple) -> dict | None:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT ed.*, s.name as session_name
            FROM extracted_data ed
            JOIN sessions s ON ed.session_id = s.id
            {filter_and_order_sql}
            LIMIT 1
        """,
            filter_values,
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "session_name": row["session_name"],
            "data": json.loads(row["data"]),
            "extracted_at": row["extracted_at"],
            **run_outcome_fields(row),
        }

    def get_all_data(self, limit: int = 50) -> list[dict]:
        """Get all extracted data across all sessions."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT ed.*, s.name as session_name, s.row_table IS NOT NULL as has_table
            FROM extracted_data ed
            JOIN sessions s ON ed.session_id = s.id
            ORDER BY ed.extracted_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        data_list = []
        for row in rows:
            data_list.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "session_name": row["session_name"],
                    "data": json.loads(row["data"]),
                    "has_table": bool(row["has_table"]),
                    "extracted_at": row["extracted_at"],
                    **run_outcome_fields(row),
                }
            )

        return data_list

    def get_run_summaries(self, limit: int = 50) -> list[dict]:
        """Get the newest runs across all sessions without their data, which can be large."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT ed.id, ed.session_id, ed.extracted_at, ed.status, ed.error, ed.duration_ms,
                   ed.triggered_by, ed.items_count,
                   s.name as session_name
            FROM extracted_data ed
            JOIN sessions s ON ed.session_id = s.id
            ORDER BY ed.extracted_at DESC, ed.id DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "session_name": row["session_name"],
                "extracted_at": row["extracted_at"],
                "items_count": row["items_count"],
                **run_outcome_fields(row),
            }
            for row in rows
        ]

    def get_run_stats(self, since_hours: int = 24) -> dict:
        """Count the runs, failed runs and extracted items of the last since_hours hours."""
        conn = self._connect()
        cursor = conn.cursor()

        # extracted_at is SQLite's CURRENT_TIMESTAMP, UTC text, so the cutoff is computed in SQLite too.
        cursor.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(status = 'failed'), 0),
                   COALESCE(SUM(items_count), 0)
            FROM extracted_data
            WHERE extracted_at >= datetime('now', ?)
        """,
            (f"-{since_hours} hours",),
        )

        runs, failed_runs, items_extracted = cursor.fetchone()
        conn.close()

        return {"runs": runs, "failed_runs": failed_runs, "items_extracted": items_extracted}
