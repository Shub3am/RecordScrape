"""
Replays a recorded session's actions in a fresh browser, then re-reads the elements picked in it,
falling back through each selector list when the one before no longer matches.
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

# vpr read values through Selenium: `.text` for textContent, which is the rendered text, and
# get_attribute for the rest, which returns the property (an absolute href or src) before the
# attribute. Kept so sessions recorded under vpr extract the same values.
READ_PICKED_VALUES_SCRIPT = """(elements, attribute) => elements.map((element) => ({
  value: attribute === 'textContent'
    ? element.innerText
    : String(element[attribute] ?? element.getAttribute(attribute) ?? ''),
  tag: element.tagName.toLowerCase(),
}))"""

# scrollTo returns before the page's scroll listeners run; browsers fire them on the next rendering
# frame, just before animation frame callbacks. Lazy-loading pages start their loads from those
# listeners, so the step resolves in that frame's callback.
SCROLL_AND_LET_LISTENERS_RUN_SCRIPT = """([x, y]) => new Promise((resolve) => {
  window.scrollTo(x, y);
  requestAnimationFrame(() => resolve());
})"""


class RecordedStepFailed(Exception):
    """A recorded action found nothing to act on, so extraction would read the wrong page."""


async def find_matching_selector(
    page, candidate_selectors: list[str], timeout_ms: int
) -> str | None:
    """Waits up to timeout_ms for any candidate to attach, then returns the first one in order that
    matches, or None if none did."""
    try:
        await page.locator(", ".join(candidate_selectors)).first.wait_for(
            state="attached", timeout=timeout_ms
        )
    except (PlaywrightTimeoutError, PatchrightTimeoutError):
        return None
    for candidate_selector in candidate_selectors:
        if await page.locator(candidate_selector).count():
            return candidate_selector
    return None


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
            rows_per_picked_element = await asyncio.gather(
                *(
                    read_picked_element(page, picked_element)
                    for picked_element in recorded_session["selectors"]
                )
            )
            extracted_rows = [row for picked_rows in rows_per_picked_element for row in picked_rows]
    except (*BROWSER_ERRORS, RecordedStepFailed) as run_error:
        return {"success": False, "error": str(run_error), "timestamp": time.time()}
    return {
        "success": True,
        "url": recorded_session["url"],
        "data": extracted_rows,
        "timestamp": time.time(),
        "items_count": len(extracted_rows),
    }
