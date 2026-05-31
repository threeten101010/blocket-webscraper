# 🇸🇪 Blocket Motorcycle Scraper - AI Development Summary
## 💡 Executive Summary

This document serves as an exhaustive developmental record and post-mortem summary of the **Blocket Motorcycle Scraper** build. It logs the step-by-step engineering progression, structural corrections, diagnostic errors caught by AI, human interventions, and documentation methods.

The objective of this project was to establish a highly automated, remote-running classifieds crawler and DuckDB analytics pipeline to parse, track, and appraise Sweden’s motorcycle market securely over Tailscale.

---

## 🛠️ Step-by-Step Build Progression

The development of the first project proceeded in several distinct phases:

### Phase 1: Repository Restructuring & Git Flattening
* **Objective**: Remove redundant nesting (`blocket-webscraper/blocket-webscraper/`) to establish a clean root-level directory layout in Git.
* **Result**: Relocated the `.git` metadata and consolidated files into `/home/aaronberman/Gemini/threeten101010/blocket-webscraper/`, pushing clean updates to GitHub. Local keys were secured in `.gitignore`.

### Phase 2: Solving the Pagination Parameter Bug
* **Objective**: Fix the scraper daemon, which was stuck in an infinite pagination loop.
* **Diagnostic**: Discovered that Blocket's modern mobility portal ignores the legacy page parameter `p` and defaults to Page 1.
* **Correction**: Changed the pagination argument to `page={page}` in `main.py`. Added duplicate detection to halt crawling dynamically when page responses yield no new items.

### Phase 3: Active Status Database Migration
* **Objective**: Expand the DuckDB schema to support active vs. deactivated (sold) tracking.
* **Actions**: Added a binary flag `is_active BOOLEAN DEFAULT TRUE` to the main registry. Updated the crawler’s post-sweep deactivation scanner to flag listings missing from a complete category crawl as `is_active = FALSE`. Recreated the `listings_analytics` premium database view to expose this flag.

### Phase 4: Model Context Protocol (MCP) Integration
* **Objective**: Enable the local AI assistant to query the remote database securely and concurrently over SSH.
* **Engineered Solution**: Built a custom Python FastMCP server (`mcps/blocket-mcp/`). To prevent SQLite/DuckDB write-lock contention while the remote daemon runs continuously, the MCP runner executes a Python script that makes a temporary copy of the database to `/tmp`, queries it, returns standard JSON data, and clears the temp file.

### Phase 5: Dynamic Skills YAML Registry
* **Objective**: Expose the scraper capabilities to the workspace discoverability systems.
* **Actions**: Created [skills/blocket_scraper.py](file:///home/aaronberman/Gemini/skills/blocket_scraper.py) and registered it under `skills/_registry.yaml` so any future AI session immediately binds to the query tools.

### Phase 6: Compound Type and Price Range Sharding
* **Objective**: Circumvent Blocket's hard pagination limit which cuts crawls off at ~2,700 listings.
* **Engineered Solution**: Performed dynamic Playwright browser-automation sweeps on the remote server to extract the internal type parameter IDs. Sharded the crawler config into 20 distinct categories, sub-sharding the massive **Touring** and **Custom** groups into price brackets to guarantee 100% catalog coverage of the 16,489 active listings.

---

## 🛠️ Corrections & Interventions (Human Input)

Key structural adjustments made during pair programming:
1. **Repository Layout Alignment**: Resolving path conflicts to ensure the development sandbox directory (`/projects/`) and production release directory (`/threeten101010/`) were mapped correctly in Git.
2. **Git Directory Write Protections**: Establishing a strict warning directive inside the master workspace `README.md` to protect `/threeten101010/` (main branch) from direct filesystem edits, mandating that all active editing happen inside `/projects/` (dev branch) and sync via standard Git pushes/pulls.
3. **Type-Based Sharding Strategy**: Identifying that sharding by vehicle type (Custom, Touring, Sport) is highly robust and more intuitive than county-based (region) sharding.

---

## 🔍 Errors & Anomalies Caught by AI Diagnostics

Critical bugs identified and resolved through AI sweeps and logs checks:

### 1. The Greedy Price-Regex Concatenation Bug
* **Finding**: diagnostic queries showed average prices for brands like Yamaha to be in the millions, with some individual listings priced over 2 billion SEK.
* **Cause**: On the classified cards list, raw text strings like `Yamaha WR 250F 2025 ... 113 900 kr` had the model year directly preceding the price. The scraper's BS4 price regex `\d[\d\s]*\s*kr` greedily matched the space, extracting `2025113900` instead of `113900`.
* **Fix**: Restricting the price match boundaries in the HTML parser logic.

### 2. Deep Pagination Cap Detection
* **Finding**: Broad crawls were consistently terminating on page ~53, saving only ~3,000 listings.
* **Cause**: Inspecting `/data/scraper.log` on the remote server revealed the duplicate wrap-around detector repeatedly triggered around page 53. Search engines cap search result listings at ~2,700 to protect server resources.
* **Fix**: Implemented the compound type and price sharding scheme.

### 3. Remote Shell SSH Quote Escaping
* **Finding**: Sending complex query scripts over SSH using python's `-c` argument triggered syntax quote escaping errors on SQL strings.
* **Fix**: Configured the remote runner to pass the multi-line Python code block cleanly into the remote `python3` process via `stdin`.

### 4. Playwright Cookie consent Iframe & Visibility Block
* **Finding**: The Playwright automated filter extractor was timed out when clicking the `Typ` filter dropdown.
* **Cause**: The cookie consent modal popped up inside a secure iframe (`#sp_message_iframe_1427784`), intercepting all pointer events. Furthermore, Blocket hides checkbox filter labels (`display: none`) from visual layout.
* **Fix**: Navigated into the iframe dynamically to click accept, and executed a native JavaScript click (`node.click()`) evaluated in the browser context to bypass visibility checks on the hidden labels.

---

## 📚 Documentation Methods

High-fidelity documentation was maintained to ensure maximum codebase transparency:
1. **Interactive Blueprints**: Created exhaustive technical plans (e.g. `analytics_web_blueprint.md`) as standard files and workspace artifacts.
2. **Visual Flowcharts**: Integrated custom visual components inside the markdown instructions to ease development onboarding:
   * **Architectural Stack Visualization**: Renders the Next.js React client, Recharts rendering, and FastAPI backend structure.
   * **Sequence Execution Flow**: Sequence diagram illustrating page-by-page sharded crawlers, duplicate checks, JIT details, and DB removal sweeps.
3. **Structured Alerting Strategic Guides**: Leveraged Strategic alerting callouts (`[!IMPORTANT]`, `[!WARNING]`, `[!TIP]`) to declare initialization guidelines and safety boundaries clearly.
