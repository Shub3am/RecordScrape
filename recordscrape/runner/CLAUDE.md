# recordscrape/runner

## Owns

Running a recorded session: opening a browser through `recordscrape/browsers/`, loading the session's start URL, replaying its recorded clicks, inputs and scrolls, and reading the current value of every picked element and of its row table.

## Must not know about

Storage, Flask, the scheduler, the worker thread, the recorder's page scripts or which backend is in use. Callers run `run_session` on the worker and persist its result.

## Entry points

`await run_session(browser_config, recorded_session)` from `recordscrape.runner`. `recorded_session` is the dict `SessionRecorder.stop()` returns, or a session row from `vpr/storage.py`; only `url`, `actions`, `selectors` and `table` are read, and all four must be present.

## Invariants and gotchas

- The result has the same shape as vpr's `SessionReplayer`: `{"success", "url", "data", "timestamp", "items_count"}`, or `{"success": False, "error", "timestamp"}`. The scheduler and the dashboard read these keys.
- Only Playwright and Patchright errors, and a step that matches nothing (`RecordedStepFailed`), become `success: False`. Any other exception is a bug and raises.
- Steps replay in recorded order, each waiting up to `STEP_TARGET_WAIT_MS` for any of its selectors. A step that matches nothing stops the run, because extracting from the wrong page would save wrong rows as if they were right. The error names the step's position in `actions`, counting from 1.
- There are no fixed sleeps. `click()` waits for a navigation it starts to begin loading, the next step's selector wait covers the rest, and a scroll waits for the page's load event first. After scrolling it waits one animation frame, because browsers run the page's scroll listeners on the next frame and lazy-loading pages start from them; reading earlier sees the page before it reacted.
- `navigate` steps are skipped: the recorder only records the start URL, which is opened before replay.
- An input whose `checked` is true or false is replayed with `set_checked`, which settles the double toggle a label click records. A `<select>` gets `select_option`, and anything else gets `fill`.
- Sessions recorded under vpr are not replayed, only opened at their start URL as before. vpr's clicks include its own overlay, which no longer exists. `recorded_by_vpr` from `recordscrape/flows/` recognises them, so export and replay agree on which sessions those are.
- All steps run on the first tab. A click that opens a popup or new tab leaves later steps on the original page, and they fail there.
- Each picked element waits up to `PICKED_ELEMENT_WAIT_MS` for any of its selectors to attach, then reads the first selector in order that matches. Elements are read concurrently, so any number of missing elements cost one full wait together and yield no rows.
- Every row carries the element's primary `selector`, even when a fallback matched, because the dashboard labels rows by it.
- Values follow Selenium's reads so vpr sessions extract the same data: `textContent` is `innerText`, and other attributes read the DOM property first, so `href` and `src` are absolute URLs. Empty values are dropped.
- `fallbackSelectors` is optional because sessions recorded under vpr lack it.
- With a row table, `data` is one record per matched row, keyed by column name, instead of the flat rows above. Rows are waited on like picked elements; cells are read the moment rows attach, with no wait of their own. A column that matches nothing in a row reads `""`, and a row whose every value is empty is dropped.
- Column selectors run through the row's own `querySelector`, so `:scope` means the row and a column reads the first match inside it. `querySelector` never returns the row itself, so a column selector that is exactly `:scope` reads the row instead.
- With a row table, each single picked element becomes a column keyed by its primary selector, holding its first value on every row. It overwrites a table column of the same name.

## Who calls it

`vpr/scheduler.py`, through the worker, for both scheduled runs (always headless) and the dashboard's manual replay (visible unless the user ticks headless).
