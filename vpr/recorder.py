"""
Session Recorder for Visual Data Scraper
Records user browser interactions using Selenium WebDriver.
"""

import time
import json
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class SessionRecorder:
    """Records browser sessions for later replay."""
    
    def __init__(self):
        """Initialize the session recorder."""
        self.driver: Optional[webdriver.Chrome] = None
        self.actions: List[Dict] = []
        self.selectors: List[Dict] = []
        self.recording = False
        self.start_url = ""
        self._inject_selector_script()
    
    def _inject_selector_script(self):
        """Prepare JavaScript for visual element selection overlay."""
        self.selector_js = """
        (function() {
            if (window.vprSelectorActive) return;
            window.vprSelectorActive = true;
            window.vprSelectedElements = [];
            
            // Create overlay
            const overlay = document.createElement('div');
            overlay.id = 'vpr-selector-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.3);
                z-index: 999999;
                pointer-events: none;
            `;
            
            // Create info panel
            const panel = document.createElement('div');
            panel.id = 'vpr-info-panel';
            panel.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 12px;
                z-index: 1000000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                pointer-events: auto;
            `;
            panel.innerHTML = `
                <h3 style="margin: 0 0 10px 0; font-size: 16px;">🎯 Element Selector</h3>
                <p style="margin: 0 0 10px 0; font-size: 13px;">Click elements to select for data extraction</p>
                <div id="vpr-selected-count" style="font-size: 14px; margin-bottom: 10px;">Selected: 0</div>
                <button id="vpr-done-btn" style="
                    background: white;
                    color: #667eea;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    width: 100%;
                ">Done Selecting</button>
            `;
            
            document.body.appendChild(overlay);
            document.body.appendChild(panel);
            
            let highlightedElement = null;
            
            // Highlight on hover
            const handleMouseMove = (e) => {
                if (e.target.closest('#vpr-info-panel')) return;
                
                const target = e.target;
                if (target && target !== overlay) {
                    if (highlightedElement && highlightedElement !== target) {
                        highlightedElement.style.outline = '';
                    }
                    target.style.outline = '3px solid #667eea';
                    target.style.cursor = 'crosshair';
                    highlightedElement = target;
                }
            };
            document.addEventListener('mousemove', handleMouseMove);
            
            // FIRST: Add selection handler that runs early
            const handleSelection = (e) => {
                if (e.target.closest('#vpr-info-panel')) return;
                if (!window.vprSelectorActive) return;
                
                const target = e.target;
                if (target && target !== overlay) {
                    // Generate selector - store only selector, not content
                    const selector = getUniqueSelector(target);
                    
                    // Determine best attribute to extract
                    let attribute = 'textContent';
                    if (target.tagName === 'IMG') attribute = 'src';
                    else if (target.tagName === 'A') attribute = 'href';
                    else if (target.hasAttribute('value')) attribute = 'value';
                    
                    // Preview text for visual feedback only (not stored for extraction)
                    const previewText = target.textContent.trim().substring(0, 30) || target.tagName;
                    
                    window.vprSelectedElements.push({
                        selector: selector,
                        tagName: target.tagName,
                        attribute: attribute,
                        preview: previewText + '...'  // Just for display during recording
                    });
                    
                    // Visual feedback
                    target.style.background = 'rgba(102, 126, 234, 0.2)';
                    target.style.outline = '3px solid #667eea';
                    
                    // Update count with preview
                    const countEl = document.getElementById('vpr-selected-count');
                    countEl.textContent = `Selected: ${window.vprSelectedElements.length}`;
                    countEl.title = window.vprSelectedElements.map(s => s.preview).join('\\n');
                }
            };
            
            // SECOND: Add blocking handler that runs later and blocks everything
            const blockEvent = (e) => {
                if (e.target.closest('#vpr-info-panel')) return;
                if (!window.vprSelectorActive) return;
                // Always block the event from propagating to the page
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            };
            
            // Add selection handler FIRST (runs first in capture phase)
            document.addEventListener('click', handleSelection, true);
            
            // Block various events AFTER selection handler
            const eventsToBlock = ['click', 'mousedown', 'mouseup', 'dblclick', 'contextmenu', 
                                   'submit', 'keydown', 'keypress', 'touchstart', 'touchend'];
            
            // Add blockers after a tiny delay to ensure selection handler is added first
            setTimeout(() => {
                eventsToBlock.forEach(eventType => {
                    document.addEventListener(eventType, blockEvent, true);
                });
            }, 0);
            
            // Store handlers for cleanup
            window.vprSelectionHandler = handleSelection;
            window.vprBlockHandler = blockEvent;
            window.vprEventsToBlock = eventsToBlock;
            window.vprMouseMoveHandler = handleMouseMove;
            
            // Done button - cleanup all event listeners
            document.getElementById('vpr-done-btn').addEventListener('click', () => {
                // Remove event blockers
                if (window.vprBlockHandler && window.vprEventsToBlock) {
                    window.vprEventsToBlock.forEach(eventType => {
                        document.removeEventListener(eventType, window.vprBlockHandler, true);
                    });
                }
                
                // Remove selection handler
                if (window.vprSelectionHandler) {
                    document.removeEventListener('click', window.vprSelectionHandler, true);
                }
                
                // Remove mousemove handler
                if (window.vprMouseMoveHandler) {
                    document.removeEventListener('mousemove', window.vprMouseMoveHandler);
                }
                
                // Remove UI
                overlay.remove();
                panel.remove();
                
                // Clear outline from last highlighted element
                if (highlightedElement) {
                    highlightedElement.style.outline = '';
                    highlightedElement.style.cursor = '';
                }
                
                window.vprSelectorActive = false;
            });
            
            // Generate unique CSS selector for element
            function getUniqueSelector(element) {
                if (element.id) {
                    return '#' + element.id;
                }
                
                if (element.className) {
                    const classes = element.className.split(' ').filter(c => c).join('.');
                    if (classes) {
                        const selector = element.tagName.toLowerCase() + '.' + classes;
                        if (document.querySelectorAll(selector).length === 1) {
                            return selector;
                        }
                    }
                }
                
                // Fallback to nth-child
                let path = [];
                let current = element;
                while (current.parentElement) {
                    let index = Array.from(current.parentElement.children).indexOf(current) + 1;
                    path.unshift(`${current.tagName.toLowerCase()}:nth-child(${index})`);
                    current = current.parentElement;
                    if (current.id) {
                        path.unshift('#' + current.id);
                        break;
                    }
                }
                return path.join(' > ');
            }
        })();
        """
    
    def start_recording(self, url: str) -> bool:
        """Start recording a new session."""
        try:
            # Setup Chrome driver
            options = webdriver.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Navigate to URL
            self.driver.get(url)
            self.start_url = url
            self.recording = True
            self.actions = []
            self.selectors = []
            
            # Record initial navigation
            self.actions.append({
                "type": "navigate",
                "url": url,
                "timestamp": time.time()
            })
            
            # Inject event listeners for tracking
            self._inject_tracking()
            
            return True
            
        except Exception as e:
            print(f"Error starting recording: {e}")
            return False
    
    def _inject_tracking(self):
        """Inject JavaScript to track user interactions."""
        tracking_js = """
        window.vprActions = [];
        
        // Track clicks
        document.addEventListener('click', (e) => {
            // Ignore clicks on VPR UI elements
            if (e.target.id === 'vpr-done-btn' || 
                e.target.id === 'vpr-selector-overlay' ||
                e.target.closest('#vpr-info-panel') ||
                e.target.closest('#vpr-selector-overlay')) return;
            
            window.vprActions.push({
                type: 'click',
                selector: getElementSelector(e.target),
                timestamp: Date.now()
            });
        }, true);
        
        // Track input
        document.addEventListener('input', (e) => {
            window.vprActions.push({
                type: 'input',
                selector: getElementSelector(e.target),
                value: e.target.value,
                timestamp: Date.now()
            });
        }, true);
        
        // Track scrolling
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                window.vprActions.push({
                    type: 'scroll',
                    x: window.scrollX,
                    y: window.scrollY,
                    timestamp: Date.now()
                });
            }, 200);
        });
        
        function getElementSelector(element) {
            if (element.id) return '#' + element.id;
            if (element.name) return `[name="${element.name}"]`;
            
            let path = [];
            let current = element;
            while (current.parentElement) {
                let index = Array.from(current.parentElement.children).indexOf(current) + 1;
                path.unshift(`${current.tagName.toLowerCase()}:nth-child(${index})`);
                current = current.parentElement;
                if (current.id) {
                    path.unshift('#' + current.id);
                    break;
                }
                if (path.length > 5) break;
            }
            return path.join(' > ');
        }
        """
        
        try:
            self.driver.execute_script(tracking_js)
        except Exception as e:
            print(f"Error injecting tracking: {e}")
    
    def activate_selector_mode(self):
        """Activate visual element selector overlay."""
        if self.driver and self.recording:
            try:
                # Make sure we're on the page
                self.driver.switch_to.default_content()
                
                # Inject the selector script
                print("Injecting selector overlay...")
                self.driver.execute_script(self.selector_js)
                
                # Verify injection succeeded
                is_active = self.driver.execute_script("return window.vprSelectorActive || false;")
                print(f"Selector overlay active: {is_active}")
                
                if not is_active:
                    print("Failed to activate selector overlay")
                    return False
                
                # Wait for user to finish selecting (5 minutes max)
                print("Selector mode activated! Click elements in browser, then click 'Done Selecting' button.")
                WebDriverWait(self.driver, 300).until(
                    lambda d: not d.execute_script("return window.vprSelectorActive;")
                )
                
                # Get selected elements
                selected = self.driver.execute_script("return window.vprSelectedElements || [];")
                print(f"Selected {len(selected)} elements")
                self.selectors.extend(selected)
                
                return True
            except TimeoutException:
                print("Selector timeout - user did not click 'Done Selecting'")
                return False
            except Exception as e:
                print(f"Error in selector mode: {e}")
                return False
        return False
    
    def stop_recording(self) -> Dict:
        """Stop recording and return session data."""
        if not self.driver or not self.recording:
            return {}
        
        try:
            # Get all tracked actions
            tracked_actions = self.driver.execute_script("return window.vprActions || [];")
            self.actions.extend(tracked_actions)
            
            # Create session data
            session_data = {
                "url": self.start_url,
                "actions": self.actions,
                "selectors": self.selectors,
                "duration": time.time() - self.actions[0]["timestamp"] if self.actions else 0
            }
            
            self.recording = False
            return session_data
            
        except Exception as e:
            print(f"Error stopping recording: {e}")
            return {}
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording and self.driver is not None
