# 🇸🇪 Blocket Web Scraper (Remote worker pipeline)

This project is a high-performance web scraper designed to target Sweden's largest classifieds portal, **Blocket.se**, and execute completely remotely on your head node server over your secure Tailscale mesh network!

---

## 📂 Project Architecture

```text
blocket-webscraper/
├── .gitignore                   # Ignores local DuckDB DBs, test logs, and virtual environments
├── README.md                    # Setup and execution instructions
├── requirements.txt             # Packages: requests, beautifulsoup4, playwright, pydantic, pyyaml
├── run_remote.sh                # 🚀 Pipeline Runner (syncs, runs remotely, downloads results)
├── main.py                      # Main orchestrator entry point
│
├── config/
│   └── scraper_config.yaml      # Search keywords, categories, throttles, and db settings
│
└── src/
    ├── parser.py                # Extracts Next.js __NEXT_DATA__ JSON (CSS bypass!)
    ├── scraper.py               # Handles static HTTP loads and dynamic Playwright drivers
    └── storage.py               # Handles DuckDB deduplicated storage pipelines
```

## 🔄 Execution Sequence

The sequence diagram below visualizes how the scraper handles the sharded categories list, paginates dynamically, bypasses pagination caps, performs JIT details parsing, records price changes, and triggers deactivation scans:

```mermaid
sequenceDiagram
    autonumber
    participant Main as main.py (Orchestrator)
    participant Config as scraper_config.yaml
    participant Scraper as src/scraper.py (Fetcher)
    participant Parser as src/parser.py (Parser)
    participant DB as src/storage.py (DuckDB)
    participant Blocket as Blocket.se (Search Engine)

    Main->>Config: 1. Read Target Shards & Settings
    Config-->>Main: Return 20 Type/Price Shards
    
    loop For Each Category Shard (e.g. Touring Budget, Sport)
        Note over Main: Initialize page = 1 & empty Scraped_IDs list
        loop Page-by-Page Pagination
            Main->>Scraper: 2. Request Page Content (URL, page)
            Scraper->>Blocket: 3. Fetch HTML (urllib or Playwright)
            Blocket-->>Scraper: Return HTML Webpage
            Scraper-->>Main: Return HTML String
            
            Main->>Parser: 4. Extract Items (HTML)
            Parser->>Parser: Try __NEXT_DATA__ JSON (Fallback to BS4)
            Parser-->>Main: Return List of parsed BlocketItems
            
            alt 0 items returned OR duplicate page wrap-around detected
                Note over Main: Break Pagination Loop
            else New items found
                Note over Main: Append new IDs to Scraped_IDs list
                Main->>DB: 5. save_listings(items)
                DB->>DB: Upsert blocket_listings & motorcycle_details
                DB->>DB: Record price_history changes
                DB-->>Main: Return number of items saved
                Note over Main: Sleep for politeness delay (delay_seconds)
                Note over Main: Increment page by 1
            end
        end
        Main->>DB: 6. detect_removals_sweep(Scraped_IDs)
        DB->>DB: Flag missing items as is_active = FALSE
        DB-->>Main: Sweep Complete
    end
    Note over Main: Crawl Cycle Complete, Enter Cooldown Sleep
```

---

## ⚡ Execution Models

### Model A: Direct Remote Pipeline (Recommended) 🚀
Run a single command on your Command Center:
```bash
bash run_remote.sh
```

**What this script automates:**
1. **Syncs Code**: Uses `rsync` to sync your local scraper codebase directly to your remote server (`101010_remote`), ignoring database files or virtualenvs.
2. **Prepares Host**: SSHs in, auto-creates a remote virtual environment, and resolves all pip requirements on the server.
3. **Runs Scraper**: Triggers `python3 main.py` on your remote server to run the scraper in the background (avoiding bandwidth or memory consumption on your local machine).
4. **Retrieves Data**: Downloads the updated DuckDB database `scraped_listings.duckdb` directly back to your local `data/` folder for analysis.

---

### Model B: Local Execution (Sandbox testing)
To test things locally before sending them to the server:

1. **Initialize a virtual environment & install requirements**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Trigger the run**:
   ```bash
   python3 main.py
   ```
   *(Options: `--browser` forces headless Chromium via Playwright, default is static HTTP)*
