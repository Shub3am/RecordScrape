"""
Visual Page Recorder (VPR)
SQLite storage and interval scheduling for recorded sessions. Recording and running live in recordscrape/.
"""

__version__ = "1.0.0"
__author__ = "Shubham VS"

from vpr.scheduler import ScraperScheduler
from vpr.storage import StorageManager

__all__ = [
    "ScraperScheduler",
    "StorageManager",
]
