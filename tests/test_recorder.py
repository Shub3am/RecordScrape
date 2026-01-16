"""
Tests for the recorder, run headless against a local fixture site on every backend.
They pin what later steps build on: actions survive navigation, typing becomes one step per field,
selectors fall back from stable to structural, picking never acts on the page, and the browser never
outlives the recording.
"""

import asyncio

import pytest

from recordscrape.browsers import BROWSER_ERRORS, BrowserConfig, open_browser_context
from recordscrape.recorder import SessionRecorder
from recordscrape.recorder.recorder_script import read_page_script
from recordscrape.runner import run_session
from tests.fixture_site import serve_fixture_pages

FIXTURE_PAGES = {
    "/form": '<title>Form</title><input name="query"><a id="to-results" href="/results">go</a>',
    "/results": (
        '<title>Results</title><button data-testid="save-result">save</button>'
        '<div style="height: 3000px"></div>'
    ),
    "/listing": (
        '<title>Listing</title><h1 class="headline">Deals</h1>'
        '<a id="deal-link" href="/form">deal</a>'
    ),
    "/options": '<title>Options</title><label><input type="checkbox" id="gift"> gift wrap</label>',
    "/cards": (
        '<title>Cards</title><ul class="results">'
        '<li class="card"><h2 class="name">Shoe</h2><span class="price">$40</span></li>'
        '<li class="card"><h2 class="name">Hat</h2><span class="price">$15</span></li>'
        '<li class="card"><h2 class="name">Sock</h2><span class="price">$5</span></li>'
        '</ul><p id="footer">footer</p>'
    ),
    "/tags": '<title>Tags</title><ul class="tags"><li>red</li><li>blue</li><li>green</li></ul>',
}
CARD_NAME_COLUMN = {
    "name": "name",
    "selector": "h2.name",
    "fallbackSelectors": [":scope > h2:nth-of-type(1)"],
    "attribute": "textContent",
}

ALL_BACKENDS = ["chromium", "patchright"]


@pytest.fixture(scope="module")
def fixture_site_url():
    with serve_fixture_pages(FIXTURE_PAGES) as site_url:
        yield site_url


async def wait_until(condition, timeout_seconds=5):
    async with asyncio.timeout(timeout_seconds):
        while not condition():
            await asyncio.sleep(0.05)


