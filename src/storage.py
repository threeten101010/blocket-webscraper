#!/usr/bin/env python3
"""
Blocket Scraper Storage Pipeline - Advanced Tracker
Saves parsed listings dynamically into a local DuckDB analytical database.
Maintains price and engagement (likes) history over time, and automatically
detects when an ad is removed to preserve the last active price and date.
"""

import os
import re
from datetime import datetime
import duckdb

class SQLStorage:
    def __init__(self, db_path: str):
        """Initialize the storage pipeline and prepare database directories."""
        self.db_path = db_path
        
        # Ensure directories exist
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        self.initialize_db()
        
    def initialize_db(self):
        """Creates the analytical tracking schema in DuckDB if it doesn't exist."""
        print(f"🗄️ [Storage] Connecting to DuckDB: {self.db_path}")
        conn = duckdb.connect(self.db_path)
        
        # 1. Main listing status registry
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blocket_listings (
                id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                location VARCHAR,
                seller_type VARCHAR,
                published_at TIMESTAMP,
                created_year INTEGER,        -- Year ad was posted
                created_month INTEGER,       -- Month ad was posted (seasonal analytics)
                status VARCHAR DEFAULT 'active', -- 'active' or 'removed'
                first_scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                removed_at TIMESTAMP,        -- When ad was identified as deactivated
                last_price INTEGER,          -- Last known price in SEK
                last_like_count INTEGER      -- Last known likes/saves count
            )
        """)
        
        # Ensure is_active and description columns exist
        conn.execute("ALTER TABLE blocket_listings ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        conn.execute("ALTER TABLE blocket_listings ADD COLUMN IF NOT EXISTS description VARCHAR")
        
        # 2. Time-series Price & Likes History (Engagement Tracker)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                listing_id VARCHAR,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price INTEGER NOT NULL,
                like_count INTEGER,
                PRIMARY KEY (listing_id, scraped_at)
            )
        """)
        
        # 3. Motorcycle Specs Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS motorcycle_details (
                listing_id VARCHAR PRIMARY KEY,
                brand VARCHAR,
                model VARCHAR,
                model_year INTEGER,          -- Vehicle model year
                mileage_km INTEGER,
                engine_cc INTEGER,
                gearbox VARCHAR,
                fuel_type VARCHAR
            )
        """)
        
        # Ensure new columns exist on motorcycle_details
        conn.execute("ALTER TABLE motorcycle_details ADD COLUMN IF NOT EXISTS vehicle_type VARCHAR")
        conn.execute("ALTER TABLE motorcycle_details ADD COLUMN IF NOT EXISTS reg_number VARCHAR")
        
        # 4. Dealers Reference Table (Keyed by natural Org.nr Primary Key)
        conn.execute("DROP VIEW IF EXISTS listings_analytics")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dealers (
                org_nr VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                location VARCHAR
            )
        """)
        
        # Ensure dealer_org_nr column exists on blocket_listings
        conn.execute("ALTER TABLE blocket_listings ADD COLUMN IF NOT EXISTS dealer_org_nr VARCHAR")
        
        # Drop legacy dealer_id column from blocket_listings to keep table structure strictly clean
        try:
            conn.execute("ALTER TABLE blocket_listings DROP COLUMN dealer_id")
        except Exception:
            pass
        
        # 5. Premium Analytical View for Listing Snapshots and Price Performance (Enriched with Dealer data)
        conn.execute("""
            CREATE OR REPLACE VIEW listings_analytics AS
            SELECT 
                l.id,
                l.title,
                l.url,
                l.location,
                l.seller_type,
                l.published_at,
                l.created_year,
                l.created_month,
                l.status,
                l.is_active,
                l.description AS description,
                l.first_scraped_at,
                l.last_scraped_at,
                l.removed_at,
                l.last_price AS price_sek,
                d.brand,
                d.model,
                d.model_year,
                d.mileage_km,
                d.engine_cc,
                d.gearbox,
                d.fuel_type,
                d.vehicle_type,
                d.reg_number,
                l.dealer_org_nr AS dealer_org_nr,
                dl.name AS dealer_name,
                dl.location AS dealer_location,
                (SELECT COUNT(*) FROM price_history ph WHERE ph.listing_id = l.id) AS price_update_count,
                (SELECT MIN(price) FROM price_history ph WHERE ph.listing_id = l.id) AS min_price_sek,
                (SELECT MAX(price) FROM price_history ph WHERE ph.listing_id = l.id) AS max_price_sek
            FROM blocket_listings l
            LEFT JOIN motorcycle_details d ON l.id = d.listing_id
            LEFT JOIN dealers dl ON l.dealer_org_nr = dl.org_nr;
        """)
        
        conn.close()
        
    def save_listings(self, listings, category: str = None) -> int:
        """
        Saves scraped items, registers new price/likes records in history if changed,
        and keeps track of time-series data.
        """
        if not listings:
            return 0
            
        conn = duckdb.connect(self.db_path)
        inserted_count = 0
        scraped_ids = []
        
        for item in listings:
            try:
                scraped_ids.append(item.id)
                # Parse publication date to extract year/month
                pub_date = None
                created_year = None
                created_month = None
                
                if hasattr(item, 'published_at') and item.published_at:
                    try:
                        # Extract YYYY-MM
                        pub_date = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
                        created_year = pub_date.year
                        created_month = pub_date.month
                    except Exception:
                        # Fallback to current date
                        pub_date = datetime.now()
                        created_year = pub_date.year
                        created_month = pub_date.month
                
                # Dynamic check for likes if present in payload (fallback 0)
                like_count = getattr(item, 'like_count', 0)
                
                # Process Dealer information if present
                detail_html = None
                dealer_org_nr = None
                dealer_name = getattr(item, 'dealer_name', None)
                if dealer_name:
                    # Check if we already have the org_nr for this dealer name
                    existing_dealer = conn.execute(
                        "SELECT org_nr FROM dealers WHERE name = ?", [dealer_name.strip()]
                    ).fetchone()
                    
                    if existing_dealer:
                        dealer_org_nr = existing_dealer[0]
                        
                    # If dealer is new or org_nr is missing, run JIT deep scrape of detail page
                    if not dealer_org_nr:
                        print(f"🕵️ Deep scraping detail page for new dealer: {dealer_name} ({item.url})...")
                        try:
                            # Dynamic import to avoid circular dependencies
                            from src.scraper import fetch_page_requests
                            detail_html = fetch_page_requests(item.url)
                            if detail_html:
                                org_match = re.search(r'\b([0-9]{6}-[0-9]{4})\b', detail_html)
                                if org_match:
                                    dealer_org_nr = org_match.group(1)
                                    print(f"✅ Discovered org.nr for {dealer_name}: {dealer_org_nr}")
                                else:
                                    print(f"⚠️ No org.nr found in detail page for {dealer_name}.")
                        except Exception as e:
                            print(f"❌ Failed to extract org.nr dynamically: {e}")
                    
                    # Store in dealers reference table linked by org_nr Primary Key
                    if dealer_org_nr:
                        conn.execute("""
                            INSERT INTO dealers (org_nr, name, location)
                            VALUES (?, ?, ?)
                            ON CONFLICT (org_nr) DO UPDATE SET
                                name = excluded.name,
                                location = excluded.location
                        """, (dealer_org_nr, dealer_name.strip(), item.location))

                # Define placeholders for type and registration number
                vehicle_type = getattr(item, 'vehicle_type', None)
                reg_number = getattr(item, 'reg_number', None)

                existing = conn.execute(
                    "SELECT last_price, last_like_count, status FROM blocket_listings WHERE id = ?",
                    [item.id]
                ).fetchone()
                            # Check if specs or description are missing in the database to enable self-healing automatic backfill
                need_details = False
                existing_details = None
                description_text = None
                
                if existing:
                    existing_details = conn.execute(
                        "SELECT reg_number, vehicle_type FROM motorcycle_details WHERE listing_id = ?",
                        [item.id]
                    ).fetchone()
                    
                    existing_desc = conn.execute(
                        "SELECT description FROM blocket_listings WHERE id = ?",
                        [item.id]
                    ).fetchone()
                    
                    if existing_desc and existing_desc[0]:
                        description_text = existing_desc[0]
                    
                    # Trigger JIT details if specs are missing OR if description is missing
                    if not existing_details or not existing_details[0] or not existing_details[1] or not description_text:
                        if not reg_number or not vehicle_type or not description_text:
                            need_details = True
                else:
                    need_details = True
 
                # Perform JIT details and description scrape if needed
                if need_details:
                    if not detail_html:
                        print(f"🔍 JIT deep scraping specs & description for: {item.title} ({item.url})...")
                        try:
                            from src.scraper import fetch_page_requests
                            detail_html = fetch_page_requests(item.url)
                        except Exception as e:
                            print(f"❌ Failed to fetch detail page: {e}")
                             
                    if detail_html:
                        try:
                            from bs4 import BeautifulSoup
                            import json
                            soup = BeautifulSoup(detail_html, 'html.parser')
                            
                            # A. Extract Description using CSS Selectors
                            desc_div = soup.find('div', class_=re.compile(r'Description__DescriptionContent|description|body', re.IGNORECASE))
                            if not desc_div:
                                desc_div = soup.find('div', {'data-testid': 'ad-description'})
                            if desc_div:
                                description_text = desc_div.get_text("\n", strip=True)
                            
                            # B. Fallback JSON __NEXT_DATA__ parsing
                            if not description_text:
                                next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', detail_html)
                                if next_data_match:
                                    try:
                                        data = json.loads(next_data_match.group(1))
                                        apollo_state = data.get("props", {}).get("pageProps", {}).get("apolloState", {})
                                        for key, val in apollo_state.items():
                                            if key.startswith("Ad:"):
                                                description_text = val.get("body")
                                                break
                                    except Exception:
                                        pass
                                        
                            if description_text:
                                print(f"   ↳ Description loaded: {description_text[:40]}... ({len(description_text)} chars)")
                            
                            # Extract Typ and Registreringsnummer using definition list siblings
                            for dt in soup.find_all('dt'):
                                dt_text = dt.get_text(" ", strip=True).lower()
                                dd = dt.find_next_sibling('dd')
                                if dd:
                                    val_text = dd.get_text(" ", strip=True)
                                    if 'typ' in dt_text and not vehicle_type:
                                        vehicle_type = val_text
                                        print(f"   ↳ Typ: {vehicle_type}")
                                    elif 'registreringsnummer' in dt_text and not reg_number:
                                        reg_number = val_text
                                        print(f"   ↳ Reg.nr: {reg_number}")
                                         
                            # Backup regex for registration number in case HTML layout changes
                            if not reg_number:
                                reg_match = re.search(r'\b(?:registreringsnummer|reg\.nr|regnr)\s*:\s*([a-z]{3}\s*\d{2}[a-z0-9])', detail_html, re.IGNORECASE)
                                if reg_match:
                                    reg_number = reg_match.group(1).replace(" ", "").upper()
                                    print(f"   ↳ Reg.nr (regex): {reg_number}")
                        except Exception as e:
                            print(f"❌ Failed to parse detail page specs & description: {e}")

                # Merge with existing details if JIT scrape returned empty but DB already had them
                if existing_details:
                    if not reg_number:
                        reg_number = existing_details[0]
                    if not vehicle_type:
                        vehicle_type = existing_details[1]
                
                if existing:
                    old_price, old_likes, status = existing
                    
                    # Update active listing (Coalescing description so we do not overwrite a fetched one with null)
                    conn.execute("""
                        UPDATE blocket_listings SET
                            title = ?,
                            location = ?,
                            last_price = ?,
                            last_like_count = ?,
                            seller_type = ?,
                            dealer_org_nr = ?,
                            description = COALESCE(?, description),
                            last_scraped_at = CURRENT_TIMESTAMP,
                            status = 'active',
                            is_active = TRUE,
                            removed_at = NULL
                        WHERE id = ?
                    """, (item.title, item.location, item.price, like_count, getattr(item, 'seller_type', 'private'), dealer_org_nr, description_text, item.id))
                    
                    # Insert history record ONLY if price or likes changed (to save space)
                    if item.price != old_price or like_count != old_likes or status == 'removed':
                        conn.execute("""
                            INSERT INTO price_history (listing_id, price, like_count)
                            VALUES (?, ?, ?)
                        """, (item.id, item.price, like_count))
                else:
                    # New Listing: Insert Registry
                    conn.execute("""
                        INSERT INTO blocket_listings 
                        (id, title, url, location, seller_type, published_at, created_year, created_month, last_price, last_like_count, dealer_org_nr, is_active, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?)
                    """, (
                        item.id, item.title, item.url, item.location, 
                        getattr(item, 'seller_type', 'private'), pub_date, 
                        created_year, created_month, item.price, like_count, dealer_org_nr, description_text
                    ))
                    
                    # New Listing: Insert History
                    conn.execute("""
                        INSERT INTO price_history (listing_id, price, like_count)
                        VALUES (?, ?, ?)
                    """, (item.id, item.price, like_count))
                    
                # Save vehicle specs if details are parsed
                brand = getattr(item, 'brand', None)
                if brand or vehicle_type or reg_number:
                    conn.execute("""
                        INSERT INTO motorcycle_details 
                        (listing_id, brand, model, model_year, mileage_km, engine_cc, gearbox, fuel_type, vehicle_type, reg_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (listing_id) DO UPDATE SET
                            brand = excluded.brand,
                            model = excluded.model,
                            model_year = excluded.model_year,
                            mileage_km = excluded.mileage_km,
                            engine_cc = excluded.engine_cc,
                            gearbox = excluded.gearbox,
                            fuel_type = excluded.fuel_type,
                            vehicle_type = excluded.vehicle_type,
                            reg_number = excluded.reg_number
                    """, (
                        item.id, brand, getattr(item, 'model', None),
                        getattr(item, 'model_year', None), getattr(item, 'mileage_km', None),
                        getattr(item, 'engine_cc', None), getattr(item, 'gearbox', None),
                        getattr(item, 'fuel_type', None), vehicle_type, reg_number
                    ))
                
                inserted_count += 1
            except Exception as e:
                print(f"⚠️ [Storage] Error parsing item {item.id}: {e}")
                continue
                
        conn.commit()
        
        # 4. Deactivation Routine (Automatic Removal Detection)
        # If we successfully parsed a complete search page, identify which active items went missing.
        if scraped_ids and category:
            self.detect_removals(conn, scraped_ids, category)
            
        conn.close()
        return inserted_count
        
    def detect_removals(self, conn, scraped_ids: list, category: str):
        """
        Flags listings previously marked as 'active' under this category 
        that did not appear in the current scrape run as 'removed'.
        """
        # Convert list to SQL list string
        id_placeholders = ",".join(["?"] * len(scraped_ids))
        
        # Fetch active listing IDs that went missing in this crawl run
        # To avoid false flags, we restrict this check to matching listings
        missing_listings = conn.execute(f"""
            SELECT id FROM blocket_listings 
            WHERE is_active = TRUE 
              AND id NOT IN ({id_placeholders})
        """, scraped_ids).fetchall()
        
        if missing_listings:
            print(f"🧹 [Storage] Identified {len(missing_listings)} deactivated/removed listings.")
            for row in missing_listings:
                missing_id = row[0]
                conn.execute("""
                    UPDATE blocket_listings SET
                        status = 'removed',
                        is_active = FALSE,
                        removed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, [missing_id])
                
    def detect_removals_sweep(self, all_scraped_ids: list):
        """
        Flags listings previously marked as 'active' in the database
        that did not appear at all during the entire sweep as 'removed'.
        """
        if not all_scraped_ids:
            return
            
        conn = duckdb.connect(self.db_path)
        # Convert list to SQL list string
        id_placeholders = ",".join(["?"] * len(all_scraped_ids))
        
        # Fetch active listing IDs that went missing
        missing_listings = conn.execute(f"""
            SELECT id FROM blocket_listings 
            WHERE is_active = TRUE 
              AND id NOT IN ({id_placeholders})
        """, all_scraped_ids).fetchall()
        
        if missing_listings:
            print(f"🧹 [Storage] Identified {len(missing_listings)} deactivated/removed listings.")
            for row in missing_listings:
                missing_id = row[0]
                conn.execute("""
                    UPDATE blocket_listings SET
                        status = 'removed',
                        is_active = FALSE,
                        removed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, [missing_id])
            conn.commit()
        conn.close()
                
    def get_listing_count(self) -> dict:
        """Returns statistics on active vs removed listings."""
        conn = duckdb.connect(self.db_path)
        stats = conn.execute("""
            SELECT status, COUNT(*) 
            FROM blocket_listings 
            GROUP BY status
        """).fetchall()
        conn.close()
        return dict(stats)
