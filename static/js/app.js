// Visual Data Scraper - Dashboard JavaScript
// API client and UI management

const API_BASE = '/api';
let recordingStatus = 'idle';
let statusCheckInterval = null;

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    startStatusPolling();
});

function initializeApp() {
    loadSessions();
    loadSchedules();
    loadData();
}

function setupEventListeners() {
    // Recording controls
    document.getElementById('start-recording-btn').addEventListener('click', startRecording);
    document.getElementById('activate-selector-btn').addEventListener('click', activateSelector);
    document.getElementById('stop-recording-btn').addEventListener('click', stopRecording);
}

// ==================== STATUS POLLING ====================

function startStatusPolling() {
    statusCheckInterval = setInterval(updateStatus, 2000);
    updateStatus();
}

async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const status = await response.json();

        recordingStatus = status.recording ? 'recording' : 'idle';
        updateRecordingUI();

        // Update stats
        document.getElementById('sessions-count').textContent = status.sessions_count;
        document.getElementById('schedules-count').textContent = status.schedules_count;

    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

function updateRecordingUI() {
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const startBtn = document.getElementById('start-recording-btn');
    const selectorBtn = document.getElementById('activate-selector-btn');
    const stopBtn = document.getElementById('stop-recording-btn');

    if (recordingStatus === 'recording') {
        statusDot.className = 'status-dot recording';
        statusText.textContent = 'Recording';
        startBtn.disabled = true;
        selectorBtn.disabled = false;
        stopBtn.disabled = false;
    } else {
        statusDot.className = 'status-dot idle';
        statusText.textContent = 'Idle';
        startBtn.disabled = false;
        selectorBtn.disabled = true;
        stopBtn.disabled = true;
    }
}

// ==================== RECORDING CONTROLS ====================

async function startRecording() {
    const urlInput = document.getElementById('url-input');
    let url = urlInput.value.trim();

    if (!url) {
        alert('Please enter a URL');
        return;
    }

    // Auto-add https:// if protocol is missing
    if (!url.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//)) {
        url = 'https://' + url;
        urlInput.value = url; // Update the input field
    }

    // Validate URL
    try {
        new URL(url);
    } catch {
        alert('Please enter a valid URL');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/sessions/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Recording started! Browser window opened.', 'success');
            recordingStatus = 'recording';
            updateRecordingUI();
        } else {
            showNotification(result.error || 'Failed to start recording', 'error');
        }
    } catch (error) {
        showNotification('Error starting recording: ' + error.message, 'error');
    }
}

async function activateSelector() {
    try {
        const response = await fetch(`${API_BASE}/sessions/selector`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Element selector activated! Click elements in the browser.', 'success');
        } else {
            showNotification(result.error || 'Failed to activate selector', 'error');
        }
    } catch (error) {
        showNotification('Error activating selector: ' + error.message, 'error');
    }
}

async function stopRecording() {
    // Generate UUID for session name
    const name = 'Session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);

    try {
        const response = await fetch(`${API_BASE}/sessions/stop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Session saved successfully!', 'success');
            recordingStatus = 'idle';
            updateRecordingUI();
            document.getElementById('url-input').value = '';
            loadSessions();
        } else {
            showNotification(result.error || 'Failed to save session', 'error');
        }
    } catch (error) {
        showNotification('Error stopping recording: ' + error.message, 'error');
    }
}

// ==================== SESSIONS ====================

async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE}/sessions`);
        const sessions = await response.json();

        renderSessions(sessions);
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

function renderSessions(sessions) {
    const container = document.getElementById('sessions-grid');

    if (sessions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📹</div>
                <div class="empty-state-text">No sessions yet</div>
                <p>Start recording to create your first session</p>
            </div>
        `;
        return;
    }

    container.innerHTML = sessions.map(session => `
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(session.name)}</h3>
                <div class="card-meta">
                    <span>📅 ${formatDate(session.created_at)}</span>
                    <span>▶️ ${session.run_count} runs</span>
                </div>
                <a href="${escapeHtml(session.url)}" target="_blank" class="card-url">${escapeHtml(session.url)}</a>
            </div>
            
            <div class="card-stats">
                <div class="stat">
                    <div class="stat-value">${session.actions.length}</div>
                    <div class="stat-label">Actions</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${session.selectors.length}</div>
                    <div class="stat-label">Selectors</div>
                </div>
            </div>
            
            <div class="card-actions">
                <button class="btn btn-success btn-small" onclick="replaySession(${session.id})">
                    ▶️ Replay
                </button>
                <button class="btn btn-primary btn-small" onclick="createSchedule(${session.id})">
                    ⏰ Schedule
                </button>
                <button class="btn btn-secondary btn-small" onclick="viewData(${session.id})">
                    📊 Data
                </button>
                <button class="btn btn-danger btn-small" onclick="deleteSession(${session.id})">
                    🗑️ Delete
                </button>
            </div>
        </div>
    `).join('');
}

async function replaySession(sessionId) {
    if (!confirm('Replay this session now?')) return;

    showNotification('Replaying session...', 'info');

    try {
        const response = await fetch(`${API_BASE}/sessions/${sessionId}/replay`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`Extracted ${result.items_count} items!`, 'success');
            loadData();
        } else {
            showNotification(result.error || 'Replay failed', 'error');
        }
    } catch (error) {
        showNotification('Error replaying session: ' + error.message, 'error');
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Delete this session? This cannot be undone.')) return;

    try {
        await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' });
        showNotification('Session deleted', 'success');
        loadSessions();
    } catch (error) {
        showNotification('Error deleting session: ' + error.message, 'error');
    }
}

// ==================== SCHEDULES ====================

async function loadSchedules() {
    try {
        const response = await fetch(`${API_BASE}/schedules`);
        const schedules = await response.json();

        renderSchedules(schedules);
    } catch (error) {
        console.error('Error loading schedules:', error);
    }
}

function renderSchedules(schedules) {
    const container = document.getElementById('schedules-list');

    if (schedules.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⏰</div>
                <div class="empty-state-text">No schedules yet</div>
                <p>Create a schedule to automate data extraction</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Session</th>
                    <th>Frequency</th>
                    <th>Next Run</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${schedules.map(schedule => `
                    <tr>
                        <td>
                            <strong>${escapeHtml(schedule.session_name)}</strong><br>
                            <small style="color: var(--text-secondary)">${escapeHtml(schedule.session_url)}</small>
                        </td>
                        <td>Every ${schedule.frequency_minutes} min</td>
                        <td>${formatDate(schedule.next_run)}</td>
                        <td>
                            <span class="badge ${schedule.enabled ? 'badge-success' : 'badge-danger'}">
                                ${schedule.enabled ? 'Active' : 'Paused'}
                            </span>
                        </td>
                        <td>
                            <button class="btn btn-secondary btn-small" onclick="toggleSchedule(${schedule.id}, ${!schedule.enabled})">
                                ${schedule.enabled ? '⏸️ Pause' : '▶️ Resume'}
                            </button>
                            <button class="btn btn-danger btn-small" onclick="deleteSchedule(${schedule.id})">
                                🗑️
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function createSchedule(sessionId) {
    const frequency = prompt('Enter frequency in minutes (e.g., 60 for hourly):');
    if (!frequency) return;

    const minutes = parseInt(frequency);
    if (isNaN(minutes) || minutes < 1) {
        alert('Please enter a valid number of minutes');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/schedules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, frequency_minutes: minutes })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Schedule created!', 'success');
            loadSchedules();
        } else {
            showNotification(result.error || 'Failed to create schedule', 'error');
        }
    } catch (error) {
        showNotification('Error creating schedule: ' + error.message, 'error');
    }
}

