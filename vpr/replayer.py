"""
Session Replayer for Visual Data Scraper
Replays recorded sessions in headless mode and extracts data.
"""

import time
from typing import List, Dict, Optional, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class SessionReplayer:
    """Replays recorded sessions and extracts data."""
    
    def __init__(self, headless: bool = True):
        """Initialize the session replayer."""
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
    
    def replay_session(self, session_data: Dict) -> Dict[str, Any]:
        """
        Replay a recorded session and extract data.
        
        Args:
            session_data: Dictionary containing url, actions, and selectors
            
        Returns:
            Dictionary with extracted data and metadata
        """
        try:
            # Setup Chrome driver
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument('--headless=new')
                options.add_argument('--disable-gpu')
            else:
                # Visible mode - maximize window
                options.add_argument('--start-maximized')
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            # Navigate to start URL
            url = session_data.get("url", "")
            if not url:
                return {"error": "No URL provided"}
            
            print(f"Navigating to: {url}")
            self.driver.get(url)
            time.sleep(2)  # Wait for initial page load
            
            # Skip replaying actions - only extract data from selectors
            # actions = session_data.get("actions", [])
            # self._replay_actions(actions)
            
            # Extract data from selected elements
            selectors = session_data.get("selectors", [])
            extracted_data = self._extract_data(selectors)
            
            return {
                "success": True,
                "url": url,
                "data": extracted_data,
                "timestamp": time.time(),
                "items_count": len(extracted_data)
            }
            
        except Exception as e:
            print(f"Error replaying session: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def _replay_actions(self, actions: List[Dict]):
        """Replay recorded actions."""
        for action in actions:
            try:
                action_type = action.get("type")
                
                if action_type == "navigate":
                    # Already handled in main replay
                    continue
                
                elif action_type == "click":
                    selector = action.get("selector")
                    if selector:
                        # Skip VPR UI elements
                        if selector.startswith('#vpr-') or 'vpr-' in selector:
                            continue
                        
                        element = self._find_element(selector)
                        if element:
                            # Scroll into view
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                                element
                            )
                            time.sleep(0.5)
                            element.click()
                            time.sleep(1)  # Wait after click
                
                elif action_type == "input":
                    selector = action.get("selector")
                    value = action.get("value", "")
                    if selector:
                        # Skip VPR UI elements
                        if selector.startswith('#vpr-') or 'vpr-' in selector:
                            continue
                        
                        element = self._find_element(selector)
                        if element:
                            element.clear()
                            element.send_keys(value)
                            time.sleep(0.5)
                
                elif action_type == "scroll":
                    x = action.get("x", 0)
                    y = action.get("y", 0)
                    self.driver.execute_script(f"window.scrollTo({x}, {y});")
                    time.sleep(0.5)
                
            except Exception as e:
                print(f"Error replaying action {action_type}: {e}")
                # Continue with next action
                continue
    
    def _find_element(self, selector: str, timeout: int = 5):
        """Find element by CSS selector with wait."""
        try:
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except TimeoutException:
            # Don't print timeout errors - element might not exist
            return None
        except Exception as e:
            print(f"Error finding element {selector}: {e}")
            return None
    
    def _extract_data(self, selectors: List[Dict]) -> List[Dict]:
        """Extract data from selected elements by retrieving current content."""
        extracted = []
        
        for selector_info in selectors:
            try:
                selector = selector_info.get("selector")
                tag_name = selector_info.get("tagName", "")
                attribute = selector_info.get("attribute", "textContent")
                
                # Find all matching elements
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for idx, element in enumerate(elements):
                    try:
                        # Extract current data from element based on attribute
                        if attribute == "textContent":
                            value = element.text
                        elif attribute == "innerHTML":
                            value = element.get_attribute("innerHTML")
                        elif attribute == "href":
                            value = element.get_attribute("href")
                        elif attribute == "src":
                            value = element.get_attribute("src")
                        elif attribute == "value":
                            value = element.get_attribute("value")
                        else:
                            value = element.get_attribute(attribute)
                        
                        if value and value.strip():
                            extracted.append({
                                "selector": selector,
                                "value": value.strip(),
                                "attribute": attribute,
                                "index": idx,
                                "tag": element.tag_name
                            })
                    
                    except Exception as e:
                        print(f"Error extracting from element {idx}: {e}")
                        continue
            
            except Exception as e:
                print(f"Error processing selector {selector}: {e}")
                continue
        
        return extracted
    
    def take_screenshot(self, filepath: str) -> bool:
        """Take a screenshot of current page."""
        try:
            if self.driver:
                self.driver.save_screenshot(filepath)
                return True
        except Exception as e:
            print(f"Error taking screenshot: {e}")
        return False
