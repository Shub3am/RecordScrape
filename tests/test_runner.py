"""
Tests for the runner, run headless against a local fixture site on every backend.
They pin extraction parity with vpr's SessionReplayer: the same result shape and values, plus the
fallback selectors, waiting for late elements, and turning a browser failure into a failed result.
"""

import asyncio

import pytest

from recordscrape.browsers import BrowserConfig
from recordscrape.runner import run_session, session_runner
from tests.fixture_site import find_closed_local_port, serve_fixture_pages

FIXTURE_PAGES = {
    "/products": (
        '<title>Products</title><h2 class="name">Shoe</h2><h2 class="name">Hat</h2>'
        '<h2 class="name"> </h2><a id="buy" href="/buy">buy</a><input id="qty" value="3">'
        '<img id="logo" src="/logo.png">'
        "<script>setTimeout(() => {"
        " const lateParagraph = document.createElement('p');"
        " lateParagraph.id = 'late'; lateParagraph.textContent = 'Loaded';"
        " document.body.append(lateParagraph); }, 300);</script>"
    ),
}

ALL_BACKENDS = ["chromium", "patchright"]


@pytest.fixture(scope="module")
def fixture_site_url():
    with serve_fixture_pages(FIXTURE_PAGES) as site_url:
        yield site_url


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_picked_elements_are_extracted_like_vpr(backend, fixture_site_url, monkeypatch):
    monkeypatch.setattr(session_runner, "PICKED_ELEMENT_WAIT_MS", 1000)
    recorded_session = {
        "url": f"{fixture_site_url}/products",
        "actions": [],
        "selectors": [
            {"selector": "h2.name", "fallbackSelectors": [], "attribute": "textContent"},
            {"selector": "#renamed-link", "fallbackSelectors": ["#buy"], "attribute": "href"},
            {"selector": "#qty", "attribute": "value"},
            {"selector": "#logo", "fallbackSelectors": [], "attribute": "src"},
            {"selector": "#late", "fallbackSelectors": [], "attribute": "textContent"},
            {"selector": "#gone", "fallbackSelectors": [".also-gone"], "attribute": "textContent"},
        ],
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["success"] is True
    assert run_result["url"] == f"{fixture_site_url}/products"
    assert run_result["items_count"] == 6
    assert run_result["data"] == [
        {
            "selector": "h2.name",
            "value": "Shoe",
            "attribute": "textContent",
            "index": 0,
            "tag": "h2",
        },
        {
            "selector": "h2.name",
            "value": "Hat",
            "attribute": "textContent",
            "index": 1,
            "tag": "h2",
        },
        {
            "selector": "#renamed-link",
            "value": f"{fixture_site_url}/buy",
            "attribute": "href",
            "index": 0,
            "tag": "a",
        },
        {"selector": "#qty", "value": "3", "attribute": "value", "index": 0, "tag": "input"},
        {
            "selector": "#logo",
            "value": f"{fixture_site_url}/logo.png",
            "attribute": "src",
            "index": 0,
            "tag": "img",
        },
        {
            "selector": "#late",
            "value": "Loaded",
            "attribute": "textContent",
            "index": 0,
            "tag": "p",
        },
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_unreachable_url_gives_a_failed_result(backend):
    unreachable_url = f"http://127.0.0.1:{find_closed_local_port()}/"
    recorded_session = {"url": unreachable_url, "actions": [], "selectors": []}

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["success"] is False
    assert "ERR_CONNECTION_REFUSED" in run_result["error"]
    assert set(run_result) == {"success", "error", "timestamp"}
