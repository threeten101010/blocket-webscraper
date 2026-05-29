#!/usr/bin/env python3
import sys
import os
from bs4 import BeautifulSoup

# Add parent path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import fetch_page_playwright

def test():
    url = "https://www.blocket.se/annonser/hela_sverige/fordon/motorcyklar?p=1"
    print("Fetching page using Playwright...")
    html = fetch_page_playwright(url)
    
    if not html:
        print("Error: Empty HTML returned!")
        return
        
    print(f"Success! HTML length: {len(html)}")
    
    # Save a sample of the HTML
    with open("data/test_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved HTML to data/test_page.html")
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Check for __NEXT_DATA__
    next_data = soup.find("script", id="__NEXT_DATA__")
    print(f"__NEXT_DATA__ script tag present? {next_data is not None}")
    if next_data:
        print(f"__NEXT_DATA__ length: {len(next_data.string)}")
        
    # Check for articles
    articles = soup.select("article")
    print(f"Number of <article> elements: {len(articles)}")
    
    # Check for any links containing /annons/
    links = [a.get("href") for a in soup.find_all("a", href=True) if "/annons/" in a.get("href")]
    print(f"Number of /annons/ links: {len(links)}")
    if links:
        print(f"Sample links: {links[:3]}")

if __name__ == "__main__":
    test()
