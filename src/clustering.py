#!/usr/bin/env python3
"""
Blocket Scraper Clustering Engine - Cohort & Deal Segmenter
Analyzes prices and listing durations, segmenting active items into value segments
(Underpriced Deals, Stale/Negotiable, Overpriced, Fair Value).
"""

import os
import sys
import duckdb
from datetime import datetime

# Bucketing logic for attributes
def get_year_bucket(year):
    if not year:
        return "Unknown"
    if year < 1990:
        return "<1990"
    elif year <= 1999:
        return "1990-1999"
    elif year <= 2005:
        return "2000-2005"
    elif year <= 2010:
        return "2006-2010"
    elif year <= 2015:
        return "2011-2015"
    elif year <= 2020:
        return "2016-2020"
    elif year <= 2023:
        return "2021-2023"
    else:
        return "2024+"

def get_mileage_bucket(km):
    if km is None:
        return "Unknown"
    if km <= 5000:
        return "0-5k"
    elif km <= 15000:
        return "5k-15k"
    elif km <= 30000:
        return "15k-30k"
    else:
        return "30k+"

def get_cc_bucket(cc):
    if not cc:
        return "Unknown"
    if cc <= 125:
        return "<125cc"
    elif cc <= 300:
        return "126-300cc"
    elif cc <= 650:
        return "301-650cc"
    elif cc <= 1000:
        return "651-1000cc"
    else:
        return ">1000cc"

def get_location_city_tier(loc):
    if not loc:
        return "Unknown"
    loc_lower = loc.lower()
    if loc_lower in ['stockholm', 'göteborg', 'malmö', 'uppsala', 'täby', 'upplands väsby', 'hisings kärra', 'kållered', 'huddinge', 'solna']:
        return "Metropolitan"
    elif loc_lower in ['västerås', 'örebro', 'linköping', 'eskilstuna', 'gävle', 'karlstad', 'sundsvall', 'umeå', 'norrköping', 'jönköping']:
        return "Urban Center"
    else:
        return "Regional/Rural"

