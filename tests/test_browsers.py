"""
Tests for the browser backends, run headless against a local fixture site.
They pin the contract the recorder builds on: every backend opens a usable context, page scripts can
reach exposed bindings on every document, and leaving the context closes the browser.
"""

import asyncio
import logging
import sys

import pytest

from recordscrape.browsers import (
    BINDINGS_READY_EVENT,
    BROWSER_ERRORS,
    BrowserConfig,
    open_browser_context,
)
from tests.fixture_proxy import serve_authenticating_proxy
from tests.fixture_site import find_closed_local_port, serve_fixture_pages
from tests.installed_backends import ALL_BACKENDS, RECORDING_BACKENDS

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


@pytest.fixture(scope="module")
def fixture_site_url():
    with serve_fixture_pages(FIXTURE_PAGES) as site_url:
        yield site_url


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_context_loads_a_page(backend, fixture_site_url):
    async def read_first_page_title():
        async with open_browser_context(BrowserConfig(backend=backend)) as browser_context:
            page = await browser_context.new_page()
            await page.goto(f"{fixture_site_url}/first")
            return await page.title()

    assert asyncio.run(read_first_page_title()) == "First"


@pytest.mark.parametrize("backend", RECORDING_BACKENDS)
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
def test_closing_right_after_a_failed_load_logs_no_error(backend, caplog):
    async def fail_a_load_then_leave_context():
        async with open_browser_context(BrowserConfig(backend=backend)) as browser_context:
            page = await browser_context.new_page()
            with pytest.raises(BROWSER_ERRORS):
                await page.goto(f"http://127.0.0.1:{find_closed_local_port()}/")

    for _ in range(3):
        asyncio.run(fail_a_load_then_leave_context())
    assert [record for record in caplog.records if record.levelno >= logging.ERROR] == []


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_leaving_the_context_closes_the_browser(backend):
    async def open_then_leave_context():
        async with open_browser_context(BrowserConfig(backend=backend)) as browser_context:
            browser = browser_context.browser
            assert browser.is_connected()
        return browser

    assert not asyncio.run(open_then_leave_context()).is_connected()


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_pages_load_through_an_authenticating_proxy(backend, fixture_site_url, monkeypatch):
    monkeypatch.setenv("FIXTURE_PROXY_PASS", "hunter2")

    async def read_title_through_proxy(proxy_url):
        browser_config = BrowserConfig(backend=backend, proxy=proxy_url)
        async with open_browser_context(browser_config) as browser_context:
            page = await browser_context.new_page()
            await page.goto("http://shop.test/first")
            return await page.title()

    with serve_authenticating_proxy("ana", "hunter2", {"shop.test": fixture_site_url}) as proxy:
        proxy_url = proxy.url_without_credentials.replace("://", "://ana:${FIXTURE_PROXY_PASS}@")
        page_title = asyncio.run(read_title_through_proxy(proxy_url))

    assert page_title == "First"
    assert "http://shop.test/first" in proxy.authenticated_urls


def test_human_like_input_is_refused_on_backends_without_it():
    with pytest.raises(ValueError, match="Human-like input needs one of these backends"):
        BrowserConfig(backend="patchright", humanize=True)


def test_cloakbrowser_without_its_extra_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "cloakbrowser", None)

    async def open_cloakbrowser():
        async with open_browser_context(BrowserConfig(backend="cloakbrowser")):
            pass

    with pytest.raises(ValueError, match="uv sync --extra cloakbrowser"):
        asyncio.run(open_cloakbrowser())


def test_cloakbrowser_clicks_with_human_like_input(fixture_site_url):
    pytest.importorskip("cloakbrowser")

    async def follow_link_with_humanize():
        browser_config = BrowserConfig(backend="cloakbrowser", humanize=True)
        async with open_browser_context(browser_config) as browser_context:
            page = await browser_context.new_page()
            await page.goto(f"{fixture_site_url}/first")
            await page.click("#to-second")
            await page.wait_for_url("**/second")
            return await page.title()

    assert asyncio.run(follow_link_with_humanize()) == "Second"
