"""
Scraper Scheduler for Visual Data Scraper
Manages periodic execution of scraping sessions using APScheduler.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from vpr.storage import StorageManager
from vpr.replayer import SessionReplayer


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScraperScheduler:
    """Manages scheduled scraping jobs."""
    
    def __init__(self, storage: StorageManager):
        """Initialize the scheduler."""
        self.storage = storage
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.jobs = {}  # Map schedule_id to job_id
        
        # Load existing schedules
        self._load_schedules()
    
    def _load_schedules(self):
        """Load and activate all enabled schedules from database."""
        schedules = self.storage.get_all_schedules()
        for schedule in schedules:
            if schedule["enabled"]:
                self.add_schedule(
                    schedule["id"],
                    schedule["session_id"],
                    schedule["frequency_minutes"]
                )
    
    def add_schedule(self, schedule_id: int, session_id: int, 
                    frequency_minutes: int) -> bool:
        """
        Add a new scheduled job.
        
        Args:
            schedule_id: ID of the schedule in database
            session_id: ID of the session to replay
            frequency_minutes: How often to run (in minutes)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove existing job if any
            if schedule_id in self.jobs:
                self.remove_schedule(schedule_id)
            
            # Create trigger
            trigger = IntervalTrigger(minutes=frequency_minutes)
            
            # Add job
            job = self.scheduler.add_job(
                func=self._run_scraping_job,
                trigger=trigger,
                args=[session_id, schedule_id],
                id=f"schedule_{schedule_id}",
                name=f"Scrape Session {session_id}",
                replace_existing=True
            )
            
            self.jobs[schedule_id] = job.id
            logger.info(f"Added schedule {schedule_id} for session {session_id} "
                       f"(every {frequency_minutes} minutes)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding schedule: {e}")
            return False
    
    def remove_schedule(self, schedule_id: int) -> bool:
        """Remove a scheduled job."""
        try:
            if schedule_id in self.jobs:
                job_id = self.jobs[schedule_id]
                self.scheduler.remove_job(job_id)
                del self.jobs[schedule_id]
                logger.info(f"Removed schedule {schedule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing schedule: {e}")
            return False
    
    def pause_schedule(self, schedule_id: int) -> bool:
        """Pause a scheduled job."""
        try:
            if schedule_id in self.jobs:
                job_id = self.jobs[schedule_id]
                self.scheduler.pause_job(job_id)
                self.storage.update_schedule(schedule_id, enabled=False)
                logger.info(f"Paused schedule {schedule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error pausing schedule: {e}")
            return False
    
    def resume_schedule(self, schedule_id: int) -> bool:
        """Resume a paused scheduled job."""
        try:
            if schedule_id in self.jobs:
                job_id = self.jobs[schedule_id]
                self.scheduler.resume_job(job_id)
                self.storage.update_schedule(schedule_id, enabled=True)
                logger.info(f"Resumed schedule {schedule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resuming schedule: {e}")
            return False
    
    def _run_scraping_job(self, session_id: int, schedule_id: int):
        """
        Execute a scraping job.
        
        Args:
            session_id: ID of session to replay
            schedule_id: ID of the schedule
        """
        logger.info(f"Running scheduled scrape for session {session_id}")
        
        try:
            # Get session data
            session = self.storage.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return
            
            # Replay session
            replayer = SessionReplayer(headless=True)
            result = replayer.replay_session(session)
            
            # Save extracted data
            if result.get("success"):
                data_id = self.storage.save_extracted_data(session_id, result["data"])
                logger.info(f"Extracted {result.get('items_count', 0)} items, "
                          f"saved as data ID {data_id}")
                
                # Update session run stats
                self.storage.update_session_run(session_id)
            else:
                logger.error(f"Scraping failed: {result.get('error', 'Unknown error')}")
            
            # Update next run time
            self.storage.update_schedule_next_run(schedule_id)
            
        except Exception as e:
            logger.error(f"Error in scraping job: {e}")
    
    def run_manual(self, session_id: int, headless: bool = False) -> dict:
        """
        Manually trigger a scraping job (not scheduled).
        
        Args:
            session_id: ID of session to replay
            headless: Whether to run in headless mode (default: False for visible browser)
            
        Returns:
            Result dictionary from replayer
        """
        mode = "headless" if headless else "visible browser"
        logger.info(f"Running manual scrape for session {session_id} in {mode} mode")
        
        try:
            # Get session data
            session = self.storage.get_session(session_id)
            if not session:
                return {"success": False, "error": "Session not found"}
            
            # Replay session with user-specified headless mode
            replayer = SessionReplayer(headless=headless)
            result = replayer.replay_session(session)
            
            # Save extracted data
            if result.get("success"):
                data_id = self.storage.save_extracted_data(session_id, result["data"])
                result["data_id"] = data_id
                
                # Update session run stats
                self.storage.update_session_run(session_id)
                
                logger.info(f"Manual scrape completed, extracted {result.get('items_count', 0)} items")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in manual scrape: {e}")
            return {"success": False, "error": str(e)}
    
    def get_job_status(self, schedule_id: int) -> Optional[dict]:
        """Get status of a scheduled job."""
        try:
            if schedule_id in self.jobs:
                job_id = self.jobs[schedule_id]
                job = self.scheduler.get_job(job_id)
                if job:
                    return {
                        "id": job.id,
                        "name": job.name,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                        "pending": job.pending
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None
    
    def shutdown(self):
        """Shutdown the scheduler."""
        logger.info("Shutting down scheduler")
        self.scheduler.shutdown()
