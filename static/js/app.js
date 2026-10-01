/*
 * The RecordScrape dashboard page: switches between its views, calls the /api routes and renders
 * what they return. It must not keep any state the server owns beyond the last list it fetched,
 * and must never write server text into HTML without escapeHtml.
 */

const API_BASE = '/api';
const API_TOKEN_KEY = 'recordscrape.apiToken';
const VIEW_NAMES = ['overview', 'record', 'sessions', 'runs', 'schedules'];
const DEFAULT_VIEW_NAME = 'overview';
const RUN_LIST_VIEW_NAMES = ['overview', 'runs'];
const STATUS_POLL_INTERVAL_MS = 2000;
const RUNS_POLL_INTERVAL_MS = 5000;
const RUNS_LIST_LIMIT = 50;
const OVERVIEW_RUNS_COUNT = 5;
const DEFAULT_SCHEDULE_MINUTES = 60;
const MISSING_VALUE = '-';
const RECORDING_ONLY_BUTTON_IDS = [
    'activate-selector-btn',
    'activate-row-picker-btn',
    'activate-next-button-picker-btn',
    'use-infinite-scroll-btn',
    'stop-recording-btn'
];
// Keyed by a row table's pagination mode: the limit's key in the stored table, the replay option
// that overrides it for one run, and how the dashboard names it.
const PAGINATION_LIMITS = {
    nextButton: { tableKey: 'maxPages', label: 'Max pages', unit: 'pages', description: 'Next button' },
    infiniteScroll: { tableKey: 'maxScrolls', label: 'Max scrolls', unit: 'scrolls', description: 'Infinite scroll' }
};
const TOAST_DURATION_MS = { success: 3500, info: 3500, error: 6500 };

let recordingStatus = 'idle';
let sessionsById = new Map();
let latestRuns = [];
let replayedSession = null;
let editedSession = null;
let scheduledSession = null;
let viewedRunId = null;
let viewedRunRecords = [];

const byId = (elementId) => document.getElementById(elementId);

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    showCurrentView();
    startPolling();
});

function setupEventListeners() {
    window.addEventListener('hashchange', showCurrentView);
    document.addEventListener('click', closeDialogOfClickedButton);

    byId('start-recording-btn').addEventListener('click', startRecording);
    byId('backend-select').addEventListener('change', allowHumanizeOnCloakBrowserOnly);
    byId('activate-selector-btn').addEventListener('click', () =>
        activatePicker('selector', 'Element selector', 'Click elements in the browser.'));
    byId('activate-row-picker-btn').addEventListener('click', () =>
        activatePicker('rows', 'Row selector', 'Click the same field in two rows.'));
    byId('activate-next-button-picker-btn').addEventListener('click', () =>
        activatePicker('next-button', 'Next button selector', 'Click the button that opens the next page.'));
    byId('use-infinite-scroll-btn').addEventListener('click', () =>
        activatePicker('infinite-scroll', 'Infinite scroll', 'Each run scrolls to load more rows.'));
    byId('stop-recording-btn').addEventListener('click', stopRecording);

    byId('import-flow-input').addEventListener('change', importFlow);
    byId('refresh-sessions-btn').addEventListener('click', loadSessions);
    byId('sessions-grid').addEventListener('click', runSessionCardAction);

    byId('refresh-runs-btn').addEventListener('click', loadRuns);
    for (const runsTableBodyId of ['runs-table-body', 'overview-runs-body']) {
        byId(runsTableBodyId).addEventListener('click', openClickedRun);
        byId(runsTableBodyId).addEventListener('keydown', openRunOnEnter);
    }

    byId('refresh-schedules-btn').addEventListener('click', loadSchedules);
    byId('schedules-list').addEventListener('change', toggleSwitchedSchedule);
    byId('schedules-list').addEventListener('click', deleteClickedSchedule);

    byId('replay-form').addEventListener('submit', runReplay);
    byId('session-edit-form').addEventListener('submit', saveSessionEdit);
    byId('session-edit-columns').addEventListener('click', removeClickedColumn);
    byId('copy-latest-url-btn').addEventListener('click', () =>
        copyText(byId('session-edit-latest-url').value, 'Latest data URL copied'));
    byId('schedule-form').addEventListener('submit', createSchedule);

    byId('run-viewer-table-tab').addEventListener('click', () => selectRunViewerTab('table'));
    byId('run-viewer-json-tab').addEventListener('click', () => selectRunViewerTab('json'));
    byId('copy-json-btn').addEventListener('click', () =>
        copyText(byId('run-viewer-json').textContent, 'JSON copied'));
    byId('export-format-select').addEventListener('change', showJsonExportOptions);
    byId('export-download-btn').addEventListener('click', downloadViewedRun);
}

