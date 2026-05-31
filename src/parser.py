#!/usr/bin/env python3
"""
Blocket Scraper Parser - High-Precision & Robust Text Extraction
Parses HTML document sources or directly extracts JSON payloads.
Implements a strict semantic keyword validator and selector-free text regex tools
to parse prices, mileage, model years, and brands directly from webpage card texts.
"""

import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from typing import Optional, List

class BlocketItem(BaseModel):
    """Pydantic model representing a detailed classified listing."""
    id: str = Field(description="Unique Blocket listing ID")
    title: str = Field(description="Clean listing title")
    price: Optional[int] = Field(None, description="Listing price in SEK")
    url: str = Field(description="Direct URL to listing details")
    location: str = Field(description="Geographic region/city")
    published_at: str = Field(description="Timestamp of publication")
    image_url: Optional[str] = Field(None, description="Primary thumbnail image")
    seller_type: Optional[str] = Field("private", description="private or company")
    dealer_name: Optional[str] = Field(None, description="Dealer name if seller is company")
    
    # Engagement Metric
    like_count: Optional[int] = Field(0, description="Number of favorites/saves")
    
    # Vehicle Specific Parameters (Optional, populated when scraping MCs)
    brand: Optional[str] = Field(None, description="Vehicle Make/Brand")
    model: Optional[str] = Field(None, description="Vehicle Model")
    model_year: Optional[int] = Field(None, description="Vehicle Calendar Year")
    mileage_km: Optional[int] = Field(None, description="Vehicle Mileage in Kilometers")
    engine_cc: Optional[int] = Field(None, description="Engine Size in Cubic Centimeters")
    gearbox: Optional[str] = Field(None, description="Manual or Automatic")
    fuel_type: Optional[str] = Field(None, description="Petrol, Diesel, Electric, etc.")
    vehicle_type: Optional[str] = Field(None, description="Type of motorcycle (e.g. touring, sport, naked)")
    reg_number: Optional[str] = Field(None, description="Registration plate / license number")

def is_motorcycle_listing(title: str, url: str) -> bool:
    """
    Surgical semantic filter to ensure an item is actually a motorcycle.
    """
    title_lower = title.lower()
    url_lower = url.lower()
    
    if "motorcyklar" in url_lower or "/mc/" in url_lower or "motorcykel" in url_lower or "mobility" in url_lower:
        return True
        
    mc_keywords = {
        "yamaha", "ktm", "honda", "suzuki", "kawasaki", "harley", "davidson", 
        "ducati", "bmw", "triumph", "husqvarna", "vespa", "scooter", "aprilia", 
        "guzzi", "indian", "enfield", "benelli", "peugeot", "kymco", "sym", 
        "rieju", "derbi", "gasgas", "sherco", "beta", "fantic", "can-am", "cfmoto", 
        "piaggio", "stark", "voge", "zontes", "bsa", "monark",
        "motorcykel", "mc", "moped", "moppe", "sporthoj", "touring", 
        "offroad", "enduro", "cross", "skoter"
    }
    
    words = set(re.findall(r'\b[a-z]{2,}\b', title_lower))
    
    if words.intersection(mc_keywords):
        return True
        
    if " mc " in f" {title_lower} ":
        return True
        
    return False

def clean_swedish_mileage(mileage_str: str) -> Optional[int]:
    """Converts Swedish 'mil' classification to standard Kilometers (1 mil = 10 km)."""
    if not mileage_str:
        return None
    try:
        digits = re.sub(r'\D', '', mileage_str)
        if digits:
            mil_val = int(digits)
            if "mil" in mileage_str.lower():
                return mil_val * 10
            return mil_val
    except Exception:
        pass
    return None

def clean_engine_size(engine_str: str) -> Optional[int]:
    """Extracts numeric CC value from string. e.g., '689 cc' -> 689."""
    if not engine_str:
        return None
    try:
        digits = re.sub(r'\D', '', engine_str)
        return int(digits) if digits else None
    except Exception:
        pass
    return None

