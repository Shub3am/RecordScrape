// API Base URL
const API_BASE = '';

// DOM Elements
const launchBtn = document.getElementById('launchBtn');
const closeBtn = document.getElementById('closeBtn');
const navigateBtn = document.getElementById('navigateBtn');
const clickBtn = document.getElementById('clickBtn');
const fillBtn = document.getElementById('fillBtn');
const screenshotBtn = document.getElementById('screenshotBtn');
const clearLogBtn = document.getElementById('clearLogBtn');

const browserType = document.getElementById('browserType');
const headless = document.getElementById('headless');
const viewportWidth = document.getElementById('viewportWidth');
const viewportHeight = document.getElementById('viewportHeight');
const urlInput = document.getElementById('urlInput');
const waitUntil = document.getElementById('waitUntil');
const selectorInput = document.getElementById('selectorInput');
const textInput = document.getElementById('textInput');
const activityLog = document.getElementById('activityLog');
const statusIndicator = document.getElementById('statusIndicator');

// State
let browserRunning = false;

// Utility Functions
function logMessage(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span class="log-message">${message}</span>
    `;
    activityLog.appendChild(entry);
    activityLog.scrollTop = activityLog.scrollHeight;
}

function updateStatus(running) {
    browserRunning = running;
    
    if (running) {
        statusIndicator.classList.add('online');
        statusIndicator.querySelector('.status-text').textContent = 'Browser Online';
        launchBtn.disabled = true;
        closeBtn.disabled = false;
        navigateBtn.disabled = false;
        clickBtn.disabled = false;
        fillBtn.disabled = false;
        screenshotBtn.disabled = false;
    } else {
        statusIndicator.classList.remove('online');
        statusIndicator.querySelector('.status-text').textContent = 'Browser Offline';
        launchBtn.disabled = false;
        closeBtn.disabled = true;
        navigateBtn.disabled = true;
        clickBtn.disabled = true;
        fillBtn.disabled = true;
        screenshotBtn.disabled = true;
    }
}

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Request failed');
        }
        
        return result;
    } catch (error) {
        throw error;
    }
}

// Event Handlers
launchBtn.addEventListener('click', async () => {
    try {
        logMessage('Launching browser...', 'info');
        const result = await apiCall('/api/browser/launch', 'POST', {
            headless: headless.checked,
            viewport_width: parseInt(viewportWidth.value),
            viewport_height: parseInt(viewportHeight.value),
            browser_type: browserType.value,
        });
        logMessage(result.message, 'success');
        updateStatus(true);
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
});

closeBtn.addEventListener('click', async () => {
    try {
        logMessage('Closing browser...', 'info');
        const result = await apiCall('/api/browser/close', 'POST');
        logMessage(result.message, 'success');
        updateStatus(false);
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
});

navigateBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) {
        logMessage('Please enter a URL', 'error');
        return;
    }
    
    try {
        logMessage(`Navigating to ${url}...`, 'info');
        const result = await apiCall('/api/browser/navigate', 'POST', {
            url,
            wait_until: waitUntil.value,
        });
        logMessage(result.message, 'success');
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
});

clickBtn.addEventListener('click', async () => {
    const selector = selectorInput.value.trim();
    if (!selector) {
        logMessage('Please enter a CSS selector', 'error');
        return;
    }
    
    try {
        logMessage(`Clicking ${selector}...`, 'info');
        const result = await apiCall('/api/browser/click', 'POST', {
            selector,
        });
        logMessage(result.message, 'success');
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
});

fillBtn.addEventListener('click', async () => {
    const selector = selectorInput.value.trim();
    const text = textInput.value;
    
    if (!selector) {
        logMessage('Please enter a CSS selector', 'error');
        return;
    }
    
    try {
        logMessage(`Filling ${selector} with text...`, 'info');
        const result = await apiCall('/api/browser/fill', 'POST', {
            selector,
            text,
        });
        logMessage(result.message, 'success');
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
});

screenshotBtn.addEventListener('click', async () => {
    try {
        const timestamp = new Date().getTime();
        const path = `screenshot_${timestamp}.png`;
        logMessage('Taking screenshot...', 'info');
        const result = await apiCall('/api/browser/screenshot', 'POST', {
            path,
        });
        logMessage(result.message, 'success');
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
});

clearLogBtn.addEventListener('click', () => {
    activityLog.innerHTML = '';
    logMessage('Log cleared', 'info');
});

// Keyboard shortcuts
urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !navigateBtn.disabled) {
        navigateBtn.click();
    }
});

selectorInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !clickBtn.disabled) {
        clickBtn.click();
    }
});

// Check browser status on load
async function checkStatus() {
    try {
        const result = await apiCall('/api/browser/status');
        updateStatus(result.running);
    } catch (error) {
        console.error('Failed to check status:', error);
    }
}

// Initialize
checkStatus();
logMessage('Welcome to Video Product Recorder! 🎬', 'success');
logMessage('Launch a browser to get started.', 'info');