// ==================== VIEWS ====================

const VIEW_LOADERS = {
    overview: loadRuns,
    sessions: loadSessions,
    runs: loadRuns,
    schedules: loadSchedules
};

function currentViewName() {
    const hashViewName = location.hash.slice(1);
    return VIEW_NAMES.includes(hashViewName) ? hashViewName : DEFAULT_VIEW_NAME;
}

function showCurrentView() {
    const viewName = currentViewName();
    for (const view of document.querySelectorAll('.view')) {
        view.hidden = view.dataset.view !== viewName;
    }
    for (const navLink of document.querySelectorAll('.nav-link')) {
        if (navLink.dataset.view === viewName) {
            navLink.setAttribute('aria-current', 'page');
        } else {
            navLink.removeAttribute('aria-current');
        }
    }
    VIEW_LOADERS[viewName]?.();
}

function closeDialogOfClickedButton(event) {
    const closeButton = event.target.closest('[data-close-dialog]');
    if (closeButton) {
        closeButton.closest('dialog').close();
    }
}

// ==================== POLLING ====================

function startPolling() {
    updateStatus();
    updateHealth();
    setInterval(() => {
        updateStatus();
        updateHealth();
    }, STATUS_POLL_INTERVAL_MS);
    setInterval(refreshRunsOnRunListViews, RUNS_POLL_INTERVAL_MS);
}

function refreshRunsOnRunListViews() {
    if (RUN_LIST_VIEW_NAMES.includes(currentViewName())) {
        loadRuns();
    }
}

