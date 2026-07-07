"""
Records one browsing session: the user's actions on every page they visit as replayable steps, and
the elements they pick for extraction.
Must not know about storage, Flask or the worker; callers run it on the worker and persist what
stop() returns.
"""

import time
from contextlib import AsyncExitStack

from recordscrape.browsers import BrowserConfig, open_browser_context
from recordscrape.recorder.recorder_script import (
    ACTIVATE_PICKER_SCRIPT,
    RECORD_BINDING,
    RECORDER_INIT_SCRIPT,
)


class SessionRecorder:
    def __init__(self, browser_config: BrowserConfig):
        self.browser_config = browser_config
        self.start_url = ""
        self.recorded_actions: list[dict] = []
        self.picked_elements: list[dict] = []
        # The page the user last acted on, which is where the picker opens.
        self.active_page = None
        self.context_exit_stack: AsyncExitStack | None = None

    async def start(self, start_url: str) -> None:
        async with AsyncExitStack() as context_exit_stack:
            browser_context = await context_exit_stack.enter_async_context(
                open_browser_context(self.browser_config)
            )
            await browser_context.expose_binding(RECORD_BINDING, self.receive_page_message)
            await browser_context.add_init_script(RECORDER_INIT_SCRIPT)
            self.active_page = await browser_context.new_page()
            self.start_url = start_url
            self.recorded_actions.append(
                {"type": "navigate", "url": start_url, "timestamp": time.time()}
            )
            await self.active_page.goto(start_url)
            # Keeps the browser open after start() returns, until stop(). If anything above raised,
            # the stack is still owned by this block and the browser has already been closed.
            self.context_exit_stack = context_exit_stack.pop_all()

    async def activate_picker(self) -> None:
        """Opens the picker overlay and returns at once; picks arrive until the user presses Done."""
        await self.active_page.evaluate(ACTIVATE_PICKER_SCRIPT)

    async def stop(self) -> dict:
        """Closes the browser and returns the session, keyed like vpr's SessionRecorder output."""
        await self.context_exit_stack.aclose()
        return {
            "url": self.start_url,
            "actions": self.recorded_actions,
            "selectors": self.picked_elements,
        }

    def receive_page_message(self, binding_source: dict, page_message: dict) -> None:
        self.active_page = binding_source["page"]
        if page_message["kind"] == "pick":
            self.picked_elements.append(page_message["pickedElement"])
        else:
            self.record_action(page_message["action"])

    def record_action(self, action: dict) -> None:
        action["timestamp"] = time.time()
        previous_action = self.recorded_actions[-1]
        # The page sends one input action per keystroke; only a field's final value is a step.
        typing_in_same_field = (
            action["type"] == "input"
            and previous_action["type"] == "input"
            and previous_action["selector"] == action["selector"]
        )
        if typing_in_same_field:
            self.recorded_actions[-1] = action
        else:
            self.recorded_actions.append(action)
