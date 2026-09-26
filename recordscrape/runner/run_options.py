"""
The limits one run sets over its session's own, so a replay can read fewer or more pages than the
session was saved with, or keep only its first rows, without editing the session.
Must not know about HTTP, storage or how a run is triggered.
"""

from pydantic import BaseModel, ConfigDict, PositiveInt


class RunOptions(BaseModel):
    """None keeps the session's own limit. max_pages and max_scrolls only apply to a row table with
    that kind of pagination; max_rows applies to every run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_pages: PositiveInt | None = None
    max_scrolls: PositiveInt | None = None
    max_rows: PositiveInt | None = None
