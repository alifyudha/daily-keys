import json
import os
import time
import asyncio
import nodriver as uc
from cloudflare_bypass import bypass

KEYGEN_URL = "https://manifesthub1.filegear-sg.me/"

async def take_screenshot(tab, name):
    """Captures a screenshot for debugging."""
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filepath = f"screenshots/{name}_{timestamp}.png"
    await tab.save_screenshot(filepath)
    print(f"Screenshot saved: {filepath}")

def parse_eval_result(result):
    """
    Parses nodriver's complex evaluate result format into a standard Python object.
    Handles formats like: [['key', {'value': val}], ...] or [{'value': val}] or raw values.
    """
    if result is None:
        return None
    
    if isinstance(result, list):
        if len(result) > 0 and isinstance(result[0], list) and len(result[0]) == 2:
            parsed_dict = {}
            for item in result:
                if isinstance(item, list) and len(item) == 2:
                    key = item[0]
                    val_obj = item[1]
                    if isinstance(val_obj, dict) and 'value' in val_obj:
                        parsed_dict[key] = val_obj['value']
            return parsed_dict
        
        processed_list = []
        for item in result:
            if isinstance(item, dict) and 'value' in item:
                processed_list.append(item['value'])
            else:
                processed_list.append(item)
        return processed_list[0] if len(processed_list) == 1 else processed_list

    if isinstance(result, dict) and 'value' in result:
        return result['value']
    
    return result

async def solve_cloudflare_challenge(tab):
    """
    Dedicated helper to detect and solve Cloudflare Turnstile/Challenge using external lib.
    """
    try:
        result = await tab.evaluate("""
            (function() {
                const title = document.title.toLowerCase();
                const isChallengePage = title.includes('checking your browser') || 
                                       title.includes('just a moment') || 
                                       document.querySelector('#challenge-running') !== null;
                
                const turnstileContainer = document.querySelector('#turnstile-container') || 
                                         document.querySelector('.cf-turnstile') ||
                                         document.querySelector('#cf-chl-widget-multi');
                
                if (!isChallengePage && !turnstileContainer) return { solved: true };

                const responseInput = document.querySelector('[name="cf-turnstile-response"]');
                if (responseInput && responseInput.value && responseInput.value.length > 10) {
                    return { solved: true };
                }

                const widgetIframe = document.querySelector('iframe[src*="cloudflare.com/cdn-cgi/challenge"]');
                if (widgetIframe) {
                    // We can't see inside the iframe easily, but sometimes the container classes change
                    if (turnstileContainer.innerHTML.includes('Success!') || 
                        turnstileContainer.innerText.includes('Success!')) {
                        return { solved: true };
                    }
                }

                if (!isChallengePage && !turnstileContainer) return { solved: true };

                let rect = null;
                const turnstileIframe = document.querySelector('iframe[src*="cloudflare.com/cdn-cgi/challenge"]') || 
                                      document.querySelector('iframe[id*="cf-chl"]') ||
                                      document.querySelector('#cf-chl-widget-multi-iframe');
                
                if (turnstileIframe) {
                    const r = turnstileIframe.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) rect = { x: r.left + r.width/2, y: r.top + r.height/2 };
                } else if (turnstileContainer) {
                    const r = turnstileContainer.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) rect = { x: r.left + r.width/2, y: r.top + r.height/2 };
                }

                return { solved: false, rect: rect };
            })()
        """)
        
        info = parse_eval_result(result)
        if not info or info.get('solved'):
            if info and info.get('solved'):
                print("Cloudflare verification confirmed SOLVED.")
            return True

        print("Cloudflare challenge detected. Running external bypass...")
        
        def run_bypass():
            return bypass(mode='light', warmup_time=2, timeout=20)
        
        loop = asyncio.get_event_loop()
        bypassed = await loop.run_in_executor(None, run_bypass)
        
        if bypassed:
            print("External bypass reports success!")
            return True
        else:
            print("External bypass timed out, falling back to coordinate click...")
            return False
    except Exception as e:
        print(f"Bypass error: {e}")
        return False