def run_market_clustering(db_path: str):
    """Computes pricing and speed-of-sale cohort clustering and writes back to DuckDB."""
    print(f"📊 [Clustering Engine] Starting market clustering on DuckDB: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"⚠️ Warning: Database file not found at {db_path}. Skipping clustering.")
        return False
        
    try:
        conn = duckdb.connect(db_path, read_only=False)
        
        # 1. Create table for analysis results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_clusters_analysis (
                listing_id VARCHAR PRIMARY KEY,
                cohort_level VARCHAR,
                cohort_key VARCHAR,
                cohort_size INTEGER,
                cohort_median_price INTEGER,
                price_deviation_pct DOUBLE,
                cohort_median_duration_hours DOUBLE,
                listing_duration_hours DOUBLE,
                duration_ratio DOUBLE,
                location_tier VARCHAR,
                market_segment_tag VARCHAR,
                negotiability_score INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Ingest active & removed listings directly from physical tables (fully optimized)
        listings = conn.execute("""
            SELECT 
                b.id, b.title, b.status, b.location, b.last_price AS price_sek, 
                m.brand, m.model, m.model_year, m.mileage_km, m.engine_cc, m.vehicle_type,
                b.published_at, b.removed_at, b.last_scraped_at
            FROM blocket_listings b
            LEFT JOIN motorcycle_details m ON b.id = m.listing_id
            WHERE b.last_price IS NOT NULL;
        """).fetchall()
        
        if not listings:
            print("📭 No listings found to cluster.")
            conn.close()
            return True

        # Group listings into hierarchical cohorts
        cohorts_lvl_1 = {}
        cohorts_lvl_2 = {}
        cohorts_lvl_3 = {}
        cohorts_lvl_4 = {}
        cohorts_lvl_5 = {}

        processed_listings = []
        
        for row in listings:
            (l_id, title, status, loc, price, brand, model, year, km, cc, v_type, 
             pub_at, rem_at, last_at) = row
            
            end_time = rem_at if status == 'removed' else last_at
            duration_hours = 0.0
            if pub_at and end_time:
                duration_hours = (end_time - pub_at).total_seconds() / 3600.0
                
            y_bucket = get_year_bucket(year)
            m_bucket = get_mileage_bucket(km)
            cc_bucket = get_cc_bucket(cc)
            loc_tier = get_location_city_tier(loc)
            
            brand_clean = (brand or "Unknown").upper()
            v_type_clean = (v_type or "Unknown").capitalize()
            
            # Construct Cohort keys
            k1 = (brand_clean, v_type_clean, y_bucket, cc_bucket, m_bucket)
            k2 = (brand_clean, v_type_clean, y_bucket, cc_bucket)
            k3 = (brand_clean, v_type_clean, y_bucket)
            k4 = (brand_clean, v_type_clean)
            k5 = (v_type_clean,)
            
            item = {
                "id": l_id, "title": title, "status": status, "price": price, 
                "duration": duration_hours, "loc_tier": loc_tier, "keys": [k1, k2, k3, k4, k5]
            }
            processed_listings.append(item)
            
            for map_dict, key in [(cohorts_lvl_1, k1), (cohorts_lvl_2, k2), 
                                 (cohorts_lvl_3, k3), (cohorts_lvl_4, k4), (cohorts_lvl_5, k5)]:
                if key not in map_dict:
                    map_dict[key] = []
                map_dict[key].append(item)

        # Pre-calculate median price, median duration, and sizes
        def get_cohort_stats(cohort_list):
            prices = [x["price"] for x in cohort_list]
            durations = [x["duration"] for x in cohort_list if x["duration"] > 0]
            
            prices.sort()
            med_price = prices[len(prices)//2] if prices else 0
            
            durations.sort()
            med_duration = durations[len(durations)//2] if durations else 24.0
            
            return len(cohort_list), med_price, med_duration

        cohort_stats_lvl = [
            ({k: get_cohort_stats(v) for k, v in cohorts_lvl_1.items()}, "Level 1 (Specific Specification)"),
            ({k: get_cohort_stats(v) for k, v in cohorts_lvl_2.items()}, "Level 2 (Model Vintage & Engine)"),
            ({k: get_cohort_stats(v) for k, v in cohorts_lvl_3.items()}, "Level 3 (Brand & Vintage)"),
            ({k: get_cohort_stats(v) for k, v in cohorts_lvl_4.items()}, "Level 4 (Brand & Style)"),
            ({k: get_cohort_stats(v) for k, v in cohorts_lvl_5.items()}, "Level 5 (Style Class Fallback)")
        ]

        insert_records = []
        for item in processed_listings:
            l_id = item["id"]
            price = item["price"]
            duration = item["duration"]
            loc_tier = item["loc_tier"]
            
            cohort_lvl_name = "Level 5"
            cohort_size, cohort_median_price, cohort_median_duration = 0, 0, 0
            cohort_key_str = ""
            
            for idx, (stats_map, lvl_desc) in enumerate(cohort_stats_lvl):
                key = item["keys"][idx]
                if key in stats_map:
                    c_size, c_med_p, c_med_d = stats_map[key]
                    if c_size >= 8 or idx == 4:
                        cohort_lvl_name = lvl_desc
                        cohort_size = c_size
                        cohort_median_price = c_med_p
                        cohort_median_duration = c_med_d
                        cohort_key_str = " | ".join(list(key))
                        break
            
            price_dev_pct = 0.0
            if cohort_median_price > 0:
                price_dev_pct = ((price - cohort_median_price) / cohort_median_price) * 100.0
                
            duration_ratio = 1.0
            if cohort_median_duration > 0:
                duration_ratio = duration / cohort_median_duration
                
            if price_dev_pct <= -15.0 and duration_ratio <= 1.2:
                tag = "🔥 Underpriced Deal"
            elif duration_ratio > 1.8 and item["status"] == 'active':
                tag = "🤝 Highly Negotiable"
            elif duration_ratio > 1.3 and item["status"] == 'active':
                tag = "🤝 Negotiable"
            elif price_dev_pct >= 15.0:
                tag = "🔴 Overpriced"
            else:
                tag = "🟢 Fair Value"
                
            neg_score = 0
            if item["status"] == 'active':
                if duration_ratio > 1.0:
                    neg_score = min(95, int((duration_ratio - 1.0) * 45))
                    if loc_tier == "Regional/Rural":
                        neg_score = min(100, neg_score + 10)
                    elif loc_tier == "Metropolitan":
                        neg_score = max(0, neg_score - 5)
                else:
                    neg_score = int(max(0, (duration_ratio) * 20))
            
            insert_records.append((
                l_id, cohort_lvl_name, cohort_key_str, cohort_size, cohort_median_price,
                price_dev_pct, cohort_median_duration, duration, duration_ratio,
                loc_tier, tag, neg_score
            ))

        # 3. Write results to DuckDB
        conn.execute("DELETE FROM market_clusters_analysis;")
        conn.executemany("""
            INSERT INTO market_clusters_analysis (
                listing_id, cohort_level, cohort_key, cohort_size, cohort_median_price,
                price_deviation_pct, cohort_median_duration_hours, listing_duration_hours,
                duration_ratio, location_tier, market_segment_tag, negotiability_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, insert_records)
        
        # 4. Recreate View listings_deal_finder
        conn.execute("DROP VIEW IF EXISTS listings_deal_finder;")
        conn.execute("""
            CREATE VIEW listings_deal_finder AS
            SELECT 
                la.brand, la.model, la.model_year, la.mileage_km, la.vehicle_type,
                la.price_sek AS listed_price,
                c.cohort_median_price AS fair_market_value,
                c.price_deviation_pct AS discount_pct,
                round(c.listing_duration_hours / 24.0, 1) AS days_on_market,
                round(c.cohort_median_duration_hours / 24.0, 1) AS avg_days_to_sell,
                c.location_tier,
                la.location,
                c.market_segment_tag,
                c.negotiability_score,
                la.url
            FROM listings_analytics la
            JOIN market_clusters_analysis c ON la.id = c.listing_id
            WHERE la.is_active = TRUE;
        """)

        conn.commit()
        conn.close()
        print("✅ [Clustering Engine] Cohort segmentation and view updates successfully saved.")
        return True
    except Exception as e:
        print(f"❌ [Clustering Engine] Error during clustering: {e}")
        return False
