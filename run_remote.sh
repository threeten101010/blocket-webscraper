#!/usr/bin/env bash
# ==============================================================================
# Blocket Scraper Remote Pipeline Runner
# This script automates synchronizing your code to your remote Head Node,
# executing the scrape remotely, and downloading the database results.
# ==============================================================================

set -e

# Target host configuratons (uses your pre-configured Tailscale SSH alias)
REMOTE_HOST="101010_remote"
REMOTE_DIR="~/blocket-webscraper"

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🌌 [Command Center] Initializing Remote Execution Pipeline..."
echo "📍 Local directory:  $LOCAL_DIR"
echo "📡 Remote host:      $REMOTE_HOST"

# Step 1: Synchronize codebase to the remote host (ignoring local databases & virtualenvs)
echo -e "\n📥 [1/4] Synchronizing files to remote server over Tailscale..."
rsync -avz --delete \
    --exclude="venv/" \
    --exclude=".venv/" \
    --exclude="data/" \
    --exclude=".playwright-browsers/" \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude="*.db" \
    --exclude="*.duckdb" \
    --exclude="*.sqlite" \
    --exclude="*.log" \
    "$LOCAL_DIR/" "$REMOTE_HOST:$REMOTE_DIR/"

# Step 2: Run environment initialization and execute scraper remotely via SSH
echo -e "\n⚙️ [2/4] Initializing environment and triggering scraper remotely..."
ssh "$REMOTE_HOST" bash << 'EOF'
    set -e
    cd ~/blocket-webscraper
    
    # Create data directory if missing
    mkdir -p data
    
    # Initialize virtual environment if missing
    if [ ! -d "venv" ]; then
        echo "🐍 Creating virtual environment on remote host..."
        python3 -m venv venv
    fi
    
    # Activate virtualenv and update dependencies
    source venv/bin/activate
    echo "📦 Checking and installing remote dependencies..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    
    # Run the scraping process
    echo "🚀 Triggering primary Blocket scraper with Playwright browser..."
    export PLAYWRIGHT_BROWSERS_PATH=~/blocket-webscraper/.playwright-browsers
    python3 main.py --browser
EOF

# Step 3: Fetch the database results back from the remote server
echo -e "\n📥 [3/4] Downloading updated database results from remote server..."
mkdir -p "$LOCAL_DIR/data"
scp "$REMOTE_HOST:$REMOTE_DIR/data/scraped_listings.duckdb" "$LOCAL_DIR/data/scraped_listings.duckdb"

# Step 4: Verification
echo -e "\n🏁 [4/4] Pipeline Complete!"
echo "💾 Database downloaded to: projects/blocket-webscraper/data/scraped_listings.duckdb"
echo "📊 Run sqlite3/duckdb queries locally to inspect the scraped classifieds."