async def get_apikey_auto():
    """
    Uses nodriver to automatically retrieve a new API Key.
    """
    print("Launching browser with nodriver...")
    headless = os.environ.get("HEADLESS", "False").lower() == "true"
    
    # Adding extra flags for VPS/Root environments
    browser_args = [
        '--no-sandbox', 
        '--disable-setuid-sandbox', 
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--window-size=1280,720',
        '--start-maximized'
    ]
    
    browser = await uc.start(
          headless=headless, 
          browser_args=browser_args,
          no_sandbox=True,
          lang='en-US'
      )
    tab = await browser.get(KEYGEN_URL)
    
    try:
        print("Waiting for page load and Turnstile...")
        
        start_time = time.time()
        button_clicked = False
        
        # Rapid polling loop for real-time response (checks every 1 second)
        while time.time() - start_time < 180: # 3 minute total timeout
            try:
                # 1. Run the Cloudflare Bypass Helper first
                is_solved = await solve_cloudflare_challenge(tab)
                if not is_solved:
                    # Fallback to manual coordinate detection if the library fails
                    print("Bypass library failed, trying manual detection...")
                    result = await tab.evaluate("""
                        (function() {
                            const turnstileIframe = document.querySelector('iframe[src*="cloudflare.com/cdn-cgi/challenge"]') || 
                                                  document.querySelector('iframe[id*="cf-chl"]') ||
                                                  document.querySelector('#cf-chl-widget-multi-iframe');
                            
                            const turnstileContainer = document.querySelector('#turnstile-container') || 
                                                     document.querySelector('.cf-turnstile') ||
                                                     document.querySelector('#cf-chl-widget-multi');

                            let rect = null;
                            if (turnstileIframe) {
                                const r = turnstileIframe.getBoundingClientRect();
                                if (r.width > 0 && r.height > 0) rect = { x: r.left + r.width/2, y: r.top + r.height/2 };
                            } else if (turnstileContainer) {
                                const r = turnstileContainer.getBoundingClientRect();
                                if (r.width > 0 && r.height > 0) rect = { x: r.left + r.width/2, y: r.top + r.height/2 };
                            }
                            return rect;
                        })()
                    """)
                    rect = parse_eval_result(result)
                    if rect and isinstance(rect, dict):
                        x, y = rect['x'], rect['y']
                        print(f"Manual Turnstile click at ({x}, {y}) using native mouse...")
                        
                        # Use native nodriver mouse events (Trusted events)
                        await tab.mouse_click(x, y)
                        
                        # JS backup click
                        await tab.evaluate(f"""
                            (function() {{
                                const x = {x};
                                const y = {y};
                                const el = document.elementFromPoint(x, y) || document.body;
                                ['mousedown', 'mouseup', 'click'].forEach(type => {{
                                    el.dispatchEvent(new MouseEvent(type, {{
                                        view: window, bubbles: true, cancelable: true, clientX: x, clientY: y
                                    }}));
                                }});
                            }})()
                        """)
                    
                    await tab.sleep(2)
                    continue

                # 2. Check main page state
                result = await tab.evaluate("""
                    (function() {
                        const btn = document.querySelector('#generateBtn') || 
                                    document.querySelector('button.generate-btn') ||
                                    Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Generate'));
                                    
                        const keyContainer = document.querySelector('.api-key div') || 
                                           document.querySelector('#api-key-display');
                        
                        if (keyContainer && keyContainer.innerText.trim().length > 5) {
                            return { state: 'key_found', key: keyContainer.innerText.trim() };
                        }
                        
                        const turnstileContainer = document.querySelector('#turnstile-container') || 
                                                 document.querySelector('.cf-turnstile');
                        const responseInput = document.querySelector('[name="cf-turnstile-response"]');
                        const isSolved = responseInput && responseInput.value && responseInput.value.length > 10;
                        
                        if (!btn) return { state: 'not_found' };
                        
                        const isDisabled = btn.disabled || 
                                         btn.classList.contains('disabled') || 
                                         btn.getAttribute('aria-disabled') === 'true';
                        
                        return {
                            state: 'button_found',
                            disabled: isDisabled,
                            visible: btn.offsetWidth > 0 && btn.offsetHeight > 0,
                            turnstile_solved: isSolved
                        };
                    })()
                """)
                
                info = parse_eval_result(result)
                if not info or not isinstance(info, dict):
                    await tab.sleep(1)
                    continue

                state = info.get('state')
                turnstile_solved = info.get('turnstile_solved', False)
                
                if state == 'key_found':
                    api_key = info.get('key')
                    print(f"Successfully retrieved new API Key: {api_key}")
                    return api_key
                
                if state == 'button_found':
                    is_disabled = info.get('disabled', True)
                    is_visible = info.get('visible', False)
                    
                    should_click = (not is_disabled and is_visible) or (turnstile_solved and is_visible)
                    
                    if should_click:
                        if not button_clicked or (turnstile_solved and int(time.time()) % 5 == 0):
                            if turnstile_solved and is_disabled:
                                print("Turnstile solved! FORCING button click despite disabled state...")
                            else:
                                print("Generate button is ENABLED and READY. Clicking now...")
                            

                            await tab.evaluate("""
                                (function() {
                                    const btn = document.querySelector('#generateBtn') || 
                                                document.querySelector('button.generate-btn') ||
                                                Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Generate'));
                                    if (btn) {
                                        btn.disabled = false;
                                        btn.classList.remove('disabled');
                                        btn.removeAttribute('disabled');
                                        btn.setAttribute('aria-disabled', 'false');
                                        
                                        btn.click();
                                        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                                    }
                                })()
                            """)
                            
                            # Native click backup
                            btn_rect = await tab.evaluate("""
                                (function() {
                                    const btn = document.querySelector('#generateBtn') || 
                                                document.querySelector('button.generate-btn') ||
                                                Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Generate'));
                                    if (btn) {
                                        const r = btn.getBoundingClientRect();
                                        return { x: r.left + r.width/2, y: r.top + r.height/2 };
                                    }
                                    return null;
                                })()
                            """)
                            btn_coords = parse_eval_result(btn_rect)
                            if btn_coords and isinstance(btn_coords, dict):
                                await tab.mouse_click(btn_coords['x'], btn_coords['y'])
                                
                            button_clicked = True
                            await tab.sleep(1)
                        else:
                            print("Waiting for key generation...")
                    else:
                        if turnstile_solved:
                            print("Turnstile solved, but button not visible yet...")
                        else:
                            print("Button found but waiting for Turnstile verification...")
                else:
                    print("Waiting for main page elements...")

            except Exception as e:
                print(f"Polling error: {e}")
            
            await tab.sleep(1)
            
        print("Timed out waiting for process to complete.")
        await take_screenshot(tab, "automation_timeout")
        
    except Exception as e:
        print(f"Unexpected error during automation: {e}")
        try:
            await take_screenshot(tab, "automation_error")
        except:
            pass
    finally:
        try:
            browser.stop()
        except:
            pass
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

async def main():
    api_key = await get_apikey_auto()
    if api_key:
        save_token(api_key)
    else:
        print("Failed to retrieve API key.")

if __name__ == "__main__":
    uc.loop().run_until_complete(main())
