#!/usr/bin/env python3
"""
Unit tests for the Blocket parser engine (BS4 Fallback Parser).
"""

import sys
import os

# Add parent path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import parse_html_fallback, is_motorcycle_listing

def test_is_motorcycle_listing():
    """Verify that only motorcycle listings pass the parser filter."""
    assert is_motorcycle_listing("Yamaha MT-07 2021", "https://www.blocket.se/item/123") == True
    assert is_motorcycle_listing("KTM Duke 390", "https://www.blocket.se/item/456") == True
    # Non-motorcycle posts (e.g. cars or unrelated gear) should return False if keywords match
    assert is_motorcycle_listing("Volvo V60 D4", "https://www.blocket.se/item/789") == False

def test_parse_html_fallback():
    """Validates HTML card parsing from mock classified sweeps."""
    mock_html = """
    <html>
        <body>
            <article>
                <a href="https://www.blocket.se/mobility/item/23456789">
                    <h2>Yamaha MT-07</h2>
                </a>
                <span>2021 ∙ 1 200 mil ∙ Bensin ∙ Manuell ∙ 690cc</span>
                <span>69 900 kr</span>
            </article>
            <article>
                <a href="https://www.blocket.se/mobility/item/98765432">
                    <h2>KTM 300 EXC</h2>
                </a>
                <span>2023 ∙ 450 mil ∙ Bensin ∙ Manuell ∙ 300cc</span>
                <span>82 500 kr</span>
            </article>
        </body>
    </html>
    """
    
    items = parse_html_fallback(mock_html)
    
    assert len(items) == 2
    
    # 1. Yamaha MT-07 Assertions
    y_item = items[0]
    assert y_item.id == "23456789"
    assert y_item.title == "Yamaha MT-07"
    assert y_item.price == 69900
    assert y_item.model_year == 2021
    assert y_item.mileage_km == 12000
    assert y_item.engine_cc == 690

    # 2. KTM 300 EXC Assertions
    k_item = items[1]
    assert k_item.id == "98765432"
    assert k_item.title == "KTM 300 EXC"
    assert k_item.price == 82500
    assert k_item.model_year == 2023
    assert k_item.mileage_km == 4500
    assert k_item.engine_cc == 300

if __name__ == "__main__":
    try:
        import pytest
        pytest.main([__file__])
    except ImportError:
        print("⚠️ 'pytest' not found. Running self-contained test execution...")
        try:
            test_is_motorcycle_listing()
            test_parse_html_fallback()
            print("🔬 --- test_parser.py: All assertions passed successfully! ---")
        except AssertionError as e:
            print(f"❌ test_parser.py: Test failed with AssertionError: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ test_parser.py: Test failed with error: {e}")
            sys.exit(1)
