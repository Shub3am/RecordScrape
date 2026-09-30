"""
Visual Data Scraper - Flask Application
Main application with REST API for managing sessions, schedules, and data extraction.
"""

from flask import Flask, render_template, request, jsonify, send_file
import dataclasses
import hmac
import io
import os
import threading
import logging
from typing import Optional
from urllib.parse import urlparse
from pydantic import ValidationError
import waitress
from recordscrape.browsers import BACKENDS_WITHOUT_BINDINGS, BROWSER_ERRORS, BrowserConfig
from recordscrape.exporters import EXPORT_FORMATS
from recordscrape.flows import (
    BrowserSettings,
    FlowFile,
    flow_file_json,
    flow_from_recorded_session,
    recorded_session_from_flow,
)
from recordscrape.recorder import SessionRecorder
from recordscrape.runner import RunOptions
from recordscrape.server_settings import server_settings_from_env
from recordscrape.worker import BrowserWorker
from vpr import StorageManager, ScraperScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Visible because recording needs a window the user can click in; runs choose their own headless.
# A session's own browser settings, when it has them, replace the backend, proxy and humanize.
BROWSER_CONFIG = BrowserConfig(backend="chromium", headless=False)
# Records a session whose backend cannot record: the closest stealth backend, keeping its proxy.
RECORDING_FALLBACK_BACKEND = "patchright"

SERVER_SETTINGS = server_settings_from_env(os.environ)

# Initialize components
storage = StorageManager(os.path.join(SERVER_SETTINGS.data_dir, "scraper.db"))
browser_worker = BrowserWorker()
scheduler = ScraperScheduler(storage, browser_worker, BROWSER_CONFIG)

# Global recorder instance (one at a time)
current_recorder: Optional[SessionRecorder] = None
# The browser settings the recording session is saved with; None means BROWSER_CONFIG.
current_browser_settings: Optional[dict] = None
recorder_lock = threading.Lock()


# ==================== API TOKEN ====================

@app.before_request
def require_api_token():
    """Refuses an /api request without the configured bearer token; the page itself stays open."""
    if SERVER_SETTINGS.api_token is None or not request.path.startswith('/api/'):
        return None
    sent_token = request.headers.get('Authorization', '').removeprefix('Bearer ')
    # compare_digest takes as long for a near miss as for a wrong first character.
    if not hmac.compare_digest(sent_token.encode(), SERVER_SETTINGS.api_token.encode()):
        return jsonify({"error": "Missing or wrong API token"}), 401
    return None


# ==================== WEB ROUTES ====================

@app.route('/')
def index():
    """Serve the main dashboard."""
    return render_template('index.html')


# ==================== SESSION API ====================

@app.route('/api/sessions/start', methods=['POST'])
def start_session():
    """Start recording a new session."""
    global current_recorder, current_browser_settings
    
    with recorder_lock:
        if current_recorder:
            return jsonify({"error": "Recording already in progress"}), 400

        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({"error": "URL is required"}), 400

        try:
            browser_settings = (
                BrowserSettings.model_validate(data['browser']).model_dump()
                if data.get('browser') else None
            )
        except ValidationError as validation_error:
            return jsonify({"error": f"Invalid browser settings: {validation_error}"}), 400

        recording_browser_config = dataclasses.replace(BROWSER_CONFIG, **(browser_settings or {}))
        if recording_browser_config.backend in BACKENDS_WITHOUT_BINDINGS:
            recording_browser_config = dataclasses.replace(
                recording_browser_config, backend=RECORDING_FALLBACK_BACKEND, humanize=False
            )

        recorder = SessionRecorder(recording_browser_config)
        try:
            browser_worker.submit(recorder.start(url)).result()
        # ValueError is a proxy URL that cannot be launched, such as one naming an unset env var.
        except (*BROWSER_ERRORS, ValueError) as browser_error:
            return jsonify({"error": f"Could not open {url}: {browser_error}"}), 400
        current_recorder = recorder
        current_browser_settings = browser_settings

        return jsonify({
            "success": True,
            "message": "Recording started",
            "url": url
        })


@app.route('/api/sessions/selector', methods=['POST'])
def activate_selector():
    """Activate element selector mode."""
    global current_recorder
    
    if not current_recorder:
        return jsonify({"error": "No active recording"}), 400

    browser_worker.submit(current_recorder.activate_picker()).result()

    return jsonify({
        "success": True,
        "message": "Selector mode activated"
    })


@app.route('/api/sessions/rows', methods=['POST'])
def activate_row_picker():
    """Activate row selector mode."""
    global current_recorder

    if not current_recorder:
        return jsonify({"error": "No active recording"}), 400

    browser_worker.submit(current_recorder.activate_row_picker()).result()

    return jsonify({
        "success": True,
        "message": "Row selector mode activated"
    })


