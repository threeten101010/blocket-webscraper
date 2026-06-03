#!/usr/bin/env python3
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def test():
    url = "https://www.blocket.se/mobility/search/mc?price=0-15000&page=1"
    print("Launching Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        print(f"Going to URL: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        
        # Check iframe status
        iframes = page.locator("iframe").all()
        print(f"Total iframes found: {len(iframes)}")
        for idx, iframe in enumerate(iframes):
            iframe_id = iframe.get_attribute("id") or ""
            iframe_name = iframe.get_attribute("name") or ""
            print(f"  [{idx}] ID: {iframe_id}, Name: {iframe_name}")
            
        # Try finding and clicking cookie consent inside iframe
        try:
            iframe_locator = page.locator("iframe[id^='sp_message_iframe_']")
            if iframe_locator.count() > 0:
                print("Found sp_message_iframe! Extracting content frame...")
                frame = page.frame_locator("iframe[id^='sp_message_iframe_']")
                if frame:
                    # Log buttons inside the iframe
                    buttons = frame.locator("button").all()
                    print(f"  Buttons inside iframe: {[b.inner_text().strip() for b in buttons]}")
                    
                    for button_text in ["Acceptera alla", "Godkänn", "Acceptera", "Accept all", "Accept"]:
                        btn = frame.locator(f"button:has-text('{button_text}')")
                        if btn.count() > 0:
                            print(f"  Clicking button: '{button_text}'...")
                            btn.first.click()
                            time.sleep(3)
                            break
            else:
                print("No sp_message_iframe found.")
        except Exception as e:
            print("Error handling iframe:", e)
            
        # Wait a bit and check content
        time.sleep(3)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        print('Final URL:', page.url)
        print('Body classes:', soup.body.get('class') if soup.body else 'No body')
        print('Div count:', len(soup.select('div')))
        print('Article count:', len(soup.select('article')))
        print('Links count:', len(soup.find_all('a')))
        browser.close()

if __name__ == "__main__":
    test()
