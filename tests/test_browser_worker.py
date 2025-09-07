"""
Tests for BrowserWorker.
They pin the threading contract every browser module relies on: one loop thread, results and
errors come back through the future, and stop() lets running coroutines clean up.
"""

import asyncio
import threading
import time

import pytest

from recordscrape.worker import BrowserWorker


@pytest.fixture
def worker():
    browser_worker = BrowserWorker()
    yield browser_worker
    browser_worker.stop()


def test_submit_returns_the_coroutine_result(worker):
    async def add_two_numbers(first, second):
        return first + second

    assert worker.submit(add_two_numbers(2, 3)).result(timeout=2) == 5


def test_every_coroutine_runs_on_the_same_worker_thread(worker):
    async def current_thread_name():
        return threading.current_thread().name

    thread_names = {worker.submit(current_thread_name()).result(timeout=2) for _ in range(3)}

    assert thread_names == {"browser-worker"}


def test_coroutines_submitted_from_several_threads_share_one_loop(worker):
    async def current_loop():
        return asyncio.get_running_loop()

    loops_seen = []
    submitting_threads = [
        threading.Thread(
            target=lambda: loops_seen.append(worker.submit(current_loop()).result(timeout=2))
        )
        for _ in range(4)
    ]
    for submitting_thread in submitting_threads:
        submitting_thread.start()
    for submitting_thread in submitting_threads:
        submitting_thread.join()

    assert len(loops_seen) == 4
    assert len(set(loops_seen)) == 1


def test_waiting_coroutines_do_not_block_each_other(worker):
    async def wait_briefly():
        await asyncio.sleep(0.3)

    started_at = time.monotonic()
    futures = [worker.submit(wait_briefly()) for _ in range(3)]
    for future in futures:
        future.result(timeout=2)

    assert time.monotonic() - started_at < 0.6


def test_coroutine_error_is_raised_to_the_caller(worker):
    async def fail_to_launch():
        raise RuntimeError("browser failed to launch")

    with pytest.raises(RuntimeError, match="browser failed to launch"):
        worker.submit(fail_to_launch()).result(timeout=2)


def test_stop_cancels_running_coroutines_and_runs_their_cleanup():
    browser_worker = BrowserWorker()
    coroutine_started = threading.Event()
    cleanup_ran = threading.Event()

    async def hold_browser_open():
        try:
            coroutine_started.set()
            await asyncio.sleep(60)
        finally:
            cleanup_ran.set()

    pending_future = browser_worker.submit(hold_browser_open())
    assert coroutine_started.wait(timeout=2)

    browser_worker.stop()

    assert cleanup_ran.is_set()
    assert pending_future.cancelled()
    assert "browser-worker" not in {thread.name for thread in threading.enumerate()}
