// Visual Data Scraper - Dashboard JavaScript
// API client and UI management

const API_BASE = '/api';
const API_TOKEN_KEY = 'recordscrape.apiToken';
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
    document.getElementById('backend-select').addEventListener('change', allowHumanizeOnCloakBrowserOnly);
    document.getElementById('activate-selector-btn').addEventListener('click', () =>
        activatePicker('selector', 'Element selector', 'Click elements in the browser.'));
    document.getElementById('activate-row-picker-btn').addEventListener('click', () =>
        activatePicker('rows', 'Row selector', 'Click the same field in two rows.'));
    document.getElementById('activate-next-button-picker-btn').addEventListener('click', () =>
        activatePicker('next-button', 'Next button selector', 'Click the button that opens the next page.'));
    document.getElementById('use-infinite-scroll-btn').addEventListener('click', () =>
        activatePicker('infinite-scroll', 'Infinite scroll', 'Each run scrolls to load more rows.'));
    document.getElementById('stop-recording-btn').addEventListener('click', stopRecording);

    document.getElementById('import-flow-input').addEventListener('change', importFlow);
}

// ==================== STATUS POLLING ====================

function startStatusPolling() {
    statusCheckInterval = setInterval(updateStatus, 2000);
    updateStatus();
}

async function updateStatus() {
    try {
        const response = await apiFetch(`/status`);
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
    const rowPickerBtn = document.getElementById('activate-row-picker-btn');
    const nextButtonPickerBtn = document.getElementById('activate-next-button-picker-btn');
    const infiniteScrollBtn = document.getElementById('use-infinite-scroll-btn');
    const stopBtn = document.getElementById('stop-recording-btn');

    if (recordingStatus === 'recording') {
        statusDot.className = 'status-dot recording';
        statusText.textContent = 'Recording';
        startBtn.disabled = true;
        selectorBtn.disabled = false;
        rowPickerBtn.disabled = false;
        nextButtonPickerBtn.disabled = false;
        infiniteScrollBtn.disabled = false;
        stopBtn.disabled = false;
    } else {
        statusDot.className = 'status-dot idle';
        statusText.textContent = 'Idle';
        startBtn.disabled = false;
        selectorBtn.disabled = true;
        rowPickerBtn.disabled = true;
        nextButtonPickerBtn.disabled = true;
        infiniteScrollBtn.disabled = true;
        stopBtn.disabled = true;
    }
}

// ==================== RECORDING CONTROLS ====================

function allowHumanizeOnCloakBrowserOnly() {
    const humanizeCheckbox = document.getElementById('humanize-checkbox');
    humanizeCheckbox.disabled = document.getElementById('backend-select').value !== 'cloakbrowser';
    if (humanizeCheckbox.disabled) {
        humanizeCheckbox.checked = false;
    }
}

function chosenBrowserSettings() {
    return {
        backend: document.getElementById('backend-select').value,
        proxy: document.getElementById('proxy-input').value.trim() || null,
        humanize: document.getElementById('humanize-checkbox').checked
    };
}

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
        const response = await apiFetch(`/sessions/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, browser: chosenBrowserSettings() })
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

async function activatePicker(endpoint, pickerName, instructions) {
    try {
        const response = await apiFetch(`/sessions/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`${pickerName} activated! ${instructions}`, 'success');
        } else {
            showNotification(result.error || `Failed to activate ${pickerName.toLowerCase()}`, 'error');
        }
    } catch (error) {
        showNotification(`Error activating ${pickerName.toLowerCase()}: ` + error.message, 'error');
    }
}

