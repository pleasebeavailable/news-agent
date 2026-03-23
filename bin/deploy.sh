#!/usr/bin/env bash
# Deploy Phase 2 code to the rich-biatch sandbox.
# Usage:  bash ~/openclaw-agent/bin/deploy.sh

set -euo pipefail

# Always run from project root regardless of where script is invoked
cd "$(dirname "$0")/.."

# Load credentials from .env
if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example and fill in your credentials."
  exit 1
fi
set -a; source .env; set +a

SANDBOX="rich-biatch"
REMOTE="/sandbox/workspace"

# openshell sandbox upload places the file INSIDE the remote path (like cp file dir/)
# so we always target the parent directory, not the full file path.
upload() {
  local local_path="$1"   # e.g. core/llm_client.py
  local remote_dir="$2"   # e.g. /sandbox/workspace/core/
  echo "  → $remote_dir$(basename "$local_path")"
  openshell sandbox upload "$SANDBOX" "$local_path" "$remote_dir"
}

echo "=== Deploying to $SANDBOX ==="

# Create remote directory structure and persistent .env
echo "[1/6] Creating remote directories and .env..."
printf "mkdir -p /sandbox/workspace/core /sandbox/workspace/skills /sandbox/workspace/config /sandbox/workspace/prompts /sandbox/workspace/data\n\
if [ ! -s /sandbox/.openclaw-data/.env ]; then\n\
  echo 'TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}' > /sandbox/.openclaw-data/.env\n\
  echo 'TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}' >> /sandbox/.openclaw-data/.env\n\
  echo 'NVIDIA_API_KEY=${NVIDIA_API_KEY}' >> /sandbox/.openclaw-data/.env\n\
  echo 'no_proxy=127.0.0.1,localhost,::1' >> /sandbox/.openclaw-data/.env\n\
  echo 'NO_PROXY=127.0.0.1,localhost,::1' >> /sandbox/.openclaw-data/.env\n\
  echo '  .env written to persistent storage'\n\
fi\n\
ln -sf /sandbox/.openclaw-data/.env /sandbox/workspace/.env\n\
grep -q NVIDIA_API_KEY /sandbox/.openclaw-data/.env 2>/dev/null || echo 'NVIDIA_API_KEY=${NVIDIA_API_KEY}' >> /sandbox/.openclaw-data/.env\n\
exit\n" \
  | nemoclaw "$SANDBOX" connect 2>/dev/null || true

# Core modules
echo "[2/6] Core..."
for f in core/llm_client.py core/telegram_bot.py core/stock_data.py \
          core/config_loader.py core/news_fetcher.py \
          core/news_scorer.py core/news_store.py core/__init__.py; do
  upload "$f" "$REMOTE/core/"
done

# Skills
echo "[3/6] Skills..."
for f in skills/*.py; do
  [ -f "$f" ] && upload "$f" "$REMOTE/skills/"
done

# Config
echo "[4/6] Config..."
upload "config.yaml" "$REMOTE/"
for f in config/portfolio.yaml config/theses.yaml \
          config/news_sources.yaml config/keywords.yaml; do
  [ -f "$f" ] && upload "$f" "$REMOTE/config/"
done

# Prompts
echo "[5/6] Prompts..."
for f in prompts/*.txt; do
  [ -f "$f" ] && upload "$f" "$REMOTE/prompts/"
done

# Entry point + requirements + start script
echo "[6/6] main.py + requirements.txt + start..."
upload "main.py"          "$REMOTE/"
upload "requirements.txt" "$REMOTE/"
upload "bin/start"        "$REMOTE/"

# Make start executable on the sandbox
printf 'chmod +x /sandbox/workspace/start\nexit\n' \
  | nemoclaw "$SANDBOX" connect 2>/dev/null || true

echo ""
echo "=== Done ==="
echo ""
echo "On sandbox:"
echo "  bash /sandbox/workspace/start"
echo ""
echo "  tail -f /tmp/nemoclaw.log           — watch logs"
echo "  kill \$(cat /tmp/nemoclaw.lock)     — stop bot"