def parse_nextjs_data(html_content: str) -> List[BlocketItem]:
    """
    Elite parsing technique: Extracts the __NEXT_DATA__ script block.
    """
    print("✂_ [Parser] Attempting to extract Next.js __NEXT_DATA__ JSON payload...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    script_tag = soup.find('script', id='__NEXT_DATA__')
    
    if not script_tag:
        print("⚠️ [Parser] __NEXT_DATA__ script block not found. Falling back to CSS parsing.")
        return []
        
    try:
        data = json.loads(script_tag.string)
        props = data.get("props", {})
        page_props = props.get("pageProps", {})
        apollo_state = page_props.get("apolloState", {})
        
        listings_found = []
        
        for key, val in apollo_state.items():
            if key.startswith("Ad:"):
                item_id = key.split(":")[1]
                title = val.get("subject", "No Title")
                
                slug = val.get("shareUrl", "")
                url = f"https://www.blocket.se/annons/{slug}" if slug else ""
                
                if not is_motorcycle_listing(title, url):
                    continue
                
                price_val = val.get("price", {})
                price = price_val.get("value") if isinstance(price_val, dict) else price_val
                
                location_val = val.get("location", [{}])
                location = location_val[0].get("name", "Unknown") if location_val else "Unknown"
                
                published = val.get("listTime", "Unknown")
                
                images = val.get("images", [])
                image_url = images[0].get("url") if images else None
                
                seller_info = val.get("seller", {})
                seller_type = seller_info.get("type", "private") if isinstance(seller_info, dict) else "private"
                dealer_name = None
                if isinstance(seller_info, dict) and seller_type != "private":
                    dealer_name = seller_info.get("name")
                
                likes = val.get("favoriteCount", 0) or val.get("likes", 0)
                
                brand = None
                model = None
                model_year = None
                mileage_km = None
                engine_cc = None
                gearbox = None
                fuel_type = None
                vehicle_type = None
                reg_number = None
                
                params = val.get("parameters", [])
                for p in params:
                    ref_key = p.get("__ref") if isinstance(p, dict) else None
                    if ref_key and ref_key in apollo_state:
                        param_node = apollo_state[ref_key]
                        p_label = param_node.get("label", "")
                        p_value = param_node.get("value", "")
                        p_key = param_node.get("key", "")
                    else:
                        p_label = p.get("label", "") if isinstance(p, dict) else ""
                        p_value = p.get("value", "") if isinstance(p, dict) else ""
                        p_key = p.get("key", "") if isinstance(p, dict) else ""
                        
                    if p_key == "model_year" or "modellår" in p_label.lower():
                        try:
                            model_year = int(re.sub(r'\D', '', p_value))
                        except Exception:
                            pass
                    elif p_key == "mileage" or "miltal" in p_label.lower():
                        mileage_km = clean_swedish_mileage(p_value)
                    elif p_key == "make" or "märke" in p_label.lower():
                        brand = p_value
                    elif p_key == "model" or "modell" in p_label.lower():
                        model = p_value
                    elif p_key == "engine_size" or "motorstorlek" in p_label.lower():
                        engine_cc = clean_engine_size(p_value)
                    elif p_key == "gearbox" or "växellåda" in p_label.lower():
                        gearbox = p_value
                    elif p_key == "fuel" or "drivmedel" in p_label.lower():
                        fuel_type = p_value
                    elif p_key == "vehicle_type" or "typ" in p_label.lower():
                        vehicle_type = p_value
                    elif p_key == "regno" or p_key == "registration_number" or "registreringsnummer" in p_label.lower():
                        reg_number = p_value
                
                listings_found.append(BlocketItem(
                    id=item_id,
                    title=title,
                    price=price,
                    url=url,
                    location=location,
                    published_at=published,
                    image_url=image_url,
                    seller_type=seller_type,
                    dealer_name=dealer_name,
                    like_count=likes,
                    brand=brand,
                    model=model,
                    model_year=model_year,
                    mileage_km=mileage_km,
                    engine_cc=engine_cc,
                    gearbox=gearbox,
                    fuel_type=fuel_type,
                    vehicle_type=vehicle_type,
                    reg_number=reg_number
                ))
                
        print(f"✅ [Parser] Successfully extracted {len(listings_found)} detailed items from Next.js state.")
        return listings_found
        
    except Exception as e:
        print(f"❌ [Parser] Failed to parse Next.js JSON: {e}")
        return []

def extract_model_from_title(title: str, brand: Optional[str]) -> Optional[str]:
    if not brand:
        return None
    model_str = title
    pattern = re.compile(re.escape(brand), re.IGNORECASE)
    model_str = pattern.sub("", model_str)
    
    # Remove duplicate brand mentions
    words = model_str.split()
    unique_words = []
    for w in words:
        if w.lower() != brand.lower() and w not in unique_words:
            unique_words.append(w)
    model_str = " ".join(unique_words)
    
    # Strip model years
    model_str = re.sub(r'[-–—]?\b(19\d{2}|20\d{2})\b', '', model_str)
    model_str = re.sub(r'[-–—]\d{2}\b', '', model_str)
    
    model_str = model_str.strip(" -–—,;.|")
    return model_str if model_str else None

def parse_html_fallback(html_content: str) -> List[BlocketItem]:
    """
    Standard BeautifulSoup CSS selector fallback in case Next.js state isn't present.
    Uses ultra-robust Regex to parse price and mileage parameters directly from card texts.
    """
    print("🎨 [Parser] Extracting via BeautifulSoup CSS selectors...")
    soup = BeautifulSoup(html_content, 'html.parser')
    listings = []
    
    cards = soup.select('article')
    
    for idx, card in enumerate(cards):
        try:
            title_el = card.select_one('h2')
            link_el = card.select_one('a')
            
            if not title_el or not link_el:
                continue
                
            title = title_el.text.strip()
            url = link_el.get('href', '')
            if url.startswith('/'):
                url = "https://www.blocket.se" + url
                
            # Apply high-precision motorcycle filter
            if not is_motorcycle_listing(title, url):
                continue
                
            item_id = re.search(r'(\d+)$', url)
            item_id = item_id.group(1) if item_id else f"html_{idx}"
            
            # --- Robust Spaced Text Extraction to avoid word boundary issues ---
            card_text_spaced = card.get_text(" ", strip=True)
            
            # 1. Parse Price (e.g., '69 900 kr' or '120 000kr')
            price_numeric = 0
            price_match = re.search(r'(\d[\d\s ]*)\s*kr', card_text_spaced)
            if price_match:
                price_str = price_match.group(1)
                price_numeric = int(re.sub(r'\D', '', price_str))
                
            # 2. Parse Specifications from specific tag if present
            model_year = None
            mileage_km = None
            engine_cc = None
            fuel_type = None
            gearbox = None
            
            specs_el = card.select_one('span.text-caption.font-bold')
            if not specs_el:
                # Fallback to search spans
                for span in card.find_all('span'):
                    if 'mil' in span.text or 'cc' in span.text or '∙' in span.text:
                        specs_el = span
                        break
                        
            if specs_el:
                specs_text = specs_el.text
                parts = [p.strip() for p in re.split(r'[∙·•\u2219]', specs_text) if p.strip()]
                for part in parts:
                    if re.match(r'^\d{4}$', part):
                        model_year = int(part)
                    elif 'mil' in part.lower():
                        mileage_km = clean_swedish_mileage(part)
                    elif 'cc' in part.lower():
                        engine_cc = clean_engine_size(part)
                    elif part.lower() in ('bensin', 'diesel', 'el', 'hybrid'):
                        fuel_type = part.capitalize()
                        if fuel_type == 'El':
                            fuel_type = 'Electric'
                    elif part.lower() in ('manuell', 'automat'):
                        gearbox = 'Manual' if part.lower() == 'manuell' else 'Automatic'
            
            # Fallback for year and mileage if specs element wasn't parsed fully
            if not model_year:
                years = re.findall(r'\b(19\d{2}|20\d{2})\b', card_text_spaced)
                for y in years:
                    y_int = int(y)
                    if 1950 <= y_int <= 2027:
                        model_year = y_int
                        break
            if not mileage_km:
                mileage_match = re.search(r'(\d[\d\s ]*)\s*mil', card_text_spaced)
                if mileage_match:
                    mileage_km = clean_swedish_mileage(mileage_match.group(0))
            
            # 3. Parse Brand (match from known list in title)
            brand = None
            mc_brands = {
                "yamaha", "ktm", "honda", "suzuki", "kawasaki", "harley", "davidson", 
                "ducati", "bmw", "triumph", "husqvarna", "vespa", "aprilia", "indian",
                "guzzi", "royal enfield", "enfield", "benelli", "peugeot", "kymco",
                "sym", "rieju", "derbi", "gasgas", "sherco", "beta", "fantic",
                "can-am", "cfmoto", "piaggio", "stark", "voge", "zontes", "bsa", "monark"
            }
            words = set(re.findall(r'\b[a-z-]+\b', title.lower())) # Support hyphenated brands like can-am
            matched_brands = words.intersection(mc_brands)
            if matched_brands:
                brand = list(matched_brands)[0].capitalize()
                if brand in ("Davidson", "Harley"):
                    brand = "Harley-Davidson"
                elif brand in ("Guzzi", "Moto"):
                    brand = "Moto Guzzi"
                elif brand in ("Enfield", "Royal"):
                    brand = "Royal Enfield"
                elif brand == "Can-am":
                    brand = "Can-Am"
                elif brand == "Cfmoto":
                    brand = "CFMOTO"
                elif brand == "Bsa":
                    brand = "BSA"
            
            # 4. Parse Model (extract from title after stripping brand/years)
            model = extract_model_from_title(title, brand)
            
            # 5. Parse Seller Type (private vs company/dealer)
            seller_type = "private"
            if "företag" in card_text_spaced.lower() or "butik" in card_text_spaced.lower() or "besök" in card_text_spaced.lower():
                seller_type = "company"
                
            # 6. Parse Location and Dealer Name
            location = "Stockholm"
            dealer_name = None
            
            detail_spans = card.select("div.flex.items-end span")
            if detail_spans:
                first_span = detail_spans[0].text.strip()
                if "∙" in first_span or "\u2219" in first_span:
                    parts = [x.strip() for x in re.split(r'[∙\u2219]', first_span) if x.strip()]
                    if len(parts) >= 2:
                        location = parts[0]
                        dealer_name = parts[1]
                    elif len(parts) == 1:
                        location = parts[0]
                else:
                    location = first_span
            
            listings.append(BlocketItem(
                id=item_id,
                title=title,
                price=price_numeric,
                url=url,
                location=location,
                published_at=datetime.now().isoformat(),
                image_url=None,
                seller_type=seller_type,
                dealer_name=dealer_name,
                like_count=0,
                brand=brand,
                model=model,
                model_year=model_year,
                mileage_km=mileage_km,
                engine_cc=engine_cc,
                gearbox=gearbox,
                fuel_type=fuel_type
            ))
        except Exception as e:
            continue
            
    return listings
