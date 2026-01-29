import json
import os
import time
from patchright.sync_api import sync_playwright

# Configuration
KEYGEN_URL = "https://manifesthub1.filegear-sg.me/"

def get_apikey_auto():
    """
    Uses Playwright to automatically retrieve a new API Key.
    """
    print("Launching browser to fetch new API Key...")
    # Use headless mode from environment variable, default to False for local use
    headless = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    '--window-position=0,0',
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )
            
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            page = context.new_page()
            
            print(f"Navigating to {KEYGEN_URL}...")
            page.goto(KEYGEN_URL)
            
            # Wait for Turnstile verification
            print("Waiting for Turnstile verification...")
            
            try:
                page.wait_for_selector("iframe", timeout=5000)
                frames = page.frames
                for frame in frames:
                    if "cloudflare" in frame.url or "turnstile" in frame.url:
                        print("Found Turnstile frame. Attempting to click...")
                        try:
                            frame.click("body", timeout=2000)
                            print("Clicked Turnstile frame.")
                        except:
                            pass
            except:
                print("Could not find/click Turnstile iframe automatically. Please click it manually.")

            page.wait_for_function("document.getElementById('generateBtn').disabled === false", timeout=120000)
            
            print("Verification complete. Generating key...")
            page.click("#generateBtn")
            
            print("Waiting for key generation...")
            page.wait_for_selector(".api-key", timeout=10000)
            
            key_element = page.query_selector(".api-key div")
            if key_element:
                api_key = key_element.inner_text().strip()
                print(f"Successfully retrieved new API Key: {api_key}")
                return api_key
            else:
                print("Error: Could not find API key element on page.")
                return None
                
    except Exception as e:
        print(f"Error fetching API Key: {e}")
        return None

def save_token(api_key):
    """Saves the API key to tokens.json."""
    tokens_file = "tokens.json"
    data = {"api_key": api_key, "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")}
    
    try:
        with open(tokens_file, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Successfully saved token to {tokens_file}")
    except Exception as e:
        print(f"Error saving token: {e}")

if __name__ == "__main__":
    api_key = get_apikey_auto()
    if api_key:
        save_token(api_key)
    else:
        print("Failed to retrieve API key.")
