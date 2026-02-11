"""
Replays a recorded session's actions in a fresh browser, then re-reads the elements and row table
picked in it, falling back through each selector list when the one before no longer matches. A row
table can span pages through its next button or through scrolling.
Must not know about storage, Flask or the worker.
"""

import asyncio
import time

from patchright.async_api import TimeoutError as PatchrightTimeoutError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from recordscrape.browsers import BROWSER_ERRORS, BrowserConfig, open_browser_context
from recordscrape.flows import recorded_by_vpr

PICKED_ELEMENT_WAIT_MS = 5000
STEP_TARGET_WAIT_MS = 10000
PAGE_CHANGE_WAIT_MS = 10000
ROW_GROWTH_WAIT_MS = 5000

TIMEOUT_ERRORS = (PlaywrightTimeoutError, PatchrightTimeoutError)

# vpr read values through Selenium: `.text` for textContent, which is the rendered text, and
# get_attribute for the rest, which returns the property (an absolute href or src) before the
# attribute. Kept so sessions recorded under vpr extract the same values.
READ_ELEMENT_VALUE_FUNCTION = """(element, attribute) => attribute === 'textContent'
  ? element.innerText
  : String(element[attribute] ?? element.getAttribute(attribute) ?? '')"""

READ_PICKED_VALUES_SCRIPT = f"""(elements, attribute) => {{
  const readElementValue = {READ_ELEMENT_VALUE_FUNCTION};
  return elements.map((element) => ({{
    value: readElementValue(element, attribute),
    tag: element.tagName.toLowerCase(),
  }}));
}}"""

# Column selectors are relative to their row, so they run through the row's own querySelector,
# where `:scope` is the row. querySelector never returns the row itself, so a selector that is
# exactly `:scope` is the column that reads the whole row.
READ_TABLE_ROWS_SCRIPT = f"""(rows, columns) => {{
  const readElementValue = {READ_ELEMENT_VALUE_FUNCTION};
  return rows.map((row) => Object.fromEntries(columns.map((column) => {{
    const cell = [column.selector, ...column.fallbackSelectors].reduce(
      (matchedCell, selector) =>
        matchedCell ?? (selector === ':scope' ? row : row.querySelector(selector)),
      null,
    );
    return [column.name, cell === null ? '' : readElementValue(cell, column.attribute).trim()];
  }})));
}}"""

# scrollTo returns before the page's scroll listeners run; browsers fire them on the next rendering
# frame, just before animation frame callbacks. Lazy-loading pages start their loads from those
# listeners, so the step resolves in that frame's callback.
SCROLL_AND_LET_LISTENERS_RUN_SCRIPT = """([x, y]) => new Promise((resolve) => {
  window.scrollTo(x, y);
  requestAnimationFrame(() => resolve());
})"""

READ_ROWS_TEXT_SCRIPT = """(rowSelectors) =>
  Array.from(document.querySelectorAll(rowSelectors), (row) => row.innerText).join('\\n')"""

# Compares text, not elements: a full page load replaces the rows, but a client-side pager may reuse
# the same elements and only change what is inside them.
ROWS_CHANGED_SCRIPT = f"""([rowSelectors, previousRowsText]) => {{
  const rowsText = ({READ_ROWS_TEXT_SCRIPT})(rowSelectors);
  return rowsText !== '' && rowsText !== previousRowsText;
}}"""

# Scrolling the last row into view reaches a list that scrolls inside its own container; scrolling
# the window to the bottom reaches a loader that sits below the list. Returns the row count before
# the scroll.
SCROLL_PAST_LAST_ROW_SCRIPT = f"""async (rowSelectors) => {{
  const rows = document.querySelectorAll(rowSelectors);
  rows[rows.length - 1].scrollIntoView();
  await ({SCROLL_AND_LET_LISTENERS_RUN_SCRIPT})([0, document.documentElement.scrollHeight]);
  return rows.length;
}}"""

ROW_COUNT_GREW_SCRIPT = """([rowSelectors, previousRowCount]) =>
  document.querySelectorAll(rowSelectors).length > previousRowCount"""


class RecordedStepFailed(Exception):
    """A recorded action found nothing to act on, so extraction would read the wrong page."""


def row_candidate_selectors(row_table: dict) -> list[str]:
    return [row_table["rowSelector"], *row_table["rowFallbackSelectors"]]


