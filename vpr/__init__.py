"""
Visual Page Recorder (VPR)
A tool for recording browser interactions and replaying them for automated data extraction.
"""

__version__ = "1.0.0"
__author__ = "Shubham VS"

from vpr.recorder import SessionRecorder
from vpr.replayer import SessionReplayer
from vpr.storage import StorageManager
from vpr.scheduler import ScraperScheduler

__all__ = [
    "SessionRecorder",
    "SessionReplayer",
    "StorageManager",
    "ScraperScheduler",
]
