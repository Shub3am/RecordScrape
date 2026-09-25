# recordscrape/recorder

## Owns

Recording one browsing session: opening a browser through `recordscrape/browsers/`, injecting the page script into every document, and turning what the user does into a list of steps with selectors, plus the list of elements the user picks for extraction.

## Must not know about

Storage, Flask, the scheduler, the worker thread or which backend is in use. Callers run its coroutines on the worker and persist what `stop()` returns.

## Entry points

`SessionRecorder(browser_config)` from `recordscrape.recorder`. `await start(url)` opens the browser and keeps it open, `await activate_picker()` opens the element picker on the page the user last acted on and returns at once, and `await stop()` closes the browser and returns `{"url", "actions", "selectors"}`. The `.js` files are page code, not Python modules; `recorder_script.py` joins them into one init script.

## Invariants and gotchas

- The page script runs on every document through `add_init_script` and reports through one exposed binding, so actions survive navigation. It never uses the console, which Patchright disables.
- Messages sent before the binding exists wait in a queue until the `BINDINGS_READY_EVENT` from `recordscrape/browsers/`. A document that navigates away before that loses its queued messages.
- The `.js` files declare plain functions and share one wrapping function scope. They must not add globals to the page; the binding is the only name the page can see.
- Only the top document is recorded. Clicks inside iframes and elements inside shadow roots get no usable selector.
- Every action's `selector` is the most stable unique selector at record time, and `fallbackSelectors` holds up to two more. The last one is a structural path that always exists but breaks when the layout shifts.
- Typing sends one input per keystroke; consecutive inputs on the same selector collapse into the final value. Password fields are recorded in plain text, as the old recorder did.
- Checkbox and radio inputs also carry `checked`, the state after the event. Clicking a label records a click on the label and another on its checkbox, so replaying clicks alone toggles it twice; replay settles it from `checked`. No other input has the key.
- Contenteditable elements have no `value`, so their input actions carry `value: None` and cannot be replayed.
- Timestamps are Python `time.time()` seconds, taken when the message arrives.
- Actions from popups and new tabs are recorded in the same list with no page marker.
- The picker must be installed before action capture. Its window capture-phase listeners run first and stop every picking click, so the page and action capture never see it.
- Each pick is sent the moment it is clicked, not when the user presses Done. Closing the browser without Done keeps the picks.
- The picker panel is appended to the end of `body`, so structural selectors of page elements do not shift. It is built with DOM calls because pages that enforce Trusted Types reject `innerHTML`.
- Marked elements are outlined through the `style` attribute, never `element.style`: Chromium writes `element.style` to the attribute lazily, and removing the attribute before that write leaves `style=""` behind.
- `start()` closes the browser itself if it fails part way. After a successful `start()`, only `stop()` closes it.

## Who calls it

`app.py`, through the worker: one recorder at a time, opened visible, from the start, selector and stop routes.