async function updateStatus() {
    try {
        const response = await apiFetch('/status');
        if (!response.ok) return;
        const status = await response.json();

        recordingStatus = status.recording ? 'recording' : 'idle';
        updateRecordingUI();

        const lastDayStats = status.last_24_hours;
        byId('sessions-count').textContent = formatCount(status.sessions_count);
        byId('schedules-count').textContent = formatCount(status.schedules_count);
        byId('runs-24h-count').textContent = formatCount(lastDayStats.runs);
        byId('failed-24h-count').textContent = formatCount(lastDayStats.failed_runs);
        byId('items-24h-count').textContent = formatCount(lastDayStats.items_extracted);
        byId('failed-24h-tile').classList.toggle('stat-tile-alert', lastDayStats.failed_runs > 0);
        byId('overview-scheduler-text').textContent = status.scheduler_running ? 'Running' : 'Stopped';
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

// /healthz needs no token, so it goes through plain fetch rather than apiFetch.
async function updateHealth() {
    const healthIndicator = byId('health-indicator');
    const healthText = byId('health-text');
    try {
        const response = await fetch('/healthz');
        const health = await response.json();
        healthIndicator.dataset.health = response.ok ? 'healthy' : 'unhealthy';
        if (response.ok) {
            healthText.textContent = 'Healthy';
        } else {
            healthText.textContent = health.scheduler_running ? 'Browser worker stopped' : 'Scheduler stopped';
        }
    } catch {
        healthIndicator.dataset.health = 'unhealthy';
        healthText.textContent = 'Server unreachable';
    }
}

function updateRecordingUI() {
    const isRecording = recordingStatus === 'recording';
    byId('status-dot').className = isRecording ? 'status-dot recording' : 'status-dot idle';
    byId('status-text').textContent = isRecording ? 'Recording' : 'Idle';
    byId('start-recording-btn').disabled = isRecording;
    for (const buttonId of RECORDING_ONLY_BUTTON_IDS) {
        byId(buttonId).disabled = !isRecording;
    }
    const overviewRecordingText = byId('overview-recording-text');
    overviewRecordingText.textContent = isRecording ? 'Recording' : 'Idle';
    overviewRecordingText.classList.toggle('is-recording', isRecording);
}

// ==================== RECORDING CONTROLS ====================

function allowHumanizeOnCloakBrowserOnly() {
    const humanizeCheckbox = byId('humanize-checkbox');
    humanizeCheckbox.disabled = byId('backend-select').value !== 'cloakbrowser';
    if (humanizeCheckbox.disabled) {
        humanizeCheckbox.checked = false;
    }
}

function chosenBrowserSettings() {
    return {
        backend: byId('backend-select').value,
        proxy: byId('proxy-input').value.trim() || null,
        humanize: byId('humanize-checkbox').checked
    };
}

async function startRecording() {
    const urlInput = byId('url-input');
    let url = urlInput.value.trim();

    if (!url) {
        showNotification('Please enter a URL', 'error');
        return;
    }

    if (!url.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//)) {
        url = 'https://' + url;
        urlInput.value = url;
    }

    try {
        new URL(url);
    } catch {
        showNotification('Please enter a valid URL', 'error');
        return;
    }

    try {
        const response = await apiFetch('/sessions/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, browser: chosenBrowserSettings() })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Recording started. A browser window opened.', 'success');
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
            showNotification(`${pickerName} activated. ${instructions}`, 'success');
        } else {
            showNotification(result.error || `Failed to activate ${pickerName.toLowerCase()}`, 'error');
        }
    } catch (error) {
        showNotification(`Error activating ${pickerName.toLowerCase()}: ` + error.message, 'error');
    }
}

async function stopRecording() {
    const sessionNameInput = byId('session-name-input');
    const name = sessionNameInput.value.trim();

    try {
        const response = await apiFetch('/sessions/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Session saved', 'success');
            recordingStatus = 'idle';
            updateRecordingUI();
            byId('url-input').value = '';
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

const SESSION_CARD_ACTIONS = {
    replay: openReplayDialog,
    edit: openSessionEditDialog,
    export: (session) => downloadFromApi(`/sessions/${session.id}/flow`),
    schedule: openScheduleDialog,
    delete: deleteSession
};

async function loadSessions() {
    try {
        const response = await apiFetch('/sessions');
        if (!response.ok) return;
        const sessions = await response.json();
        sessionsById = new Map(sessions.map((session) => [session.id, session]));
        renderSessions(sessions);
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

function renderSessions(sessions) {
    const sessionsGrid = byId('sessions-grid');
    if (sessions.length === 0) {
        sessionsGrid.innerHTML = `
            <div class="empty-state">
                <strong>No sessions yet</strong>
                <a href="#record">Record a session</a> or import a flow file.
            </div>`;
        return;
    }
    sessionsGrid.innerHTML = sessions.map(sessionCardHtml).join('');
}

function sessionCardHtml(session) {
    const lastRun = parseUtcTimestamp(session.last_run);
    return `
        <article class="session-card" data-session-id="${session.id}">
            <header class="session-card-header">
                <h3 class="session-card-title">${escapeHtml(session.name)}</h3>
                <span class="session-card-host" title="${escapeHtml(session.url)}">${escapeHtml(urlHost(session.url))}</span>
                <div class="badge-row">${browserBadgesHtml(session.browser)}</div>
            </header>
            <dl class="session-facts">
                <div><dt>Extracts</dt><dd>${describeExtraction(session)}</dd></div>
                <div><dt>Pagination</dt><dd>${describePagination(session.table)}</dd></div>
                <div><dt>Runs</dt><dd>${formatCount(session.run_count)}</dd></div>
                <div><dt>Last run</dt><dd title="${escapeHtml(session.last_run || '')}">${formatRelativeTime(lastRun)}</dd></div>
            </dl>
            <div class="session-card-actions">
                <button type="button" class="btn btn-primary btn-small" data-action="replay">Replay</button>
                <button type="button" class="btn btn-secondary btn-small" data-action="edit">Edit</button>
                <button type="button" class="btn btn-secondary btn-small" data-action="export">Export flow</button>
                <button type="button" class="btn btn-secondary btn-small" data-action="schedule">Schedule</button>
                <button type="button" class="btn btn-ghost-danger btn-small" data-action="delete">Delete</button>
            </div>
        </article>`;
}

// Shows only whether a proxy is set: its URL can hold a password typed literally.
function browserBadgesHtml(browserSettings) {
    if (!browserSettings) {
        return '<span class="badge">chromium</span>';
    }
    const badges = [`<span class="badge">${escapeHtml(browserSettings.backend)}</span>`];
    if (browserSettings.proxy) {
        badges.push('<span class="badge badge-accent">proxy</span>');
    }
    if (browserSettings.humanize) {
        badges.push('<span class="badge">humanize</span>');
    }
    return badges.join('');
}

function describeExtraction(session) {
    if (session.table) {
        const columnCount = session.table.columns.length;
        return `Rows, ${columnCount} ${columnCount === 1 ? 'column' : 'columns'}`;
    }
    const pickedCount = session.selectors.length;
    return `${pickedCount} picked ${pickedCount === 1 ? 'element' : 'elements'}`;
}

function describePagination(table) {
    const pagination = table && table.pagination;
    if (!pagination) {
        return 'Single page';
    }
    const paginationLimit = PAGINATION_LIMITS[pagination.mode];
    return `${paginationLimit.description}, up to ${pagination[paginationLimit.tableKey]} ${paginationLimit.unit}`;
}

function urlHost(url) {
    try {
        return new URL(url).host || url;
    } catch {
        return url;
    }
}

function runSessionCardAction(event) {
    const actionButton = event.target.closest('[data-action]');
    if (!actionButton) return;
    const sessionId = Number(actionButton.closest('[data-session-id]').dataset.sessionId);
    SESSION_CARD_ACTIONS[actionButton.dataset.action](sessionsById.get(sessionId));
}

async function deleteSession(session) {
    const confirmed = await askConfirmation(
        `Delete "${session.name}"? Its runs and schedules are deleted with it. This cannot be undone.`,
        'Delete session'
    );
    if (!confirmed) return;

    try {
        const response = await apiFetch(`/sessions/${session.id}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            showNotification('Session deleted', 'success');
            loadSessions();
        } else {
            showNotification(result.error || 'Failed to delete session', 'error');
        }
    } catch (error) {
        showNotification('Error deleting session: ' + error.message, 'error');
    }
}

async function importFlow(event) {
    const fileInput = event.target;
    const flowFile = fileInput.files[0];
    if (!flowFile) return;

    try {
        const response = await apiFetch('/flows', {
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

// ==================== REPLAY DIALOG ====================

function openReplayDialog(session) {
    replayedSession = session;
    byId('replay-dialog-title').textContent = `Replay ${session.name}`;

    const pagination = session.table && session.table.pagination;
    showReplayLimitInput('replay-max-pages', pagination && pagination.mode === 'nextButton' ? pagination.maxPages : null);
    showReplayLimitInput('replay-max-scrolls', pagination && pagination.mode === 'infiniteScroll' ? pagination.maxScrolls : null);
    byId('replay-max-rows-input').value = '';
    byId('replay-result').hidden = true;
    byId('replay-dialog').showModal();
}

// A limit the session has no pagination for is hidden and disabled, which also keeps it out of
// form validation.
function showReplayLimitInput(limitIdPrefix, sessionLimit) {
    const limitInput = byId(`${limitIdPrefix}-input`);
    const isShown = sessionLimit !== null;
    byId(`${limitIdPrefix}-field`).hidden = !isShown;
    limitInput.disabled = !isShown;
    limitInput.value = '';
    limitInput.placeholder = isShown ? `Session: ${sessionLimit}` : '';
}

function replayRequestBody() {
    const replayRequest = { headless: byId('replay-headless-checkbox').checked };
    const limitInputsByOption = {
        max_pages: byId('replay-max-pages-input'),
        max_scrolls: byId('replay-max-scrolls-input'),
        max_rows: byId('replay-max-rows-input')
    };
    for (const [optionName, limitInput] of Object.entries(limitInputsByOption)) {
        if (!limitInput.disabled && limitInput.value !== '') {
            replayRequest[optionName] = Number(limitInput.value);
        }
    }
    return replayRequest;
}

async function runReplay(event) {
    event.preventDefault();
    const runButton = byId('replay-run-btn');
    const sessionId = replayedSession.id;
    setButtonBusy(runButton, true);
    showReplayResult('running', 'Running the session. This can take a minute.');

    try {
        const response = await apiFetch(`/sessions/${sessionId}/replay`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(replayRequestBody())
        });
        const result = await response.json();

        if (result.success) {
            const itemsText = `${formatCount(result.items_count)} ${result.items_count === 1 ? 'item' : 'items'}`;
            showReplayResult('success', `Extracted ${itemsText} in ${formatDuration(result.duration_ms)}.`);
            showNotification(`Replay finished: ${itemsText}`, 'success');
        } else {
            showReplayResult('error', result.error || 'Replay failed');
            showNotification('Replay failed', 'error');
        }
    } catch (error) {
        showReplayResult('error', 'Error replaying session: ' + error.message);
    } finally {
        setButtonBusy(runButton, false);
        loadRuns();
        loadSessions();
    }
}

function showReplayResult(outcome, resultText) {
    const replayResult = byId('replay-result');
    replayResult.dataset.outcome = outcome;
    replayResult.textContent = resultText;
    replayResult.hidden = false;
}

function setButtonBusy(button, isBusy) {
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    button.querySelector('.btn-label').textContent = isBusy ? button.dataset.busyLabel : button.dataset.idleLabel;
}

// ==================== SESSION EDIT DIALOG ====================

function openSessionEditDialog(session) {
    editedSession = session;
    byId('session-edit-dialog-title').textContent = `Edit ${session.name}`;
    byId('session-edit-name-input').value = session.name;
    byId('session-edit-latest-url').value = `${location.origin}${API_BASE}/sessions/${session.id}/data/latest`;
    byId('session-edit-error').hidden = true;

    const table = session.table;
    byId('session-edit-table-section').hidden = !table;
    byId('session-edit-columns').innerHTML = table ? table.columns.map(editableColumnHtml).join('') : '';
    allowColumnRemovalWhileSeveralRemain();

    const pagination = table && table.pagination;
    const paginationInput = byId('session-edit-pagination-input');
    byId('session-edit-pagination-field').hidden = !pagination;
    paginationInput.disabled = !pagination;
    if (pagination) {
        const paginationLimit = PAGINATION_LIMITS[pagination.mode];
        byId('session-edit-pagination-label').textContent = paginationLimit.label;
        paginationInput.value = pagination[paginationLimit.tableKey];
    }

    byId('session-edit-dialog').showModal();
}

function editableColumnHtml(column, columnIndex) {
    return `
        <li class="column-row" data-column-index="${columnIndex}">
            <input type="text" class="column-name-input" value="${escapeHtml(column.name)}" aria-label="Column name" required autocomplete="off" spellcheck="false">
            <button type="button" class="btn btn-ghost-danger btn-small" data-remove-column>Remove</button>
            <code class="column-selector" title="${escapeHtml(column.selector)}">${escapeHtml(column.selector)}</code>
        </li>`;
}

function removeClickedColumn(event) {
    const removeButton = event.target.closest('[data-remove-column]');
    if (!removeButton) return;
    removeButton.closest('.column-row').remove();
    allowColumnRemovalWhileSeveralRemain();
}

// A row table needs at least one column, so the last one cannot be removed.
function allowColumnRemovalWhileSeveralRemain() {
    const removeButtons = byId('session-edit-columns').querySelectorAll('[data-remove-column]');
    for (const removeButton of removeButtons) {
        removeButton.disabled = removeButtons.length === 1;
    }
}

// The server replaces the whole table, so this sends the stored one with the kept columns renamed
// and the pagination limit changed.
function editedTable() {
    const columnRows = byId('session-edit-columns').querySelectorAll('.column-row');
    const columns = [...columnRows].map((columnRow) => ({
        ...editedSession.table.columns[Number(columnRow.dataset.columnIndex)],
        name: columnRow.querySelector('.column-name-input').value.trim()
    }));
    const table = { ...editedSession.table, columns };
    if (table.pagination) {
        const limitKey = PAGINATION_LIMITS[table.pagination.mode].tableKey;
        table.pagination = { ...table.pagination, [limitKey]: Number(byId('session-edit-pagination-input').value) };
    }
    return table;
}

async function saveSessionEdit(event) {
    event.preventDefault();
    const sessionChanges = { name: byId('session-edit-name-input').value.trim() };
    if (editedSession.table) {
        sessionChanges.table = editedTable();
    }
    const editError = byId('session-edit-error');
    editError.hidden = true;

    try {
        const response = await apiFetch(`/sessions/${editedSession.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sessionChanges)
        });
        const result = await response.json();

        if (response.ok) {
            byId('session-edit-dialog').close();
            showNotification('Session saved', 'success');
            loadSessions();
        } else {
            editError.textContent = result.error || 'Failed to save session';
            editError.hidden = false;
        }
    } catch (error) {
        editError.textContent = 'Error saving session: ' + error.message;
        editError.hidden = false;
    }
}

// ==================== SCHEDULES ====================

function openScheduleDialog(session) {
    scheduledSession = session;
    byId('schedule-dialog-title').textContent = `Schedule ${session.name}`;
    byId('schedule-frequency-input').value = DEFAULT_SCHEDULE_MINUTES;
    byId('schedule-dialog').showModal();
}

async function createSchedule(event) {
    event.preventDefault();
    const frequencyMinutes = Number(byId('schedule-frequency-input').value);

    try {
        const response = await apiFetch('/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: scheduledSession.id, frequency_minutes: frequencyMinutes })
        });

        const result = await response.json();

        if (result.success) {
            byId('schedule-dialog').close();
            showNotification(`Scheduled ${scheduledSession.name} ${formatFrequency(frequencyMinutes).toLowerCase()}`, 'success');
            loadSchedules();
        } else {
            showNotification(result.error || 'Failed to create schedule', 'error');
        }
    } catch (error) {
        showNotification('Error creating schedule: ' + error.message, 'error');
    }
}

async function loadSchedules() {
    try {
        const response = await apiFetch('/schedules');
        if (!response.ok) return;
        renderSchedules(await response.json());
    } catch (error) {
        console.error('Error loading schedules:', error);
    }
}

function renderSchedules(schedules) {
    const schedulesList = byId('schedules-list');

    if (schedules.length === 0) {
        schedulesList.innerHTML = `
            <div class="empty-state">
                <strong>No schedules yet</strong>
                Use a session's Schedule action on the <a href="#sessions">Sessions</a> page.
            </div>`;
        return;
    }

    schedulesList.innerHTML = `
        <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Session</th>
                        <th>Frequency</th>
                        <th>Next run</th>
                        <th>Enabled</th>
                        <th class="actions-col"><span class="visually-hidden">Actions</span></th>
                    </tr>
                </thead>
                <tbody>${schedules.map(scheduleRowHtml).join('')}</tbody>
            </table>
        </div>`;
}

function scheduleRowHtml(schedule) {
    const nextRunText = schedule.enabled
        ? formatRelativeTime(parseServerLocalTimestamp(schedule.next_run))
        : 'Paused';
    return `
        <tr>
            <td>
                <span class="cell-title">${escapeHtml(schedule.session_name)}</span>
                <span class="cell-subtitle" title="${escapeHtml(schedule.session_url)}">${escapeHtml(urlHost(schedule.session_url))}</span>
            </td>
            <td>${formatFrequency(schedule.frequency_minutes)}</td>
            <td title="${escapeHtml(schedule.next_run || '')}">${nextRunText}</td>
            <td>
                <label class="switch">
                    <input type="checkbox" role="switch" data-schedule-id="${schedule.id}" aria-label="Enabled" ${schedule.enabled ? 'checked' : ''}>
                    <span class="switch-track"></span>
                </label>
            </td>
            <td class="actions-col">
                <button type="button" class="btn btn-ghost-danger btn-small" data-delete-schedule-id="${schedule.id}">Delete</button>
            </td>
        </tr>`;
}

function toggleSwitchedSchedule(event) {
    const scheduleSwitch = event.target.closest('[data-schedule-id]');
    if (scheduleSwitch) {
        toggleSchedule(Number(scheduleSwitch.dataset.scheduleId), scheduleSwitch.checked);
    }
}

function deleteClickedSchedule(event) {
    const deleteButton = event.target.closest('[data-delete-schedule-id]');
    if (deleteButton) {
        deleteSchedule(Number(deleteButton.dataset.deleteScheduleId));
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
    if (!await askConfirmation('Delete this schedule? The session stays.', 'Delete schedule')) return;

    try {
        await apiFetch(`/schedules/${scheduleId}`, { method: 'DELETE' });
        showNotification('Schedule deleted', 'success');
        loadSchedules();
    } catch (error) {
        showNotification('Error deleting schedule: ' + error.message, 'error');
    }
}

// ==================== RUNS ====================

async function loadRuns() {
    try {
        const response = await apiFetch(`/runs?limit=${RUNS_LIST_LIMIT}`);
        if (!response.ok) return;
        latestRuns = await response.json();
        renderRunRows(byId('runs-table-body'), latestRuns);
        renderRunRows(byId('overview-runs-body'), latestRuns.slice(0, OVERVIEW_RUNS_COUNT));
    } catch (error) {
        console.error('Error loading runs:', error);
    }
}

function renderRunRows(runsTableBody, runs) {
    if (runs.length === 0) {
        runsTableBody.innerHTML = '<tr><td colspan="6" class="table-note">No runs yet. Replay a session to extract data.</td></tr>';
        return;
    }
    runsTableBody.innerHTML = runs.map(runRowHtml).join('');
}

function runRowHtml(run) {
    const failedWithError = run.status === 'failed' && run.error;
    return `
        <tr class="run-row" data-run-id="${run.id}" tabindex="0"${failedWithError ? ` title="${escapeHtml(run.error)}"` : ''}>
            <td>${statusPillHtml(run.status)}</td>
            <td class="run-session-cell">
                <span class="run-session-name">${escapeHtml(run.session_name)}</span>
                ${failedWithError ? `<span class="run-error-line">${escapeHtml(run.error)}</span>` : ''}
            </td>
            <td class="col-trigger">${escapeHtml(run.triggered_by || MISSING_VALUE)}</td>
            <td class="num">${formatCount(run.items_count)}</td>
            <td class="num col-duration">${formatDuration(run.duration_ms)}</td>
            <td title="${escapeHtml(run.extracted_at)}">${formatRelativeTime(parseUtcTimestamp(run.extracted_at))}</td>
        </tr>`;
}

function statusPillHtml(runStatus) {
    return runStatus === 'failed'
        ? '<span class="pill pill-failed">Failed</span>'
        : '<span class="pill pill-success">Success</span>';
}

function openClickedRun(event) {
    const runRow = event.target.closest('.run-row');
    if (runRow) {
        openRunViewer(Number(runRow.dataset.runId));
    }
}

function openRunOnEnter(event) {
    if (event.key === 'Enter') {
        openClickedRun(event);
    }
}

// ==================== RUN VIEWER ====================

// The run summaries carry no records, so the viewer reads them through the JSON export, which
// returns any one run's records by its id.
async function openRunViewer(runId) {
    const runSummary = latestRuns.find((run) => run.id === runId);
    viewedRunId = runId;
    viewedRunRecords = [];
    renderRunViewerHeader(runSummary);
    byId('run-viewer-records').innerHTML = '<p class="table-note">Loading records...</p>';
    byId('run-viewer-json').textContent = '';
    renderExportFields([]);
    showJsonExportOptions();
    selectRunViewerTab('table');
    byId('run-viewer').showModal();

    try {
        const response = await apiFetch(`/data/${runId}/export?format=json`);
        const responseBody = await response.json();
        if (viewedRunId !== runId) return;
        if (!response.ok) {
            byId('run-viewer-records').innerHTML = `<p class="table-note">${escapeHtml(responseBody.error)}</p>`;
            return;
        }
        viewedRunRecords = responseBody;
        const columnNames = recordColumnNames(viewedRunRecords);
        byId('run-viewer-records').innerHTML = recordsTableHtml(viewedRunRecords, columnNames);
        byId('run-viewer-json').textContent = JSON.stringify(viewedRunRecords, null, 2);
        renderExportFields(columnNames);
    } catch (error) {
        showNotification('Error loading run: ' + error.message, 'error');
    }
}

function renderRunViewerHeader(runSummary) {
    byId('run-viewer-title').textContent = runSummary.session_name;
    const itemsCount = runSummary.items_count;
    byId('run-viewer-meta').innerHTML = `
        ${statusPillHtml(runSummary.status)}
        <span>Run #${runSummary.id}</span>
        <span>${formatCount(itemsCount)} ${itemsCount === 1 ? 'item' : 'items'}</span>
        <span>${formatDuration(runSummary.duration_ms)}</span>
        <span>${escapeHtml(runSummary.triggered_by || 'unknown trigger')}</span>
        <span title="${escapeHtml(runSummary.extracted_at)}">${formatRelativeTime(parseUtcTimestamp(runSummary.extracted_at))}</span>`;
    const runError = byId('run-viewer-error');
    runError.textContent = runSummary.error || '';
    runError.hidden = !runSummary.error;
}

// Table records and picked-element rows are both flat objects; a Set keeps first-seen key order.
function recordColumnNames(records) {
    return [...new Set(records.flatMap((record) => Object.keys(record)))];
}

function recordsTableHtml(records, columnNames) {
    if (records.length === 0) {
        return '<p class="table-note">This run extracted no records.</p>';
    }
    const headerCells = columnNames.map((columnName) => `<th>${escapeHtml(columnName)}</th>`).join('');
    const bodyRows = records.map((record, recordIndex) => {
        const cells = columnNames.map((columnName) => {
            const cellText = escapeHtml(recordCellText(record[columnName]));
            return `<td title="${cellText}">${cellText}</td>`;
        }).join('');
        return `<tr><td class="num row-number">${recordIndex + 1}</td>${cells}</tr>`;
    }).join('');
    return `
        <table class="data-table records-table">
            <thead><tr><th class="num">#</th>${headerCells}</tr></thead>
            <tbody>${bodyRows}</tbody>
        </table>`;
}

function recordCellText(cellValue) {
    if (cellValue === undefined || cellValue === null) {
        return '';
    }
    return typeof cellValue === 'object' ? JSON.stringify(cellValue) : String(cellValue);
}

function selectRunViewerTab(tabName) {
    for (const shownTabName of ['table', 'json']) {
        const isSelected = shownTabName === tabName;
        byId(`run-viewer-${shownTabName}-tab`).setAttribute('aria-selected', String(isSelected));
        byId(`run-viewer-${shownTabName}-panel`).hidden = !isSelected;
    }
}

function renderExportFields(columnNames) {
    byId('export-fields-list').innerHTML = columnNames.length === 0
        ? '<span class="muted">No fields to pick.</span>'
        : columnNames.map((columnName) => `
            <label class="field-chip">
                <input type="checkbox" value="${escapeHtml(columnName)}" checked>
                <span>${escapeHtml(columnName)}</span>
            </label>`).join('');
}

// envelope and pretty are refused by the server for any format but JSON.
function showJsonExportOptions() {
    byId('export-json-options').hidden = byId('export-format-select').value !== 'json';
}

function downloadViewedRun() {
    const exportFormat = byId('export-format-select').value;
    const fieldCheckboxes = [...byId('export-fields-list').querySelectorAll('input[type="checkbox"]')];
    const checkedFieldNames = fieldCheckboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
    if (fieldCheckboxes.length > 0 && checkedFieldNames.length === 0) {
        showNotification('Pick at least one field to export', 'error');
        return;
    }

    const exportParameters = new URLSearchParams({ format: exportFormat });
    if (checkedFieldNames.length < fieldCheckboxes.length) {
        exportParameters.set('fields', checkedFieldNames.join(','));
    }
    if (exportFormat === 'json') {
        if (byId('export-envelope-checkbox').checked) {
            exportParameters.set('envelope', '1');
        }
        if (!byId('export-pretty-checkbox').checked) {
            exportParameters.set('pretty', '0');
        }
    }
    downloadFromApi(`/data/${viewedRunId}/export?${exportParameters}`);
}

// ==================== CONFIRMATION AND CLIPBOARD ====================

function askConfirmation(question, acceptLabel) {
    const confirmDialog = byId('confirm-dialog');
    byId('confirm-message').textContent = question;
    byId('confirm-accept-btn').textContent = acceptLabel;
    confirmDialog.returnValue = '';
    confirmDialog.showModal();
    return new Promise((resolve) => {
        confirmDialog.addEventListener('close', () => resolve(confirmDialog.returnValue === 'accept'), { once: true });
    });
}

async function copyText(copiedText, successMessage) {
    try {
        await navigator.clipboard.writeText(copiedText);
        showNotification(successMessage, 'success');
    } catch (error) {
        showNotification('Could not copy: ' + error.message, 'error');
    }
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

// ==================== FORMATTING ====================

// SQLite's CURRENT_TIMESTAMP, which fills created_at, last_run and extracted_at, is UTC text
// with no zone mark.
function parseUtcTimestamp(timestampText) {
    return timestampText ? new Date(timestampText.replace(' ', 'T') + 'Z') : null;
}

// A schedule's next_run is written by Python's datetime.now(), the server's local time, also with
// no zone mark. Read as the browser's local time, it is right when both share a time zone.
function parseServerLocalTimestamp(timestampText) {
    return timestampText ? new Date(timestampText.replace(' ', 'T')) : null;
}

const relativeTimeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
const RELATIVE_TIME_UNITS = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
    ['second', 1]
];

function formatRelativeTime(moment) {
    if (!moment || Number.isNaN(moment.getTime())) {
        return MISSING_VALUE;
    }
    const secondsFromNow = (moment.getTime() - Date.now()) / 1000;
    const [unitName, unitSeconds] = RELATIVE_TIME_UNITS.find(
        ([, unitLengthSeconds]) => Math.abs(secondsFromNow) >= unitLengthSeconds
    ) || ['second', 1];
    return relativeTimeFormat.format(Math.round(secondsFromNow / unitSeconds), unitName);
}

function formatDuration(durationMs) {
    if (durationMs === null || durationMs === undefined) {
        return MISSING_VALUE;
    }
    if (durationMs < 1000) {
        return `${durationMs} ms`;
    }
    if (durationMs < 60000) {
        return `${(durationMs / 1000).toFixed(1)} s`;
    }
    const totalSeconds = Math.round(durationMs / 1000);
    return `${Math.floor(totalSeconds / 60)} min ${totalSeconds % 60} s`;
}

function formatFrequency(frequencyMinutes) {
    if (frequencyMinutes % 1440 === 0) {
        return `Every ${frequencyMinutes / 1440} d`;
    }
    if (frequencyMinutes % 60 === 0) {
        return `Every ${frequencyMinutes / 60} h`;
    }
    return `Every ${frequencyMinutes} min`;
}

function formatCount(count) {
    return Number(count || 0).toLocaleString();
}

// innerHTML escapes <, > and & but leaves quotes, and these strings also go into attribute values.
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

// ==================== TOASTS ====================

function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.textContent = message;
    byId('toast-region').append(toast);

    setTimeout(() => {
        toast.classList.add('toast-leaving');
        setTimeout(() => toast.remove(), 200);
    }, TOAST_DURATION_MS[type]);
}
