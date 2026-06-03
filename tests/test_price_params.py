#!/usr/bin/env python3
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def test():
    urls = [
        ("price=0-15000", "https://www.blocket.se/mobility/search/mc?price=0-15000"),
        ("price_sek=0-15000", "https://www.blocket.se/mobility/search/mc?price_sek=0-15000"),
        ("price_sek_from=0&price_sek_to=15000", "https://www.blocket.se/mobility/search/mc?price_sek_from=0&price_sek_to=15000"),
        ("price_from=0&price_to=15000", "https://www.blocket.se/mobility/search/mc?price_from=0&price_to=15000"),
        ("price_sek=15000", "https://www.blocket.se/mobility/search/mc?price_sek=15000")
    ]
    
    print("Launching Playwright to test price parameters...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        for name, url in urls:
            print(f"\n--- Testing URL: {url} ---")
            page.goto(url, wait_until="load", timeout=30000)
            time.sleep(3)
            
            # Dismiss cookie banner
            try:
                iframe_locator = page.locator("iframe[id^='sp_message_iframe_']")
                if iframe_locator.count() > 0:
                    frame = page.frame_locator("iframe[id^='sp_message_iframe_']")
                    btn = frame.locator("button:has-text('Godkänn alla')")
                    if btn.count() > 0:
                        btn.first.click()
                        time.sleep(2)
            except Exception:
                pass
                
            text = page.locator("body").inner_text()
            # Find the line containing "resultat"
            result_lines = [l for l in text.split("\n") if "resultat" in l.lower()]
            print(f"Results lines: {result_lines}")
            
        browser.close()

if __name__ == "__main__":
    test()