def without_timestamps(recorded_actions):
    return [
        {key: value for key, value in action.items() if key != "timestamp"}
        for action in recorded_actions
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_actions_are_recorded_across_navigation(backend, fixture_site_url):
    async def record_search_then_save():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/form")
        page = recorder.active_page
        await page.locator("input").press_sequentially("shoes")
        await page.click("#to-results")
        await page.wait_for_url("**/results")
        await page.click("button")
        await page.evaluate("() => window.scrollTo(0, 500)")
        await wait_until(lambda: recorder.recorded_actions[-1]["type"] == "scroll")
        return await recorder.stop()

    recorded_session = asyncio.run(record_search_then_save())

    assert recorded_session["url"] == f"{fixture_site_url}/form"
    assert without_timestamps(recorded_session["actions"]) == [
        {"type": "navigate", "url": f"{fixture_site_url}/form"},
        {
            "type": "input",
            "selector": 'input[name="query"]',
            "fallbackSelectors": ["html > body:nth-of-type(1) > input:nth-of-type(1)"],
            "value": "shoes",
        },
        {
            "type": "click",
            "selector": "#to-results",
            "fallbackSelectors": ["html > body:nth-of-type(1) > a:nth-of-type(1)"],
        },
        {
            "type": "click",
            "selector": '[data-testid="save-result"]',
            "fallbackSelectors": ["html > body:nth-of-type(1) > button:nth-of-type(1)"],
        },
        {"type": "scroll", "x": 0, "y": 500},
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_checkbox_input_records_its_checked_state(backend, fixture_site_url):
    async def record_label_click():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/options")
        await recorder.active_page.click("label")
        await wait_until(lambda: recorder.recorded_actions[-1]["type"] == "input")
        return await recorder.stop()

    recorded_session = asyncio.run(record_label_click())

    checkbox_input = recorded_session["actions"][-1]
    assert checkbox_input["selector"] == "#gift"
    assert checkbox_input["value"] == "on"
    assert checkbox_input["checked"] is True


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_picker_collects_elements_without_acting_on_the_page(backend, fixture_site_url):
    async def pick_headline_and_link_then_follow_link():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/listing")
        page = recorder.active_page
        await recorder.activate_picker()
        await page.click("h1")
        await page.click("#deal-link")
        await wait_until(lambda: len(recorder.picked_elements) == 2)
        url_while_picking = page.url
        await page.click("#recordscrape-picker-done")
        headline_style_after_done = await page.locator("h1").get_attribute("style")
        await page.click("#deal-link")
        await page.wait_for_url("**/form")
        await wait_until(lambda: recorder.recorded_actions[-1]["type"] == "click")
        return url_while_picking, headline_style_after_done, await recorder.stop()

    url_while_picking, headline_style_after_done, recorded_session = asyncio.run(
        pick_headline_and_link_then_follow_link()
    )

    assert url_while_picking == f"{fixture_site_url}/listing"
    assert headline_style_after_done is None
    assert recorded_session["selectors"] == [
        {
            "selector": "h1.headline",
            "fallbackSelectors": ["html > body:nth-of-type(1) > h1:nth-of-type(1)"],
            "tagName": "H1",
            "attribute": "textContent",
            "preview": "Deals...",
        },
        {
            "selector": "#deal-link",
            "fallbackSelectors": ["html > body:nth-of-type(1) > a:nth-of-type(1)"],
            "tagName": "A",
            "attribute": "href",
            "preview": "deal...",
        },
    ]
    assert without_timestamps(recorded_session["actions"]) == [
        {"type": "navigate", "url": f"{fixture_site_url}/listing"},
        {
            "type": "click",
            "selector": "#deal-link",
            "fallbackSelectors": ["html > body:nth-of-type(1) > a:nth-of-type(1)"],
        },
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_stop_closes_the_browser(backend, fixture_site_url):
    async def record_then_stop():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/form")
        browser = recorder.active_page.context.browser
        await recorder.stop()
        return browser

    assert not asyncio.run(record_then_stop()).is_connected()


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_failed_start_closes_the_browser(backend):
    async def start_on_unreachable_url():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        with pytest.raises(BROWSER_ERRORS):
            await recorder.start("http://127.0.0.1:1/")
        return recorder.active_page.context.browser

    assert not asyncio.run(start_on_unreachable_url()).is_connected()


def build_selectors_on_page(page_body, target_selector, build_selectors_call):
    """Runs selector_builder.js on the target element; `build_selectors_call` sees it as `element`."""
    selector_builder_script = read_page_script("selector_builder.js")
    build_selectors_for_element = (
        f"(element) => {{ {selector_builder_script} return {build_selectors_call}; }}"
    )

    async def build_selectors_for_target():
        async with open_browser_context(BrowserConfig(backend="chromium")) as browser_context:
            page = await browser_context.new_page()
            await page.set_content(page_body)
            return await page.locator(target_selector).evaluate(build_selectors_for_element)

    return asyncio.run(build_selectors_for_target())


@pytest.mark.parametrize(
    ("page_body", "target_selector", "expected_selectors"),
    [
        (
            '<button data-testid="save" id="save-button" class="primary">save</button>',
            "button",
            [
                '[data-testid="save"]',
                "#save-button",
                "button.primary",
            ],
        ),
        (
            '<div id="item:1">x</div>',
            "div",
            ["#item\\:1", "html > body:nth-of-type(1) > div:nth-of-type(1)"],
        ),
        (
            '<ul><li class="row">a</li><li class="row">b</li></ul>',
            "li >> nth=1",
            ["html > body:nth-of-type(1) > ul:nth-of-type(1) > li:nth-of-type(2)"],
        ),
        (
            '<div id="results"><p>a</p><p>b</p></div>',
            "p >> nth=1",
            ["#results > p:nth-of-type(2)"],
        ),
    ],
    ids=["test-id-first", "escaped-id", "duplicate-class", "id-anchored-path"],
)
def test_selector_builder_orders_unique_selectors(page_body, target_selector, expected_selectors):
    built_selectors = build_selectors_on_page(page_body, target_selector, "buildSelectors(element)")

    assert built_selectors == expected_selectors


def test_selector_builder_with_a_root_builds_selectors_relative_to_it():
    built_selectors = build_selectors_on_page(
        '<ul><li><h2 id="first" class="name">a</h2></li><li><h2 class="name">b</h2></li></ul>',
        "#first",
        "buildSelectors(element, element.closest('li'))",
    )

    assert built_selectors == ["h2.name", ":scope > h2:nth-of-type(1)"]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_row_picker_records_a_table_that_replays_into_records(backend, fixture_site_url):
    async def pick_rows_then_replay():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/cards")
        page = recorder.active_page
        await recorder.activate_row_picker()
        await page.locator("h2").nth(0).click()
        await page.locator("h2").nth(1).click()
        await page.click("#footer")
        await page.locator(".price").nth(2).click()
        await wait_until(lambda: recorder.row_table and len(recorder.row_table["columns"]) == 2)
        await page.click("#recordscrape-picker-done")
        recorded_session = await recorder.stop()
        return recorded_session, await run_session(BrowserConfig(backend=backend), recorded_session)

    recorded_session, run_result = asyncio.run(pick_rows_then_replay())

    assert recorded_session["table"] == {
        "rowSelector": "ul.results > li.card",
        "rowFallbackSelectors": ["html > body:nth-of-type(1) > ul:nth-of-type(1) > li.card"],
        "columns": [
            CARD_NAME_COLUMN,
            {
                "name": "price",
                "selector": "span.price",
                "fallbackSelectors": [":scope > span:nth-of-type(1)"],
                "attribute": "textContent",
            },
        ],
    }
    assert without_timestamps(recorded_session["actions"]) == [
        {"type": "navigate", "url": f"{fixture_site_url}/cards"}
    ]
    assert run_result["data"] == [
        {"name": "Shoe", "price": "$40"},
        {"name": "Hat", "price": "$15"},
        {"name": "Sock", "price": "$5"},
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_row_picker_takes_whole_rows_as_a_column(backend, fixture_site_url):
    async def pick_two_list_items_then_replay():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/tags")
        page = recorder.active_page
        await recorder.activate_row_picker()
        await page.locator("li").nth(0).click()
        await page.locator("li").nth(1).click()
        await wait_until(lambda: recorder.row_table is not None)
        await page.click("#recordscrape-picker-done")
        recorded_session = await recorder.stop()
        return recorded_session, await run_session(BrowserConfig(backend=backend), recorded_session)

    recorded_session, run_result = asyncio.run(pick_two_list_items_then_replay())

    assert recorded_session["table"] == {
        "rowSelector": "ul.tags > li",
        "rowFallbackSelectors": ["html > body:nth-of-type(1) > ul:nth-of-type(1) > li"],
        "columns": [
            {
                "name": "column_1",
                "selector": ":scope",
                "fallbackSelectors": [],
                "attribute": "textContent",
            }
        ],
    }
    assert run_result["data"] == [
        {"column_1": "red"},
        {"column_1": "blue"},
        {"column_1": "green"},
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_row_picker_refuses_a_second_example_from_the_same_row(backend, fixture_site_url):
    async def pick_twice_in_one_row_then_in_another():
        recorder = SessionRecorder(BrowserConfig(backend=backend))
        await recorder.start(f"{fixture_site_url}/cards")
        page = recorder.active_page
        await recorder.activate_row_picker()
        await page.locator("h2").nth(0).click()
        await page.locator(".price").nth(0).click()
        await page.get_by_text("Not a field inside another row").wait_for()
        table_after_refusal = recorder.row_table
        await page.locator("h2").nth(1).click()
        await wait_until(lambda: recorder.row_table is not None)
        return table_after_refusal, await recorder.stop()

    table_after_refusal, recorded_session = asyncio.run(pick_twice_in_one_row_then_in_another())

    assert table_after_refusal is None
    assert recorded_session["table"]["rowSelector"] == "ul.results > li.card"
    assert recorded_session["table"]["columns"] == [CARD_NAME_COLUMN]
