"""
Tests for the browser backends, run headless against a local fixture site.
They pin the contract the recorder builds on: every backend opens a usable context, page scripts can
reach exposed bindings on every document, and leaving the context closes the browser.
"""

import asyncio
import http.server
import logging
import threading

import pytest

from recordscrape.browsers import BINDINGS_READY_EVENT, BrowserConfig, open_browser_context

FIXTURE_PAGES = {
    "/first": '<title>First</title><a id="to-second" href="/second">second</a>',
    "/second": '<title>Second</title><a id="to-third" href="/third" target="_blank">third</a>',
    "/third": "<title>Third</title>",
}

REPORT_DOCUMENT_SCRIPT = f"""
(() => {{
  const reportDocument = () => window.__reportDocument(location.pathname);
  if (typeof window.__reportDocument === 'function') {{
    reportDocument();
  }} else {{
    window.addEventListener('{BINDINGS_READY_EVENT}', reportDocument, {{once: true}});
  }}
}})();
"""

ALL_BACKENDS = ["chromium", "patchright"]


class FixturePageHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path not in FIXTURE_PAGES:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<!doctype html><html>{FIXTURE_PAGES[self.path]}</html>".encode())


@pytest.fixture(scope="module")
def fixture_site_url():
    fixture_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixturePageHandler)
    threading.Thread(target=fixture_server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{fixture_server.server_address[1]}"
    fixture_server.shutdown()
    fixture_server.server_close()


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_context_loads_a_page(backend, fixture_site_url):
    async def read_first_page_title():
        async with open_browser_context(BrowserConfig(backend=backend)) as browser_context:
            page = await browser_context.new_page()
            await page.goto(f"{fixture_site_url}/first")
            return await page.title()

    assert asyncio.run(read_first_page_title()) == "First"


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_page_scripts_reach_exposed_bindings_on_every_document(backend, fixture_site_url, caplog):
    async def collect_reported_documents():
        reported_paths = []
        popup_reported = asyncio.Event()

        def record_document(source, path):
            reported_paths.append(path)
            if path == "/third":
                popup_reported.set()

        async with open_browser_context(BrowserConfig(backend=backend)) as browser_context:
            await browser_context.expose_binding("__reportDocument", record_document)
            await browser_context.add_init_script(REPORT_DOCUMENT_SCRIPT)
            page = await browser_context.new_page()
            await page.goto(f"{fixture_site_url}/first")
            await page.click("#to-second")
            await page.wait_for_url("**/second")
            async with browser_context.expect_page() as popup_opened:
                await page.click("#to-third")
            popup = await popup_opened.value
            await popup.wait_for_load_state()
            await asyncio.wait_for(popup_reported.wait(), timeout=5)
        # Stock Chromium also runs init scripts on a new tab's about:blank, Patchright does not.
        return [path for path in reported_paths if path != "blank"]

    assert asyncio.run(collect_reported_documents()) == ["/first", "/second", "/third"]
    assert [record for record in caplog.records if record.levelno >= logging.ERROR] == []


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_leaving_the_context_closes_the_browser(backend):
    async def open_then_leave_context():
        async with open_browser_context(BrowserConfig(backend=backend)) as browser_context:
            browser = browser_context.browser
            assert browser.is_connected()
        return browser

    assert not asyncio.run(open_then_leave_context()).is_connected()
