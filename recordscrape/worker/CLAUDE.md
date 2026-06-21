# recordscrape/worker

## Owns

The single thread and asyncio event loop that every browser coroutine runs on. Playwright objects are bound to the loop that created them, so no other thread may touch a page, context or browser directly.

## Must not know about

Playwright, backends, flows, storage, Flask or the scheduler. It runs coroutines and nothing else.

## Entry points

`BrowserWorker` from `recordscrape.worker`. `submit(coroutine)` returns a `concurrent.futures.Future`, and `stop()` shuts the loop down.

## Invariants and gotchas

- The thread starts in the constructor. Build one worker per process.
- Never call `submit(...).result()` from inside a coroutine already running on the worker. The loop blocks waiting on itself and deadlocks.
- A coroutine that blocks synchronously (a `time.sleep`, a sync library call) stalls every other browser task, because they share one loop.
- `stop()` cancels every running coroutine and waits for its `finally` blocks, so browser cleanup belongs in `finally` or `async with`. A cleanup that hangs makes `stop()` hang.
- The thread is a daemon, so a process that skips `stop()` still exits, but without that cleanup.
- After `stop()` the loop is closed and `submit` raises `RuntimeError`.

## Who calls it

Nothing yet. The browser backends, recorder and runner will submit through it, and `app.py` and the scheduler will own the single instance.