async def first_matching_selector(page, candidate_selectors: list[str]) -> str | None:
    """Returns the first candidate in order that matches now, or None, without waiting."""
    for candidate_selector in candidate_selectors:
        if await page.locator(candidate_selector).count():
            return candidate_selector
    return None


async def find_matching_selector(
    page, candidate_selectors: list[str], timeout_ms: int
) -> str | None:
    """Waits up to timeout_ms for any candidate to attach, then returns the first one in order that
    matches, or None if none did."""
    try:
        await page.locator(", ".join(candidate_selectors)).first.wait_for(
            state="attached", timeout=timeout_ms
        )
    except TIMEOUT_ERRORS:
        return None
    return await first_matching_selector(page, candidate_selectors)


async def replay_recorded_step(page, step_number: int, recorded_step: dict) -> None:
    """Performs one recorded click, input or scroll. Raises RecordedStepFailed when no selector matches."""
    if recorded_step["type"] == "scroll":
        # The user scrolled a page they could see, and a page still loading may be too short to reach y.
        await page.wait_for_load_state()
        await page.evaluate(
            SCROLL_AND_LET_LISTENERS_RUN_SCRIPT, [recorded_step["x"], recorded_step["y"]]
        )
        return
    candidate_selectors = [recorded_step["selector"], *recorded_step["fallbackSelectors"]]
    matched_selector = await find_matching_selector(page, candidate_selectors, STEP_TARGET_WAIT_MS)
    if matched_selector is None:
        raise RecordedStepFailed(
            f"Step {step_number} ({recorded_step['type']} {recorded_step['selector']}) "
            f"matched nothing within {STEP_TARGET_WAIT_MS} ms"
        )
    step_target = page.locator(matched_selector).first
    if recorded_step["type"] == "click":
        await step_target.click()
    elif recorded_step.get("checked") is not None:
        await step_target.set_checked(recorded_step["checked"])
    elif await step_target.evaluate("element => element.tagName") == "SELECT":
        await step_target.select_option(recorded_step["value"])
    else:
        await step_target.fill(recorded_step["value"])


async def read_picked_element(page, picked_element: dict) -> list[dict]:
    """Returns one row per non-empty match of the first of the element's selectors that matches."""
    # Sessions recorded under vpr have no fallbackSelectors key.
    candidate_selectors = [picked_element["selector"], *picked_element.get("fallbackSelectors", [])]
    matched_selector = await find_matching_selector(
        page, candidate_selectors, PICKED_ELEMENT_WAIT_MS
    )
    if matched_selector is None:
        return []
    matched_values = await page.locator(matched_selector).evaluate_all(
        READ_PICKED_VALUES_SCRIPT, picked_element["attribute"]
    )
    return [
        {
            "selector": picked_element["selector"],
            "value": matched_value["value"].strip(),
            "attribute": picked_element["attribute"],
            "index": match_index,
            "tag": matched_value["tag"],
        }
        for match_index, matched_value in enumerate(matched_values)
        if matched_value["value"].strip()
    ]


async def read_row_table(page, row_table: dict) -> list[dict]:
    """Returns one record per matched row, keyed by column name. A column that matches nothing in a
    row reads "", and a row whose every value is empty is dropped."""
    matched_selector = await find_matching_selector(
        page, row_candidate_selectors(row_table), PICKED_ELEMENT_WAIT_MS
    )
    if matched_selector is None:
        return []
    row_records = await page.locator(matched_selector).evaluate_all(
        READ_TABLE_ROWS_SCRIPT, row_table["columns"]
    )
    return [row_record for row_record in row_records if any(row_record.values())]


async def read_row_table_after_scrolling(page, row_table: dict, max_scrolls: int) -> list[dict]:
    """Scrolls past the last row up to max_scrolls times, stopping early when no new row arrives
    within ROW_GROWTH_WAIT_MS of a scroll, then reads every row."""
    candidate_selectors = row_candidate_selectors(row_table)
    if await find_matching_selector(page, candidate_selectors, PICKED_ELEMENT_WAIT_MS) is None:
        return []
    row_selectors = ", ".join(candidate_selectors)
    for _ in range(max_scrolls):
        row_count = await page.evaluate(SCROLL_PAST_LAST_ROW_SCRIPT, row_selectors)
        try:
            await page.wait_for_function(
                ROW_COUNT_GREW_SCRIPT, arg=[row_selectors, row_count], timeout=ROW_GROWTH_WAIT_MS
            )
        except TIMEOUT_ERRORS:
            break
    return await read_row_table(page, row_table)


