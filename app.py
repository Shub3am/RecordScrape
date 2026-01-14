"""
Visual Data Scraper - Flask Application
Main application with REST API for managing sessions, schedules, and data extraction.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import threading
import logging
from typing import Optional
from vpr import SessionRecorder, SessionReplayer, StorageManager, ScraperScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize components
storage = StorageManager()
scheduler = ScraperScheduler(storage)

# Global recorder instance (one at a time)
current_recorder: Optional[SessionRecorder] = None
recorder_lock = threading.Lock()


# ==================== WEB ROUTES ====================

@app.route('/')
def index():
    """Serve the main dashboard."""
    return render_template('index.html')


# ==================== SESSION API ====================

@app.route('/api/sessions/start', methods=['POST'])
def start_session():
    """Start recording a new session."""
    global current_recorder
    
    with recorder_lock:
        if current_recorder and current_recorder.is_recording():
            return jsonify({"error": "Recording already in progress"}), 400
        
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        # Start recording in a separate thread
        current_recorder = SessionRecorder()
        recorder = current_recorder  # Local reference for type checking
        
        def start_recording():
            success = recorder.start_recording(url)
            if not success:
                logger.error("Failed to start recording")
        
        thread = threading.Thread(target=start_recording)
        thread.start()
        thread.join(timeout=5)  # Wait for browser to start
        
        return jsonify({
            "success": True,
            "message": "Recording started",
            "url": url
        })


@app.route('/api/sessions/selector', methods=['POST'])
def activate_selector():
    """Activate element selector mode."""
    global current_recorder
    
    if not current_recorder or not current_recorder.is_recording():
        return jsonify({"error": "No active recording"}), 400
    
    recorder = current_recorder  # Local reference for type checking
    
    # Activate selector in background
    def run_selector():
        recorder.activate_selector_mode()
    
    thread = threading.Thread(target=run_selector)
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Selector mode activated"
    })


@app.route('/api/sessions/stop', methods=['POST'])
def stop_session():
    """Stop recording and save session."""
    global current_recorder
    
    with recorder_lock:
        if not current_recorder or not current_recorder.is_recording():
            return jsonify({"error": "No active recording"}), 400
        
        data = request.json
        name = data.get('name', 'Untitled Session')
        
        # Stop recording
        session_data = current_recorder.stop_recording()
        
        if not session_data:
            return jsonify({"error": "Failed to stop recording"}), 500
        
        # Save to database
        session_id = storage.create_session(
            name=name,
            url=session_data['url'],
            actions=session_data['actions'],
            selectors=session_data.get('selectors', [])
        )
        
        current_recorder = None
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": "Session saved successfully"
        })


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all sessions."""
    sessions = storage.get_all_sessions()
    return jsonify(sessions)


@app.route('/api/sessions/<int:session_id>', methods=['GET'])
def get_session(session_id):
    """Get a specific session."""
    session = storage.get_session(session_id)
    if session:
        return jsonify(session)
    return jsonify({"error": "Session not found"}), 404


@app.route('/api/sessions/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session."""
    storage.delete_session(session_id)
    return jsonify({"success": True, "message": "Session deleted"})


@app.route('/api/sessions/<int:session_id>/replay', methods=['POST'])
def replay_session(session_id):
    """Manually replay a session."""
    result = scheduler.run_manual(session_id)
    return jsonify(result)


# ==================== SCHEDULE API ====================

@app.route('/api/schedules', methods=['POST'])
def create_schedule():
    """Create a new schedule."""
    data = request.json
    session_id = data.get('session_id')
    frequency_minutes = data.get('frequency_minutes')
    
    if not session_id or not frequency_minutes:
        return jsonify({"error": "session_id and frequency_minutes required"}), 400
    
    # Create in database
    schedule_id = storage.create_schedule(session_id, frequency_minutes)
    
    # Add to scheduler
    scheduler.add_schedule(schedule_id, session_id, frequency_minutes)
    
    return jsonify({
        "success": True,
        "schedule_id": schedule_id,
        "message": "Schedule created"
    })


@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    """Get all schedules."""
    schedules = storage.get_all_schedules()
    return jsonify(schedules)


@app.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    """Update a schedule."""
    data = request.json
    frequency_minutes = data.get('frequency_minutes')
    enabled = data.get('enabled')
    
    # Update in database
    storage.update_schedule(schedule_id, frequency_minutes, enabled)
    
    # Update in scheduler
    if enabled is False:
        scheduler.pause_schedule(schedule_id)
    elif enabled is True:
        scheduler.resume_schedule(schedule_id)
    
    if frequency_minutes:
        schedule = storage.get_schedule(schedule_id)
        if schedule:
            scheduler.add_schedule(
                schedule_id,
                schedule['session_id'],
                frequency_minutes
            )
    
    return jsonify({"success": True, "message": "Schedule updated"})


@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete a schedule."""
    scheduler.remove_schedule(schedule_id)
    storage.delete_schedule(schedule_id)
    return jsonify({"success": True, "message": "Schedule deleted"})


# ==================== DATA API ====================

@app.route('/api/data', methods=['GET'])
def get_all_data():
    """Get all extracted data."""
    limit = request.args.get('limit', 50, type=int)
    data = storage.get_all_data(limit)
    return jsonify(data)


@app.route('/api/data/<int:session_id>', methods=['GET'])
def get_session_data(session_id):
    """Get extracted data for a specific session."""
    limit = request.args.get('limit', 10, type=int)
    data = storage.get_session_data(session_id, limit)
    return jsonify(data)


# ==================== STATUS API ====================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get application status."""
    return jsonify({
        "recording": current_recorder is not None and current_recorder.is_recording(),
        "sessions_count": len(storage.get_all_sessions()),
        "schedules_count": len(storage.get_all_schedules()),
        "scheduler_running": scheduler.scheduler.running
    })


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("Starting Visual Data Scraper...")
    logger.info("Dashboard: http://localhost:5001")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()
