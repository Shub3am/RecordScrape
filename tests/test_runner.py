"""
Tests for the runner, run headless against a local fixture site on every backend.
They pin extraction parity with vpr's SessionReplayer: the same result shape and values, plus the
fallback selectors, waiting for late elements, and turning a browser failure into a failed result.
They also pin that recorded steps replay before extraction, and that vpr sessions are not replayed.
"""

import asyncio

import pytest

from recordscrape.browsers import BrowserConfig
from recordscrape.runner import RunOptions, run_session, session_runner
from tests.fixture_site import find_closed_local_port, serve_fixture_pages
from tests.installed_backends import ALL_BACKENDS

SHOP_PAGES = [["Shoe", "Hat"], ["Boot", "Cap"], ["Sock", "Belt"]]

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
    "/search": (
        '<title>Search</title><h1>Search</h1><input id="query">'
        '<select id="size"><option value="S">Small</option><option value="M">Medium</option></select>'
        '<label><input type="checkbox" id="gift"> gift wrap</label>'
        '<button id="apply">apply</button><p id="summary"></p><a id="next" href="/details">next</a>'
        "<script>document.getElementById('apply').onclick = () => {"
        " document.getElementById('summary').textContent = ["
        " document.getElementById('query').value, document.getElementById('size').value,"
        " document.getElementById('gift').checked].join('|'); };</script>"
    ),
    "/cards": (
        '<title>Cards</title><h1>Catalog</h1><ul class="results">'
        '<li class="card"><h2 class="name">Shoe</h2><span class="price">$40</span>'
        '<a class="more" href="/shoe">more</a></li>'
        '<li class="card"><h2 class="name">Hat</h2><a class="more" href="/hat">more</a></li>'
        '<li class="card"><h2 class="name"> </h2></li></ul>'
    ),
    "/tags": '<title>Tags</title><ul class="tags"><li>red</li><li>blue</li></ul>',
    "/table": (
        "<title>Table</title><table><tbody>"
        "<tr><td>Shoe</td><td>40</td></tr><tr><td>Hat</td><td>15</td></tr>"
        "</tbody></table>"
    ),
    **{
        f"/shop?page={page_number}": (
            f"<title>Shop</title><h1>Shop page {page_number}</h1><ul class='results'>"
            + "".join(f"<li class='card'><h2 class='name'>{name}</h2></li>" for name in names)
            + "</ul>"
            + (
                ""
                if page_number == 3
                else f"<a class='next' href='/shop?page={page_number + 1}'>Next</a>"
            )
        )
        for page_number, names in enumerate(SHOP_PAGES, start=1)
    },
    # Renders each page into the same list after a short delay, like a pager fetching JSON, and
    # marks Next aria-disabled on the last page instead of removing it.
    "/pager": (
        "<title>Pager</title><ul class='results'></ul><button class='next'>Next</button>"
        f"<script>const pages = {SHOP_PAGES}; let pageIndex = 0;"
        " const list = document.querySelector('ul.results');"
        " const nextButton = document.querySelector('button.next');"
        " function renderPage() {"
        "  list.replaceChildren(...pages[pageIndex].map((name) => {"
        "   const card = document.createElement('li'); card.className = 'card';"
        "   card.innerHTML = `<h2 class='name'>${name}</h2>`; return card; }));"
        "  if (pageIndex === pages.length - 1) nextButton.setAttribute('aria-disabled', 'true'); }"
        " nextButton.onclick = () => { pageIndex += 1; setTimeout(renderPage, 100); };"
        " renderPage();</script>"
    ),
    # Appends three tall posts whenever the window reaches the bottom, until it holds nine.
    "/feed": (
        "<title>Feed</title><ul class='feed'></ul>"
        "<script>const feed = document.querySelector('ul.feed'); let loading = false;"
        " function appendPosts() { for (let post = 0; post < 3; post += 1) {"
        "  const item = document.createElement('li'); item.style.height = '400px';"
        "  item.textContent = `post ${feed.children.length + 1}`; feed.append(item); } }"
        " appendPosts();"
        " window.addEventListener('scroll', () => {"
        "  const atBottom = window.innerHeight + window.scrollY"
        "   >= document.documentElement.scrollHeight - 50;"
        "  if (loading || !atBottom || feed.children.length >= 9) return;"
        "  loading = true; setTimeout(() => { appendPosts(); loading = false; }, 100); });</script>"
    ),
    "/details": (
        '<title>Details</title><h1>Details</h1><p id="position">0</p><div style="height: 3000px"></div>'
        "<script>window.addEventListener('scroll', () => {"
        " document.getElementById('position').textContent = window.scrollY; });</script>"
    ),
}


def click_step(selector, *fallback_selectors):
    return {"type": "click", "selector": selector, "fallbackSelectors": list(fallback_selectors)}


