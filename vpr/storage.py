"""
Storage Manager for Visual Data Scraper
Handles SQLite database operations for sessions, schedules, and extracted data.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any


class StorageManager:
    """Manages all database operations for the scraper."""
    
    def __init__(self, db_path: str = "scraper.db"):
        """Initialize storage manager with database path."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                actions TEXT NOT NULL,
                selectors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run TIMESTAMP,
                run_count INTEGER DEFAULT 0
            )
        """)
        
        # Schedules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                frequency_minutes INTEGER NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                next_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        
        # Extracted data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracted_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ==================== SESSION OPERATIONS ====================
    
    def create_session(self, name: str, url: str, actions: List[Dict], 
                      selectors: Optional[List[Dict]] = None) -> int:
        """Create a new session recording."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sessions (name, url, actions, selectors)
            VALUES (?, ?, ?, ?)
        """, (
            name,
            url,
            json.dumps(actions),
            json.dumps(selectors) if selectors else None
        ))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get a session by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "actions": json.loads(row["actions"]),
                "selectors": json.loads(row["selectors"]) if row["selectors"] else [],
                "created_at": row["created_at"],
                "last_run": row["last_run"],
                "run_count": row["run_count"]
            }
        return None
    
    def get_all_sessions(self) -> List[Dict]:
        """Get all sessions."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        sessions = []
        for row in rows:
            sessions.append({
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "actions": json.loads(row["actions"]),
                "selectors": json.loads(row["selectors"]) if row["selectors"] else [],
                "created_at": row["created_at"],
                "last_run": row["last_run"],
                "run_count": row["run_count"]
            })
        
        return sessions
    
    def update_session_run(self, session_id: int):
        """Update session last run time and increment run count."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE sessions 
            SET last_run = CURRENT_TIMESTAMP, run_count = run_count + 1
            WHERE id = ?
        """, (session_id,))
        
        conn.commit()
        conn.close()
    
    def delete_session(self, session_id: int):
        """Delete a session and all related data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        
        conn.commit()
        conn.close()
    
    # ==================== SCHEDULE OPERATIONS ====================
    
    def create_schedule(self, session_id: int, frequency_minutes: int) -> int:
        """Create a new schedule for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate next run time
        from datetime import timedelta
        next_run = datetime.now() + timedelta(minutes=frequency_minutes)
        
        cursor.execute("""
            INSERT INTO schedules (session_id, frequency_minutes, next_run)
            VALUES (?, ?, ?)
        """, (session_id, frequency_minutes, next_run))
        
        schedule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return schedule_id
    
    def get_schedule(self, schedule_id: int) -> Optional[Dict]:
        """Get a schedule by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, sess.name as session_name, sess.url as session_url
            FROM schedules s
            JOIN sessions sess ON s.session_id = sess.id
            WHERE s.id = ?
        """, (schedule_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "session_id": row["session_id"],
                "session_name": row["session_name"],
                "session_url": row["session_url"],
                "frequency_minutes": row["frequency_minutes"],
                "enabled": bool(row["enabled"]),
                "next_run": row["next_run"],
                "created_at": row["created_at"]
            }
        return None
    
    def get_all_schedules(self) -> List[Dict]:
        """Get all schedules."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, sess.name as session_name, sess.url as session_url
            FROM schedules s
            JOIN sessions sess ON s.session_id = sess.id
            ORDER BY s.created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        schedules = []
        for row in rows:
            schedules.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "session_name": row["session_name"],
                "session_url": row["session_url"],
                "frequency_minutes": row["frequency_minutes"],
                "enabled": bool(row["enabled"]),
                "next_run": row["next_run"],
                "created_at": row["created_at"]
            })
        
        return schedules
    
    def update_schedule(self, schedule_id: int, frequency_minutes: Optional[int] = None,
                       enabled: Optional[bool] = None):
        """Update a schedule."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if frequency_minutes is not None:
            updates.append("frequency_minutes = ?")
            params.append(frequency_minutes)
            
            # Recalculate next run
            from datetime import timedelta
            next_run = datetime.now() + timedelta(minutes=frequency_minutes)
            updates.append("next_run = ?")
            params.append(next_run)
        
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        
        if updates:
            params.append(schedule_id)
            query = f"UPDATE schedules SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
    
    def delete_schedule(self, schedule_id: int):
        """Delete a schedule."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        
        conn.commit()
        conn.close()
    
    def update_schedule_next_run(self, schedule_id: int):
        """Update the next run time for a schedule."""
        schedule = self.get_schedule(schedule_id)
        if schedule:
            from datetime import timedelta
            next_run = datetime.now() + timedelta(minutes=schedule["frequency_minutes"])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE schedules SET next_run = ? WHERE id = ?", 
                         (next_run, schedule_id))
            conn.commit()
            conn.close()
    
    # ==================== DATA OPERATIONS ====================
    
    def save_extracted_data(self, session_id: int, data: Any) -> int:
        """Save extracted data for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO extracted_data (session_id, data)
            VALUES (?, ?)
        """, (session_id, json.dumps(data)))
        
        data_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return data_id
    
    def get_session_data(self, session_id: int, limit: int = 10) -> List[Dict]:
        """Get extracted data for a session."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM extracted_data 
            WHERE session_id = ? 
            ORDER BY extracted_at DESC 
            LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        data_list = []
        for row in rows:
            data_list.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "data": json.loads(row["data"]),
                "extracted_at": row["extracted_at"]
            })
        
        return data_list
    
    def get_all_data(self, limit: int = 50) -> List[Dict]:
        """Get all extracted data across all sessions."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ed.*, s.name as session_name
            FROM extracted_data ed
            JOIN sessions s ON ed.session_id = s.id
            ORDER BY ed.extracted_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        data_list = []
        for row in rows:
            data_list.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "session_name": row["session_name"],
                "data": json.loads(row["data"]),
                "extracted_at": row["extracted_at"]
            })
        
        return data_list