@app.route('/api/sessions/next-button', methods=['POST'])
def activate_next_button_picker():
    """Activate next page button selector mode."""
    global current_recorder

    if not current_recorder:
        return jsonify({"error": "No active recording"}), 400
    if current_recorder.row_table is None:
        return jsonify({"error": "Select rows first"}), 400

    browser_worker.submit(current_recorder.activate_next_button_picker()).result()

    return jsonify({
        "success": True,
        "message": "Next button selector mode activated"
    })


@app.route('/api/sessions/infinite-scroll', methods=['POST'])
def use_infinite_scroll():
    """Make the row table load more rows by scrolling."""
    global current_recorder

    if not current_recorder:
        return jsonify({"error": "No active recording"}), 400
    if current_recorder.row_table is None:
        return jsonify({"error": "Select rows first"}), 400

    current_recorder.use_infinite_scroll()

    return jsonify({
        "success": True,
        "message": "Infinite scroll enabled"
    })


@app.route('/api/sessions/stop', methods=['POST'])
def stop_session():
    """Stop recording and save session."""
    global current_recorder
    
    with recorder_lock:
        if not current_recorder:
            return jsonify({"error": "No active recording"}), 400

        session_data = browser_worker.submit(current_recorder.stop()).result()
        typed_name = request.json.get('name', '').strip()
        name = typed_name or urlparse(session_data['url']).hostname or session_data['url']

        # Save to database
        session_id = storage.create_session(
            name=name,
            url=session_data['url'],
            actions=session_data['actions'],
            selectors=session_data.get('selectors', []),
            table=session_data['table'],
            browser=current_browser_settings
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
    scheduler.remove_session_schedules(session_id)
    storage.delete_session(session_id)
    return jsonify({"success": True, "message": "Session deleted"})


@app.route('/api/sessions/<int:session_id>/replay', methods=['POST'])
def replay_session(session_id):
    """Manually replay a session. Besides headless, the body may set max_pages, max_scrolls and
    max_rows for this run only."""
    data = request.json or {}
    headless = data.pop('headless', False)
    try:
        run_options = RunOptions.model_validate(data)
    except ValidationError as validation_error:
        return jsonify({"error": f"Invalid run options: {validation_error}"}), 400
    result = scheduler.run_manual(session_id, headless=headless, run_options=run_options)
    return jsonify(result)


# ==================== FLOW FILE API ====================

@app.route('/api/sessions/<int:session_id>/flow', methods=['GET'])
def export_session_flow(session_id):
    """Download a session as a flow file."""
    session = storage.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    flow_text = flow_file_json(flow_from_recorded_session(session['name'], session))
    return send_file(
        io.BytesIO(flow_text.encode()),
        mimetype='application/json',
        as_attachment=True,
        download_name=f"{session['name']}.flow.json"
    )


@app.route('/api/flows', methods=['POST'])
def import_flow():
    """Save an uploaded flow file as a new session."""
    try:
        flow = FlowFile.model_validate_json(request.get_data())
    except ValidationError as validation_error:
        return jsonify({"error": f"Invalid flow file: {validation_error}"}), 400

    session_id = storage.create_session(name=flow.name, **recorded_session_from_flow(flow))

    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Flow imported"
    })


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


@app.route('/api/data/<int:data_id>/export', methods=['GET'])
def export_extraction(data_id):
    """Download one extraction as CSV, JSON or JSONL."""
    format_name = request.args.get('format', '')
    export_format = EXPORT_FORMATS.get(format_name)
    if not export_format:
        return jsonify({"error": f"Format must be one of: {', '.join(EXPORT_FORMATS)}"}), 400

    extraction = storage.get_extraction(data_id)
    if not extraction:
        return jsonify({"error": "Data not found"}), 404

    export_text = export_format.write_records(extraction['data'])
    return send_file(
        io.BytesIO(export_text.encode()),
        mimetype=export_format.mimetype,
        as_attachment=True,
        download_name=f"{extraction['session_name']}-{data_id}.{format_name}"
    )


# ==================== STATUS API ====================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get application status."""
    return jsonify({
        "recording": current_recorder is not None,
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
    logger.info(f"Dashboard: http://{SERVER_SETTINGS.host}:{SERVER_SETTINGS.port}")
    # waitress.serve returns, instead of raising, when it is stopped with Ctrl+C.
    waitress.serve(app, host=SERVER_SETTINGS.host, port=SERVER_SETTINGS.port)
    logger.info("Shutting down...")
    scheduler.shutdown()
    browser_worker.stop()
