# vpr

## Owns

The scraping engine: recording a session in a visible Chrome, replaying it to extract selected elements, running replays on an interval, and persisting sessions, schedules and extracted data in SQLite.

## Must not know about

Flask, HTTP, request shapes or the dashboard. `app.py` translates between HTTP and this package.

## Entry points

`SessionRecorder`, `SessionReplayer`, `StorageManager` and `ScraperScheduler`, exported from `vpr/__init__.py`. Only `app.py` calls them.

## Invariants and gotchas

- Replay opens the start URL and re-reads the saved selectors. Recorded actions are stored but not replayed, because the call in `replayer.py` is commented out.
- The recorder injects its tracking JS once. Actions on any page after a navigation are lost.
- The selector overlay runs in a thread that blocks for up to 300s waiting for "Done Selecting".
- `StorageManager` must open connections through `_connect()`, which turns on `PRAGMA foreign_keys`. A raw `sqlite3.connect` silently disables `ON DELETE CASCADE`.
- `ScraperScheduler` starts APScheduler in its constructor, so constructing it twice runs every job twice.
- `ScraperScheduler` runs sessions with `recordscrape/runner/` on the `BrowserWorker` it is given, blocking the APScheduler or request thread until the run ends. It never drives a browser itself.
- The DB path defaults to `scraper.db` in the current working directory.
- Replay uses fixed `sleep` waits and a 30s page load timeout.
- The recorder mixes timestamp units: the first action is in Python seconds, the rest are JS milliseconds.