async def read_following_pages(page, row_table: dict, next_button: dict) -> list[dict]:
    """Returns the records of every page after the current one, clicking the next button until
    maxPages pages are read, the button is missing, hidden or disabled, or a click leaves the rows
    unchanged for PAGE_CHANGE_WAIT_MS."""
    row_selectors = ", ".join(row_candidate_selectors(row_table))
    candidate_next_selectors = [next_button["selector"], *next_button["fallbackSelectors"]]
    following_records = []
    for _ in range(next_button["maxPages"] - 1):
        # A server-rendered pager comes after the rows, which attach while the document still parses.
        await page.wait_for_load_state()
        next_button_selector = await first_matching_selector(page, candidate_next_selectors)
        if next_button_selector is None:
            break
        next_button_target = page.locator(next_button_selector).first
        if not (await next_button_target.is_visible() and await next_button_target.is_enabled()):
            break
        rows_text = await page.evaluate(READ_ROWS_TEXT_SCRIPT, row_selectors)
        await next_button_target.click()
        try:
            # Re-runs in the new document when the click navigates.
            await page.wait_for_function(
                ROWS_CHANGED_SCRIPT, arg=[row_selectors, rows_text], timeout=PAGE_CHANGE_WAIT_MS
            )
        except TIMEOUT_ERRORS:
            break
        following_records += await read_row_table(page, row_table)
    return following_records


async def run_session(browser_config: BrowserConfig, recorded_session: dict) -> dict:
    """Returns the result dict vpr's SessionReplayer did, so the scheduler and dashboard read it
    unchanged. A browser failure or a step that matches nothing becomes `success: False`; any other
    exception is a bug and raises."""
    recorded_steps = recorded_session["actions"]
    # The recorder records navigate only for the start URL, which is opened before replay.
    # Step numbers count every action so an error points at its position in `actions`.
    replayable_steps = (
        []
        if recorded_by_vpr(recorded_steps)
        else [
            (step_number, recorded_step)
            for step_number, recorded_step in enumerate(recorded_steps, start=1)
            if recorded_step["type"] != "navigate"
        ]
    )
    try:
        async with open_browser_context(browser_config) as browser_context:
            page = await browser_context.new_page()
            await page.goto(recorded_session["url"])
            for step_number, recorded_step in replayable_steps:
                await replay_recorded_step(page, step_number, recorded_step)
            # Read concurrently so missing elements wait out one timeout together, not one each.
            # gather keeps the picked order, so rows come out in the order the user picked.
            row_table = recorded_session["table"]
            picked_element_reads = (
                read_picked_element(page, picked_element)
                for picked_element in recorded_session["selectors"]
            )
            if row_table is None:
                rows_per_picked_element = await asyncio.gather(*picked_element_reads)
                extracted_rows = [
                    row for picked_rows in rows_per_picked_element for row in picked_rows
                ]
            else:
                # Tables stored before pagination existed have no pagination key.
                table_pagination = row_table.get("pagination") or {}
                first_page_table_read = (
                    read_row_table_after_scrolling(page, row_table, table_pagination["maxScrolls"])
                    if table_pagination.get("mode") == "infiniteScroll"
                    else read_row_table(page, row_table)
                )
                table_records, *rows_per_picked_element = await asyncio.gather(
                    first_page_table_read, *picked_element_reads
                )
                # Single picked elements are read on the first page only, before it is left.
                if table_pagination.get("mode") == "nextButton":
                    table_records += await read_following_pages(page, row_table, table_pagination)
                # Each single picked element becomes a column holding its first value on every row.
                single_columns = {
                    picked_element["selector"]: picked_rows[0]["value"] if picked_rows else ""
                    for picked_element, picked_rows in zip(
                        recorded_session["selectors"], rows_per_picked_element
                    )
                }
                extracted_rows = [
                    {**table_record, **single_columns} for table_record in table_records
                ]
    except (*BROWSER_ERRORS, RecordedStepFailed) as run_error:
        return {"success": False, "error": str(run_error), "timestamp": time.time()}
    return {
        "success": True,
        "url": recorded_session["url"],
        "data": extracted_rows,
        "timestamp": time.time(),
        "items_count": len(extracted_rows),
    }
