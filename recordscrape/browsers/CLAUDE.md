# recordscrape/browsers

## Owns

Turning a `BrowserConfig` into an open Playwright-API `BrowserContext` for one backend, and closing it again. Each backend file owns its library's launch call and its library's quirks.

## Must not know about

The recorder, the runner, flows, storage, Flask, the scheduler or the worker thread. Callers run these coroutines on the worker; this module does not know that.

## Entry points

`open_browser_context(config)` from `recordscrape.browsers`, used as `async with`. Leaving the block closes the browser and stops that library's driver. `BINDINGS_READY_EVENT` is the DOM event name page scripts listen for.

## Invariants and gotchas

- Each open context starts its own driver process and browser. There is no sharing between contexts.
- Chromium and Patchright contexts are different Python classes with the same API. Use the API, never `isinstance`.
- Patchright only makes `expose_binding` callables reachable in a document's main world after a main-world evaluate on that document (patchright#207). The Patchright backend runs one on every page's `domcontentloaded`, and once more when the page first appears, then dispatches `BINDINGS_READY_EVENT` on `window`. Page scripts must call a binding directly if it is a function, or else wait for that event. The event can fire more than once for one document, so listeners must tolerate repeats.
- A popup can reach Patchright's `page` event after its first document has already loaded, which is why the page is announced when it appears as well as on each load. Without that, roughly one popup in seven is never announced.
- An event queued on a document that navigates away before its announcement runs is lost.
- Patchright injects init scripts through request routes, so they do not run on `about:blank`. Stock Chromium does run them there.
- Patchright disables the console API, so `page.on("console")` never fires on that backend.
- Both backends launch the bundled Chromium build, not Google Chrome. Patchright recommends `channel="chrome"` for stealth; that option does not exist yet.
- Tests need browsers installed: `uv run playwright install chromium` and `uv run patchright install chromium`.

## Who calls it

`recordscrape/recorder/` opens its recording context here. The runner will too. Both run on the worker from `recordscrape/worker/`.
