# recordscrape/runner

## Owns

Running a recorded session headless: opening a browser through `recordscrape/browsers/`, loading the session's start URL and reading the current value of every picked element.

## Must not know about

Storage, Flask, the scheduler, the worker thread, the recorder's page scripts or which backend is in use. Callers run `run_session` on the worker and persist its result.

## Entry points

`await run_session(browser_config, recorded_session)` from `recordscrape.runner`. `recorded_session` is the dict `SessionRecorder.stop()` returns, or a session row from `vpr/storage.py`; only `url` and `selectors` are read.

## Invariants and gotchas

- The result has the same shape as vpr's `SessionReplayer`: `{"success", "url", "data", "timestamp", "items_count"}`, or `{"success": False, "error", "timestamp"}`. The scheduler and the dashboard read these keys.
- Only Playwright and Patchright errors become `success: False`. Any other exception is a bug and raises.
- Recorded actions are not replayed yet, exactly as vpr. Pages that need a click or a login before the data shows extract nothing.
- Each picked element waits up to `PICKED_ELEMENT_WAIT_MS` for any of its selectors to attach, then reads the first selector in order that matches. Elements are read concurrently, so any number of missing elements cost one full wait together and yield no rows.
- Every row carries the element's primary `selector`, even when a fallback matched, because the dashboard labels rows by it.
- Values follow Selenium's reads so vpr sessions extract the same data: `textContent` is `innerText`, and other attributes read the DOM property first, so `href` and `src` are absolute URLs. Empty values are dropped.
- `fallbackSelectors` is optional because sessions recorded under vpr lack it.

## Who calls it

`vpr/scheduler.py`, through the worker, for both scheduled runs (always headless) and the dashboard's manual replay (visible unless the user ticks headless).
