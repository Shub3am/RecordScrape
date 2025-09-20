"""
Assembles the one init script the recorder injects into every document it records.
Must not hold page logic; that lives in the .js files beside this one.
"""

import json
from pathlib import Path

from recordscrape.browsers import BINDINGS_READY_EVENT

RECORD_BINDING = "__recordscrapeRecord"


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
  const sendToRecorder = createRecorderChannel(
    {json.dumps(RECORD_BINDING)},
    {json.dumps(BINDINGS_READY_EVENT)},
  );
  startActionCapture(sendToRecorder);
}})();
"""