async function stopRecording() {
    const sessionNameInput = document.getElementById('session-name-input');
    const name = sessionNameInput.value.trim();

    try {
        const response = await apiFetch(`/sessions/stop`, {
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
            sessionNameInput.value = '';
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
        const response = await apiFetch(`/sessions`);
        const sessions = await response.json();

        renderSessions(sessions);
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

// Names the proxy's presence only: its URL can hold a password typed literally.
function describeBrowserSettings(browserSettings) {
    if (!browserSettings) {
        return 'chromium';
    }
    const settingLabels = [escapeHtml(browserSettings.backend)];
    if (browserSettings.proxy) {
        settingLabels.push('proxy');
    }
    if (browserSettings.humanize) {
        settingLabels.push('humanize');
    }
    return settingLabels.join(' + ');
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
                    <span>🌐 ${describeBrowserSettings(session.browser)}</span>
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
                <div class="stat">
                    <div class="stat-value">${session.table ? session.table.columns.length : 0}</div>
                    <div class="stat-label">Row Columns</div>
                </div>
            </div>
            
            <div style="padding: 10px; border-top: 1px solid rgba(255,255,255,0.1);">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                    <input type="checkbox" id="headless-${session.id}" style="cursor: pointer;">
                    <span>Headless mode (faster, no browser window)</span>
                </label>
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
                <button class="btn btn-secondary btn-small" onclick="downloadFromApi('/sessions/${session.id}/flow')">
                    📤 Export
                </button>
                <button class="btn btn-danger btn-small" onclick="deleteSession(${session.id})">
                    🗑️ Delete
                </button>
            </div>
        </div>
    `).join('');
}

async function replaySession(sessionId) {
    const headlessCheckbox = document.getElementById(`headless-${sessionId}`);
    const headless = headlessCheckbox ? headlessCheckbox.checked : false;

    const mode = headless ? 'headless mode' : 'visible browser';
    if (!confirm(`Replay this session now in ${mode}?`)) return;

    showNotification(`Replaying session in ${mode}...`, 'info');

    try {
        const response = await apiFetch(`/sessions/${sessionId}/replay`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ headless })
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`Extracted ${result.items_count} items!`, 'success');
            loadSessions();
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
        await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
        showNotification('Session deleted', 'success');
        loadSessions();
    } catch (error) {
        showNotification('Error deleting session: ' + error.message, 'error');
    }
}

async function importFlow(event) {
    const fileInput = event.target;
    const flowFile = fileInput.files[0];
    if (!flowFile) return;

    try {
        const response = await apiFetch(`/flows`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: await flowFile.text()
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`Imported ${flowFile.name}`, 'success');
            loadSessions();
        } else {
            showNotification(result.error || 'Import failed', 'error');
        }
    } catch (error) {
        showNotification('Error importing flow: ' + error.message, 'error');
    } finally {
        // Clearing lets the same file be picked again after it is fixed; otherwise no change event fires.
        fileInput.value = '';
    }
}

// ==================== SCHEDULES ====================

async function loadSchedules() {
    try {
        const response = await apiFetch(`/schedules`);
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
        const response = await apiFetch(`/schedules`, {
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
        await apiFetch(`/schedules/${scheduleId}`, {
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
        await apiFetch(`/schedules/${scheduleId}`, { method: 'DELETE' });
        showNotification('Schedule deleted', 'success');
        loadSchedules();
    } catch (error) {
        showNotification('Error deleting schedule: ' + error.message, 'error');
    }
}

// ==================== DATA ====================

async function loadData() {
    try {
        const response = await apiFetch(`/data?limit=20`);
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
                ${item.data.slice(0, 5).map(entry => `
                    <div style="padding: 8px; background: var(--bg-card); margin-bottom: 8px; border-radius: 6px;">
                        ${item.has_table ? renderTableRecord(entry) : renderPickedValue(entry)}
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
                <button class="btn btn-secondary btn-small" onclick="downloadData(${item.id}, 'jsonl')">
                    📃 JSONL
                </button>
            </div>
        </div>
    `).join('');
}

function renderPickedValue(pickedValue) {
    return `
        <strong style="color: var(--primary)">${escapeHtml(pickedValue.label || pickedValue.selector)}</strong><br>
        <span style="color: var(--text-secondary); font-size: 0.9rem;">${escapeHtml(pickedValue.value.substring(0, 100))}</span>
    `;
}

function renderTableRecord(tableRecord) {
    return Object.entries(tableRecord).map(([columnName, cellValue]) => `
        <strong style="color: var(--primary)">${escapeHtml(columnName)}</strong>:
        <span style="color: var(--text-secondary); font-size: 0.9rem;">${escapeHtml(cellValue.substring(0, 100))}</span>
    `).join('<br>');
}

async function viewData(sessionId) {
    try {
        const response = await apiFetch(`/data/${sessionId}`);
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
    downloadFromApi(`/data/${dataId}/export?format=${format}`);
}

// ==================== API ACCESS ====================

// A server started with RECORDSCRAPE_TOKEN refuses /api requests without it; the dashboard asks
// for it on the first refusal and keeps it in this browser.
async function apiFetch(path, options = {}) {
    const sentToken = localStorage.getItem(API_TOKEN_KEY);
    const response = await fetch(`${API_BASE}${path}`, withApiToken(options, sentToken));
    if (response.status !== 401) {
        return response;
    }
    // prompt() blocks, so requests refused together ask once: the rest retry with the stored token.
    if (localStorage.getItem(API_TOKEN_KEY) === sentToken) {
        const enteredToken = window.prompt('This server needs its API token (RECORDSCRAPE_TOKEN):');
        if (!enteredToken) {
            return response;
        }
        localStorage.setItem(API_TOKEN_KEY, enteredToken.trim());
    }
    return fetch(`${API_BASE}${path}`, withApiToken(options, localStorage.getItem(API_TOKEN_KEY)));
}

function withApiToken(options, apiToken) {
    if (!apiToken) {
        return options;
    }
    return { ...options, headers: { ...options.headers, Authorization: `Bearer ${apiToken}` } };
}

// Downloads through fetch, because following a link cannot send the API token.
async function downloadFromApi(path) {
    const response = await apiFetch(path);
    if (!response.ok) {
        const result = await response.json();
        showNotification('Download failed: ' + result.error, 'error');
        return;
    }
    const downloadLink = document.createElement('a');
    downloadLink.href = URL.createObjectURL(await response.blob());
    downloadLink.download = attachmentFilename(response.headers.get('Content-Disposition'));
    downloadLink.click();
    // Revoked a turn later: some browsers start reading the blob after click() returns.
    setTimeout(() => URL.revokeObjectURL(downloadLink.href), 0);
}

function attachmentFilename(contentDisposition) {
    const encodedFilename = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition);
    if (encodedFilename) {
        return decodeURIComponent(encodedFilename[1]);
    }
    return /filename="?([^";]+)"?/i.exec(contentDisposition)[1];
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