def input_step(selector, value, *fallback_selectors):
    return {
        "type": "input",
        "selector": selector,
        "fallbackSelectors": list(fallback_selectors),
        "value": value,
    }


def picked_text(selector):
    return {"selector": selector, "fallbackSelectors": [], "attribute": "textContent"}


def table_column(name, selector, attribute="textContent", *fallback_selectors):
    return {
        "name": name,
        "selector": selector,
        "fallbackSelectors": list(fallback_selectors),
        "attribute": attribute,
    }


def paginated_card_session(page_url, table_pagination, picked_elements=()):
    return {
        "url": page_url,
        "actions": [],
        "selectors": list(picked_elements),
        "table": {
            "rowSelector": "ul.results > li.card",
            "rowFallbackSelectors": [],
            "columns": [table_column("name", "h2.name")],
            "pagination": table_pagination,
        },
    }


def next_button_pagination(selector, max_pages):
    return {
        "mode": "nextButton",
        "selector": selector,
        "fallbackSelectors": [],
        "maxPages": max_pages,
    }


def extracted_values(run_result):
    return [row["value"] for row in run_result["data"]]


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
        "table": None,
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
    recorded_session = {"url": unreachable_url, "actions": [], "selectors": [], "table": None}

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["success"] is False
    assert "ERR_CONNECTION_REFUSED" in run_result["error"]
    assert set(run_result) == {"success", "error", "timestamp"}


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_recorded_form_steps_are_replayed_before_extraction(backend, fixture_site_url):
    search_url = f"{fixture_site_url}/search"
    recorded_session = {
        "url": search_url,
        "actions": [
            {"type": "navigate", "url": search_url},
            input_step("#renamed-query", "shoes", "#query"),
            input_step("#size", "M"),
            # Clicking the label records the label click and the checkbox click it causes.
            click_step("label"),
            click_step("#gift"),
            {
                "type": "input",
                "selector": "#gift",
                "fallbackSelectors": [],
                "value": "on",
                "checked": True,
            },
            click_step("#apply"),
        ],
        "selectors": [picked_text("#summary")],
        "table": None,
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["success"] is True
    assert extracted_values(run_result) == ["shoes|M|true"]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_replay_follows_a_link_then_scrolls(backend, fixture_site_url):
    search_url = f"{fixture_site_url}/search"
    recorded_session = {
        "url": search_url,
        "actions": [
            {"type": "navigate", "url": search_url},
            click_step("#next"),
            {"type": "scroll", "x": 0, "y": 400},
        ],
        "selectors": [picked_text("h1"), picked_text("#position")],
        "table": None,
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["success"] is True
    assert extracted_values(run_result) == ["Details", "400"]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_step_that_matches_nothing_fails_the_run(backend, fixture_site_url, monkeypatch):
    monkeypatch.setattr(session_runner, "STEP_TARGET_WAIT_MS", 500)
    search_url = f"{fixture_site_url}/search"
    recorded_session = {
        "url": search_url,
        "actions": [
            {"type": "navigate", "url": search_url},
            click_step("#removed-button", ".also-removed"),
        ],
        "selectors": [picked_text("h1")],
        "table": None,
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["success"] is False
    assert run_result["error"] == "Step 2 (click #removed-button) matched nothing within 500 ms"


def test_sessions_recorded_under_vpr_only_open_the_start_url(fixture_site_url):
    search_url = f"{fixture_site_url}/search"
    recorded_session = {
        "url": search_url,
        "actions": [
            {"type": "navigate", "url": search_url, "timestamp": 1},
            {"type": "click", "selector": "#next", "timestamp": 2},
        ],
        "selectors": [{"selector": "h1", "attribute": "textContent"}],
        "table": None,
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend="chromium"), recorded_session))

    assert run_result["success"] is True
    assert extracted_values(run_result) == ["Search"]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_row_table_extracts_one_record_per_row_with_singles_as_columns(
    backend, fixture_site_url, monkeypatch
):
    monkeypatch.setattr(session_runner, "PICKED_ELEMENT_WAIT_MS", 1000)
    recorded_session = {
        "url": f"{fixture_site_url}/cards",
        "actions": [],
        "selectors": [picked_text("h1"), picked_text("#gone")],
        "table": {
            "rowSelector": "ul.results > li.card",
            "rowFallbackSelectors": [],
            "columns": [
                table_column("name", "h2.name"),
                table_column("price", "span.price"),
                table_column("link", "a.more", "href"),
            ],
        },
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["data"] == [
        {
            "name": "Shoe",
            "price": "$40",
            "link": f"{fixture_site_url}/shoe",
            "h1": "Catalog",
            "#gone": "",
        },
        {
            "name": "Hat",
            "price": "",
            "link": f"{fixture_site_url}/hat",
            "h1": "Catalog",
            "#gone": "",
        },
    ]
    assert run_result["items_count"] == 2


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_row_table_falls_back_through_row_and_column_selectors(backend, fixture_site_url):
    recorded_session = {
        "url": f"{fixture_site_url}/table",
        "actions": [],
        "selectors": [],
        "table": {
            "rowSelector": "tr.renamed",
            "rowFallbackSelectors": ["tbody > tr"],
            "columns": [
                table_column("name", "td.renamed", "textContent", ":scope > td:nth-of-type(1)"),
                table_column("price", ":scope > td:nth-of-type(2)"),
            ],
        },
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["data"] == [{"name": "Shoe", "price": "40"}, {"name": "Hat", "price": "15"}]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_row_table_column_at_scope_reads_the_row_itself(backend, fixture_site_url):
    recorded_session = {
        "url": f"{fixture_site_url}/tags",
        "actions": [],
        "selectors": [],
        "table": {
            "rowSelector": "ul.tags > li",
            "rowFallbackSelectors": [],
            "columns": [table_column("tag", ":scope")],
        },
    }

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["data"] == [{"tag": "red"}, {"tag": "blue"}]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_next_button_reads_every_page_with_singles_from_the_first(backend, fixture_site_url):
    recorded_session = paginated_card_session(
        f"{fixture_site_url}/shop?page=1",
        next_button_pagination("a.next", 10),
        [picked_text("h1")],
    )

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert run_result["data"] == [
        {"name": name, "h1": "Shop page 1"} for names in SHOP_PAGES for name in names
    ]
    assert run_result["items_count"] == 6


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_next_button_stops_at_max_pages(backend, fixture_site_url):
    recorded_session = paginated_card_session(
        f"{fixture_site_url}/shop?page=1", next_button_pagination("a.next", 2)
    )

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert [record["name"] for record in run_result["data"]] == ["Shoe", "Hat", "Boot", "Cap"]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_client_side_pager_stops_when_next_is_disabled(backend, fixture_site_url):
    recorded_session = paginated_card_session(
        f"{fixture_site_url}/pager", next_button_pagination("button.next", 10)
    )

    run_result = asyncio.run(run_session(BrowserConfig(backend=backend), recorded_session))

    assert [record["name"] for record in run_result["data"]] == [
        name for names in SHOP_PAGES for name in names
    ]


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_run_options_max_pages_overrides_the_sessions_limit(backend, fixture_site_url):
    recorded_session = paginated_card_session(
        f"{fixture_site_url}/shop?page=1", next_button_pagination("a.next", 2)
    )

    run_result = asyncio.run(
        run_session(BrowserConfig(backend=backend), recorded_session, RunOptions(max_pages=3))
    )

    assert [record["name"] for record in run_result["data"]] == [
        name for names in SHOP_PAGES for name in names
    ]


def test_run_options_max_rows_stops_paging_once_enough_rows_are_read(fixture_site_url, monkeypatch):
    page_reads = []
    read_row_table = session_runner.read_row_table

    async def counted_read_row_table(page, row_table):
        page_reads.append(page.url)
        return await read_row_table(page, row_table)

    monkeypatch.setattr(session_runner, "read_row_table", counted_read_row_table)
    recorded_session = paginated_card_session(
        f"{fixture_site_url}/shop?page=1", next_button_pagination("a.next", 10)
    )

    run_result = asyncio.run(
        run_session(BrowserConfig(backend="chromium"), recorded_session, RunOptions(max_rows=3))
    )

    assert [record["name"] for record in run_result["data"]] == ["Shoe", "Hat", "Boot"]
    assert run_result["items_count"] == 3
    assert len(page_reads) == 2


@pytest.mark.parametrize(
    "max_scrolls, run_options, expected_post_count",
    [(10, RunOptions(), 9), (1, RunOptions(), 6), (10, RunOptions(max_scrolls=1), 6)],
    ids=["to-the-end", "max-scrolls", "run-options-max-scrolls"],
)
@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_infinite_scroll_reads_rows_loaded_by_scrolling(
    backend, max_scrolls, run_options, expected_post_count, fixture_site_url, monkeypatch
):
    monkeypatch.setattr(session_runner, "ROW_GROWTH_WAIT_MS", 1000)
    recorded_session = {
        "url": f"{fixture_site_url}/feed",
        "actions": [],
        "selectors": [],
        "table": {
            "rowSelector": "ul.feed > li",
            "rowFallbackSelectors": [],
            "columns": [table_column("post", ":scope")],
            "pagination": {"mode": "infiniteScroll", "maxScrolls": max_scrolls},
        },
    }

    run_result = asyncio.run(
        run_session(BrowserConfig(backend=backend), recorded_session, run_options)
    )

    assert run_result["data"] == [
        {"post": f"post {post_number}"} for post_number in range(1, expected_post_count + 1)
    ]
