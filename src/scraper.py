#!/usr/bin/env python3
"""
Blocket Scraper Engine
Manages HTTP requests and provides optional headless Playwright browser drivers
to bypass dynamic Javascript challenges on remote server hosts.
"""

import urllib.request
import urllib.error
import time
import random

# Standard headers to rotate and look like a real browser
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def fetch_page_requests(url: str) -> str:
    """
    Fast and lightweight HTTP fetcher using standard Python urllib.
    Excellent for server-side scrapes without loading full browsers.
    """
    print(f"📡 [Scraper] Fetching URL statically: {url}")
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'sv,en-US;q=0.7,en;q=0.3'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        print(f"❌ [Scraper] HTTP Error {e.code}: {e.reason}")
        return ""
    except Exception as e:
        print(f"❌ [Scraper] Connection error: {e}")
        return ""

def fetch_page_playwright(url: str) -> str:
    """
    Dynamic Javascript fetcher using headless Playwright.
    Launches a real Chromium browser, automatically solves consent cookie banners,
    and returns fully rendered page source. Excellent for remote server jobs.
    """
    print(f"🌐 [Scraper] Launching Playwright browser driver for: {url}")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠️ [Scraper] Playwright not installed. Falling back to static HTTP.")
        return fetch_page_requests(url)
        
    try:
        with sync_playwright() as p:
            # Launch chromium headlessly
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            
            # Go to URL
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Simulate human delay
            time.sleep(random.uniform(2, 4))
            
            # Handle potential cookie banners (common in Sweden/EU)
            # Find and click typical consent buttons (e.g. text containing "Godkänn", "Acceptera", "OK")
            consent_selectors = [
                "button:has-text('Godkänn')",
                "button:has-text('Acceptera')",
                "#accept-cookie-banner",
                ".consent-button"
            ]
            for selector in consent_selectors:
                try:
                    if page.locator(selector).is_visible():
                        page.locator(selector).first.click()
                        print(f"🍪 [Scraper] Handled cookie consent using: {selector}")
                        time.sleep(1)
                        break
                except Exception:
                    continue
                    
            html_content = page.content()
            browser.close()
            return html_content
            
    except Exception as e:
        print(f"❌ [Scraper] Playwright crash: {e}")
        return ""
