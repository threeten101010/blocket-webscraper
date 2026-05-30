#!/usr/bin/env python3
import sys
import os
import re

# Add parent path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import clean_swedish_mileage

def test_parser_regex():
    print("🔬 --- Testing Web Scraper Regex Parsers ---")
    
    # Target simulated card text from Blocket listings
    card_text = "Yamaha MT-07 2021 | 1 250 mil | 69 900 kr | Stockholm"
    
    # 1. Test Price
    price_match = re.search(r'(\d[\d\s ]*)\s*kr', card_text)
    price = int(re.sub(r'\D', '', price_match.group(1))) if price_match else 0
    print(f"💰 Price Extracted:   {price} SEK (Expected: 69900)")
    
    # 2. Test Mileage
    mileage_match = re.search(r'(\d[\d\s ]*)\s*mil', card_text)
    mileage_km = clean_swedish_mileage(mileage_match.group(0)) if mileage_match else None
    print(f"🛣️ Mileage Extracted: {mileage_km} km (Expected: 12500)")
    
    # 3. Test Year
    model_year = None
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', card_text)
    for y in years:
        y_int = int(y)
        if 1950 <= y_int <= 2027:
            model_year = y_int
            break
    print(f"📅 Model Year:        {model_year} (Expected: 2021)")
    
    assert price == 69900, "Price parsing failed!"
    assert mileage_km == 12500, "Mileage parsing failed!"
    assert model_year == 2021, "Model year parsing failed!"
    print("✅ All Regex Parsers Validated Successfully!")

if __name__ == "__main__":
    test_parser_regex()
