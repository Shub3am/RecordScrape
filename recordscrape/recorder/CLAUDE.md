# recordscrape/recorder

## Owns

Recording one browsing session: opening a browser through `recordscrape/browsers/`, injecting the page script into every document, and turning what the user does into a list of steps with selectors.

## Must not know about

Storage, Flask, the scheduler, the worker thread or which backend is in use. Callers run its coroutines on the worker and persist what `stop()` returns.

## Entry points

`SessionRecorder(browser_config)` from `recordscrape.recorder`. `await start(url)` opens the browser and keeps it open, `await stop()` closes it and returns `{"url", "actions"}`. The `.js` files are page code, not Python modules; `recorder_script.py` joins them into one init script.

## Invariants and gotchas

- The page script runs on every document through `add_init_script` and reports through one exposed binding, so actions survive navigation. It never uses the console, which Patchright disables.
- Messages sent before the binding exists wait in a queue until the `BINDINGS_READY_EVENT` from `recordscrape/browsers/`. A document that navigates away before that loses its queued messages.
- The `.js` files declare plain functions and share one wrapping function scope. They must not add globals to the page; the binding is the only name the page can see.
- Only the top document is recorded. Clicks inside iframes and elements inside shadow roots get no usable selector.
- Every action's `selector` is the most stable unique selector at record time, and `fallbackSelectors` holds up to two more. The last one is a structural path that always exists but breaks when the layout shifts.
- Typing sends one input per keystroke; consecutive inputs on the same selector collapse into the final value. Password fields are recorded in plain text, as the old recorder did.
- Timestamps are Python `time.time()` seconds, taken when the message arrives.
- Actions from popups and new tabs are recorded in the same list with no page marker.
- `start()` closes the browser itself if it fails part way. After a successful `start()`, only `stop()` closes it.

## Who calls it

Nothing yet. `app.py` will drive it through the worker once the Selenium recorder in `vpr/` is removed.
