# vpr

## Owns

Running recorded sessions on an interval, and persisting sessions, schedules and extracted data in SQLite. Recording and running a session live in `recordscrape/`.

## Must not know about

Flask, HTTP, request shapes or the dashboard. `app.py` translates between HTTP and this package.

## Entry points

`StorageManager` and `ScraperScheduler`, exported from `vpr/__init__.py`. Only `app.py` calls them.

## Invariants and gotchas

- `StorageManager` must open connections through `_connect()`, which turns on `PRAGMA foreign_keys`. A raw `sqlite3.connect` silently disables `ON DELETE CASCADE`.
- `ScraperScheduler` starts APScheduler in its constructor, so constructing it twice runs every job twice.
- `ScraperScheduler` runs sessions with `recordscrape/runner/` on the `BrowserWorker` it is given, blocking the APScheduler or request thread until the run ends. It never drives a browser itself.
- The DB path defaults to `scraper.db` in the current working directory.
- Sessions saved by the old Selenium recorder mix timestamp units: the first action is in Python seconds, the rest are JS milliseconds. Sessions recorded now use seconds throughout.