async function toggleSchedule(scheduleId, enabled) {
    try {
        await fetch(`${API_BASE}/schedules/${scheduleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        showNotification(enabled ? 'Schedule resumed' : 'Schedule paused', 'success');
        loadSchedules();
    } catch (error) {
        showNotification('Error updating schedule: ' + error.message, 'error');
    }
}

async function deleteSchedule(scheduleId) {
    if (!confirm('Delete this schedule?')) return;

    try {
        await fetch(`${API_BASE}/schedules/${scheduleId}`, { method: 'DELETE' });
        showNotification('Schedule deleted', 'success');
        loadSchedules();
    } catch (error) {
        showNotification('Error deleting schedule: ' + error.message, 'error');
    }
}

// ==================== DATA ====================

async function loadData() {
    try {
        const response = await fetch(`${API_BASE}/data?limit=20`);
        const data = await response.json();

        renderData(data);
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

function renderData(dataList) {
    const container = document.getElementById('data-list');

    if (dataList.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📊</div>
                <div class="empty-state-text">No data yet</div>
                <p>Replay a session to extract data</p>
            </div>
        `;
        return;
    }

    container.innerHTML = dataList.map(item => `
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(item.session_name)}</h3>
                <div class="card-meta">
                    <span>📅 ${formatDate(item.extracted_at)}</span>
                    <span>📊 ${item.data.length} items</span>
                </div>
            </div>
            
            <div style="max-height: 200px; overflow-y: auto; margin: 15px 0;">
                ${item.data.slice(0, 5).map(d => `
                    <div style="padding: 8px; background: var(--bg-card); margin-bottom: 8px; border-radius: 6px;">
                        <strong style="color: var(--primary)">${escapeHtml(d.label || d.selector)}</strong><br>
                        <span style="color: var(--text-secondary); font-size: 0.9rem;">${escapeHtml(d.value.substring(0, 100))}</span>
                    </div>
                `).join('')}
                ${item.data.length > 5 ? `<p style="color: var(--text-secondary); text-align: center;">+ ${item.data.length - 5} more items</p>` : ''}
            </div>
            
            <div class="card-actions">
                <button class="btn btn-primary btn-small" onclick="downloadData(${item.id}, 'json')">
                    💾 JSON
                </button>
                <button class="btn btn-secondary btn-small" onclick="downloadData(${item.id}, 'csv')">
                    📄 CSV
                </button>
            </div>
        </div>
    `).join('');
}

async function viewData(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/data/${sessionId}`);
        const data = await response.json();

        if (data.length === 0) {
            alert('No data available for this session yet. Try replaying it first.');
            return;
        }

        // Scroll to data section
        document.getElementById('data-section').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        showNotification('Error loading data: ' + error.message, 'error');
    }
}

function downloadData(dataId, format) {
    // In a real implementation, this would fetch the specific data item
    // For now, we'll show a notification
    showNotification(`Download ${format.toUpperCase()} functionality coming soon!`, 'info');
}

// ==================== UTILITIES ====================

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showNotification(message, type = 'info') {
    // Simple notification - could be enhanced with a toast library
    const colors = {
        success: 'var(--success)',
        error: 'var(--danger)',
        info: 'var(--primary)',
        warning: 'var(--warning)'
    };

    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type]};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: fadeIn 0.3s ease;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
