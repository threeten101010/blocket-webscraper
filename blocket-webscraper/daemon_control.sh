#!/usr/bin/env bash
# ==============================================================================
# Blocket Continuous Scraper Daemon Controller
# This script manages starting, stopping, and auditing your continuous background
# scraper service on your remote Head Node (101010_0001) over Tailscale.
# ==============================================================================

set -e

REMOTE_HOST="101010_remote"
REMOTE_DIR="~/blocket-webscraper"

usage() {
    echo "Usage: $0 {start|stop|status|logs}"
    echo "  start  : Launch the continuous scraper in the background on the remote server"
    echo "  stop   : Safely terminate the running remote background scraper process"
    echo "  status : Check if the remote scraper daemon is active"
    echo "  logs   : Tail the remote log file to watch execution in real-time"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

ACTION=$1

# Define get_scraper_pid as a bash snippet that can be evaluated on the remote server
GET_PID_COMMAND='
get_scraper_pid() {
    pgrep -f "main.py" | while read -r pid; do
        comm=$(ps -p "$pid" -o comm= 2>/dev/null || true)
        if [ "$comm" = "python3" ] || [ "$comm" = "python" ]; then
            if ps -p "$pid" -o command= | grep -q "main.py" && ps -p "$pid" -o command= | grep -q -- "--continuous"; then
                echo "$pid"
                return 0
            fi
        fi
    done
    return 1
}
'

case "$ACTION" in
    start)
        echo "🚀 Synchronizing local code changes to remote node..."
        LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

        echo -e "\n📡 Dispatching continuous background daemon to remote host..."
        ssh "$REMOTE_HOST" bash << EOF
            $GET_PID_COMMAND
            
            cd ~/blocket-webscraper
            mkdir -p data
            
            # Check if already running
            PID=\$(get_scraper_pid || true)
            if [ -n "\$PID" ]; then
                echo "⚠️ Warning: Scraper daemon is already running remotely (PID: \$PID)."
                exit 0
            fi
            
            # Activate environment and launch nohup background daemon
            source venv/bin/activate
            export PLAYWRIGHT_BROWSERS_PATH=~/blocket-webscraper/.playwright-browsers
            
            echo "⚙️ Triggering nohup daemon process (unbuffered output)..."
            # Runs continuously in background, sleeping 15 minutes between page 1 restarts
            nohup python3 -u main.py --browser --continuous --cooldown 15 >> data/scraper.log 2>&1 &
            
            sleep 3
            PID=\$(get_scraper_pid || true)
            if [ -n "\$PID" ]; then
                echo "✅ Success: Remote background daemon is running! (PID: \$PID)"
                echo "📝 Logs are writing to: ~/blocket-webscraper/data/scraper.log"
            else
                echo "❌ Error: Failed to start remote background daemon. Check server error logs."
            fi
EOF
        ;;
        
    stop)
        echo "🛑 Requesting safe termination of remote scraper process..."
        ssh "$REMOTE_HOST" bash << EOF
            $GET_PID_COMMAND
            
            PID=\$(get_scraper_pid || true)
            if [ -n "\$PID" ]; then
                echo "⚙️ Terminating scraper process PID: \$PID..."
                kill -15 \$PID
                sleep 2
                PID_CHECK=\$(get_scraper_pid || true)
                if [ -n "\$PID_CHECK" ]; then
                    echo "⚠️ Process did not exit. Forcing shutdown (SIGKILL)..."
                    kill -9 \$PID
                fi
                echo "✅ Success: Remote background scraper stopped."
            else
                echo "ℹ️ Info: No active background scraper processes were found."
            fi
EOF
        ;;
        
    status)
        echo "🧐 Checking remote daemon status..."
        ssh "$REMOTE_HOST" bash << EOF
            $GET_PID_COMMAND
            
            PID=\$(get_scraper_pid || true)
            if [ -n "\$PID" ]; then
                echo "🟢 Active: Scraper daemon is RUNNING (PID: \$PID)"
                echo "📈 Uptime info:"
                ps -p \$PID -o pid,ppid,%cpu,%mem,etime,command
            else
                echo "🔴 Idle: Scraper daemon is STOPPED"
            fi
EOF
        ;;
        
    logs)
        echo "📝 Tailing remote scraper logs in real-time (Press Ctrl+C to exit)..."
        ssh "$REMOTE_HOST" "tail -f ~/blocket-webscraper/data/scraper.log"
        ;;
        
    *)
        usage
        ;;
esac
