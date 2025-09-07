"""
Runs every browser coroutine on one dedicated thread that owns one asyncio event loop.
Playwright objects are bound to the loop that created them, so Flask request threads and scheduler
threads hand coroutines to this worker instead of driving a browser themselves.
Must not import Playwright or know about backends, flows or storage.
"""

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

CoroutineResult = TypeVar("CoroutineResult")


class BrowserWorker:
    """Owns the event loop thread that every browser coroutine runs on. Starts on construction."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        # Daemon so a process that exits without calling stop() is not held open by the loop.
        self._thread = threading.Thread(target=self._run_loop, name="browser-worker", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(
        self, coroutine: Coroutine[Any, Any, CoroutineResult]
    ) -> concurrent.futures.Future[CoroutineResult]:
        """Schedule a coroutine on the worker loop and return a future the caller can wait on."""
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def stop(self) -> None:
        """Cancel every running coroutine so its cleanup runs, then end the worker thread."""
        asyncio.run_coroutine_threadsafe(self._cancel_running_tasks(), self._loop).result()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
        self._loop.close()

    async def _cancel_running_tasks(self) -> None:
        # Mirrors asyncio.run's shutdown: cancelled tasks get to run their finally blocks,
        # which is where browsers and Playwright drivers are closed.
        shutdown_task = asyncio.current_task()
        running_tasks = [task for task in asyncio.all_tasks() if task is not shutdown_task]
        for task in running_tasks:
            task.cancel()
        await asyncio.gather(*running_tasks, return_exceptions=True)
        await self._loop.shutdown_asyncgens()
