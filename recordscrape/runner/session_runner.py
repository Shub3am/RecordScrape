"""
Re-reads the elements picked in a recorded session from a fresh browser, falling back through each
element's selectors when the one before no longer matches.
Must not replay recorded actions yet, and must not know about storage, Flask or the worker.
"""

import asyncio
import time

from patchright.async_api import Error as PatchrightError
from patchright.async_api import TimeoutError as PatchrightTimeoutError
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from recordscrape.browsers import BrowserConfig, open_browser_context

PICKED_ELEMENT_WAIT_MS = 5000

# vpr read values through Selenium: `.text` for textContent, which is the rendered text, and
# get_attribute for the rest, which returns the property (an absolute href or src) before the
# attribute. Kept so sessions recorded under vpr extract the same values.
READ_PICKED_VALUES_SCRIPT = """(elements, attribute) => elements.map((element) => ({
  value: attribute === 'textContent'
    ? element.innerText
    : String(element[attribute] ?? element.getAttribute(attribute) ?? ''),
  tag: element.tagName.toLowerCase(),
}))"""


async def read_picked_element(page, picked_element: dict) -> list[dict]:
    """Returns one row per non-empty match of the first of the element's selectors that matches."""
    # Sessions recorded under vpr have no fallbackSelectors key.
    candidate_selectors = [picked_element["selector"], *picked_element.get("fallbackSelectors", [])]
    try:
        await page.locator(", ".join(candidate_selectors)).first.wait_for(
            state="attached", timeout=PICKED_ELEMENT_WAIT_MS
        )
    except (PlaywrightTimeoutError, PatchrightTimeoutError):
        return []
    for candidate_selector in candidate_selectors:
        matched_values = await page.locator(candidate_selector).evaluate_all(
            READ_PICKED_VALUES_SCRIPT, picked_element["attribute"]
        )
        if matched_values:
            break
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


async def run_session(browser_config: BrowserConfig, recorded_session: dict) -> dict:
    """Returns the result dict vpr's SessionReplayer did, so the scheduler and dashboard read it
    unchanged. A browser failure becomes `success: False`; any other exception is a bug and raises."""
    try:
        async with open_browser_context(browser_config) as browser_context:
            page = await browser_context.new_page()
            await page.goto(recorded_session["url"])
            # Read concurrently so missing elements wait out one timeout together, not one each.
            # gather keeps the picked order, so rows come out in the order the user picked.
            rows_per_picked_element = await asyncio.gather(
                *(
                    read_picked_element(page, picked_element)
                    for picked_element in recorded_session["selectors"]
                )
            )
            extracted_rows = [row for picked_rows in rows_per_picked_element for row in picked_rows]
    except (PlaywrightError, PatchrightError) as browser_error:
        return {"success": False, "error": str(browser_error), "timestamp": time.time()}
    return {
        "success": True,
        "url": recorded_session["url"],
        "data": extracted_rows,
        "timestamp": time.time(),
        "items_count": len(extracted_rows),
    }
