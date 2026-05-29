#!/usr/bin/env python3
"""
Blocket Web Scraper - Main Entry Point (Continuous Mode)
Orchestrates loading configuration, running HTTP crawls with pagination,
and supports a continuous loop mode that runs, paginates to the end, 
cooldowns, and starts over.
"""

import os
import sys
import yaml
import time
import random
from pathlib import Path

# Insert parent dir to import local src modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scraper import fetch_page_requests, fetch_page_playwright
from src.parser import parse_nextjs_data, parse_html_fallback
from src.storage import SQLStorage

def load_config(config_path: str) -> dict:
    """Safely loads project configuration."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def run_scraper_run(use_browser: bool, config: dict, storage: SQLStorage, base_dir: str):
    """Executes a single sweep through all pages until the end is reached."""
    target_config = config.get("target", {})
    base_url = target_config.get("base_url", "https://www.blocket.se")
    categories = target_config.get("categories", [])
    
    settings = config.get("scraper_settings", {})
    delay = settings.get("delay_seconds", 3.0)
    
    total_new_items = 0
    
    for category in categories:
        cat_name = category.get("name")
        cat_path = category.get("path")
        
        page = 1
        consecutive_empty_pages = 0
        max_empty_pages = 1 # Stop immediately on the first page returning 0 items
        
        print(f"\n📂 Crawling Category: '{cat_name}' (Continuous Sweep Mode)")
        
        all_scraped_ids = []
        
        while True:
            # Construct URL with pagination parameter
            separator = "&" if "?" in cat_path else "?"
            target_url = f"{base_url}{cat_path}{separator}p={page}"
            
            print(f"📄 Scraping Page {page}: {target_url}")
            
            # Fetch HTML source
            if use_browser or settings.get("headless", True) == False:
                html = fetch_page_playwright(target_url)
            else:
                html = fetch_page_requests(target_url)
                
            if not html:
                print(f"⚠️ Failed to fetch page content. Reached boundary or blocked.")
                break
                
            # Parse Data
            items = parse_nextjs_data(html)
            if not items:
                items = parse_html_fallback(html)
                
            if not items:
                print(f"🛑 Reached end of listings on Page {page} (0 parsed items).")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_empty_pages:
                    break
            else:
                consecutive_empty_pages = 0 # Reset counter
                
            # Accumulate IDs for removal detection scan
            for item in items:
                all_scraped_ids.append(item.id)
                
            # Persist to Database (passing category=None to bypass old on-page-1 detect_removals)
            saved_count = storage.save_listings(items, None)
            total_new_items += saved_count
            
            print(f"📝 Page {page} complete. Stored {saved_count} listings.")
            
            # Increment page count
            page += 1
            
            # Politeness delay
            throttle = delay + random.uniform(0.5, 1.5)
            time.sleep(throttle)
            
        # Execute deactivation routine using all accumulated IDs for the complete category sweep
        if all_scraped_ids:
            print(f"🧹 Running deactivation sweep for '{cat_name}' with {len(all_scraped_ids)} scraped listing IDs...")
            storage.detect_removals_sweep(all_scraped_ids)
            
    return total_new_items

def run_scraper(use_browser: bool = False, continuous: bool = False, cooldown_minutes: int = 15):
    print("🚀 --- Starting Blocket Web Scraper Job ---")
    
    # 1. Resolve configuration
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", "scraper_config.yaml")
    
    if not os.path.exists(config_path):
        print(f"❌ Configuration file not found at {config_path}")
        return
        
    config = load_config(config_path)
    
    # 2. Initialize Database
    db_filename = config.get("database", {}).get("filename", "data/scraped_listings.duckdb")
    if not os.path.isabs(db_filename):
        db_path = os.path.join(base_dir, db_filename)
    else:
        db_path = db_filename
        
    storage = SQLStorage(db_path)
    
    # 3. Execution Loops
    if not continuous:
        total = run_scraper_run(use_browser, config, storage, base_dir)
        print("\n🏁 --- Scraper Job Complete ---")
        print(f"📊 New/Updated Listings Stored: {total}")
        print(f"📁 Cumulative Listings in DB:  {storage.get_listing_count()}")
        print("---------------------------------")
    else:
        print(f"🔄 --- Loop Mode Active (Cooldown: {cooldown_minutes} minutes) ---")
        try:
            loop_count = 1
            while True:
                print(f"\n🔄 [Loop #{loop_count}] Starting full crawl cycle...")
                cycle_start = time.time()
                
                total = run_scraper_run(use_browser, config, storage, base_dir)
                
                cycle_duration = (time.time() - cycle_start) / 60
                print(f"\n✅ [Loop #{loop_count} Complete] Crawl duration: {cycle_duration:.2f} mins. Stored: {total} items.")
                print(f"📊 Cumulative Listings in DB: {storage.get_listing_count()}")
                
                print(f"💤 Entering cooldown. Sleeping for {cooldown_minutes} minutes before restarting...")
                time.sleep(cooldown_minutes * 60)
                loop_count += 1
        except KeyboardInterrupt:
            print("\n🛑 Loop Mode terminated by user. Shutting down gracefully...")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Blocket classifieds scraper engine.")
    parser.add_argument("--browser", action="store_true", help="Forces the use of headless browser (Playwright).")
    parser.add_argument("--continuous", action="store_true", help="Enables continuous loop execution mode.")
    parser.add_argument("--cooldown", type=int, default=15, help="Cooldown minutes between loop restarts.")
    args = parser.parse_args()
    
    run_scraper(use_browser=args.browser, continuous=args.continuous, cooldown_minutes=args.cooldown)
