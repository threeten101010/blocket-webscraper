#!/usr/bin/env python3
import time
from playwright.sync_api import sync_playwright

def test():
    url = "https://www.blocket.se/annonser/hela_sverige/fordon/motorcyklar"
    print(f"Launching Playwright to intercept requests on: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        # Intercept requests
        requests = []
        def handle_request(request):
            req_url = request.url
            if "search" in req_url or "api" in req_url or "recommerce" in req_url or "graphql" in req_url:
                requests.append(req_url)
                
        page.on("request", handle_request)
        
        try:
            page.goto(url, wait_until="load", timeout=30000)
            time.sleep(5)
            # Dismiss cookie banner if visible
            try:
                iframe_locator = page.locator("iframe[id^='sp_message_iframe_']")
                if iframe_locator.count() > 0:
                    frame = page.frame_locator("iframe[id^='sp_message_iframe_']")
                    btn = frame.locator("button:has-text('Godkänn alla')")
                    if btn.count() > 0:
                        btn.first.click()
                        print("🍪 Dismissed cookie consent banner inside intercept test.")
                        time.sleep(5)
            except Exception:
                pass
        except Exception as e:
            print("Navigation error:", e)
            
        print("\n--- Intercepted Search/API Requests ---")
        for r in set(requests):
            print(r)
        print("---------------------------------------")
        browser.close()

if __name__ == "__main__":
    test()
