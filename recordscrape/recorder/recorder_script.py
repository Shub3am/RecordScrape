"""
Assembles the one init script the recorder injects into every document it records.
Must not hold page logic; that lives in the .js files beside this one.
"""

import json
from pathlib import Path

from recordscrape.browsers import BINDINGS_READY_EVENT

RECORD_BINDING = "__recordscrapeRecord"

ACTIVATE_PICKER_EVENT = "recordscrape:activate-picker"

# A DOM event reaches listeners in every JS world, so this works from Patchright's isolated evaluate.
ACTIVATE_PICKER_SCRIPT = (
    f"() => window.dispatchEvent(new Event({json.dumps(ACTIVATE_PICKER_EVENT)}))"
)


def read_page_script(file_name: str) -> str:
    return (Path(__file__).parent / file_name).read_text()


# The .js files declare plain functions. Wrapping them in one function keeps those names out of the
# page's global scope, where they could clash with the page's own code.
RECORDER_INIT_SCRIPT = f"""
(() => {{
  // Steps recorded inside a frame could not be replayed from the top page, so frames are skipped.
  if (window !== window.top) return;
{read_page_script("selector_builder.js")}
{read_page_script("recorder_channel.js")}
{read_page_script("action_capture.js")}
{read_page_script("element_picker.js")}
  const sendToRecorder = createRecorderChannel(
    {json.dumps(RECORD_BINDING)},
    {json.dumps(BINDINGS_READY_EVENT)},
  );
  installElementPicker(sendToRecorder, {json.dumps(ACTIVATE_PICKER_EVENT)});
  startActionCapture(sendToRecorder);
}})();
"""
