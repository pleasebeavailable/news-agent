#!/usr/bin/env bash
# Deploy Phase 2 code to sandbox.
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

SANDBOX="${NEMOCLAW_SANDBOX:-my-sandbox}"
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

# Build sandbox .env from local .env + proxy vars
echo "[1/7] Preparing .env for sandbox..."
SANDBOX_ENV=$(mktemp)
cp .env "$SANDBOX_ENV"
grep -q '^no_proxy=' "$SANDBOX_ENV" || echo 'no_proxy=127.0.0.1,localhost,::1' >> "$SANDBOX_ENV"
grep -q '^NO_PROXY=' "$SANDBOX_ENV" || echo 'NO_PROXY=127.0.0.1,localhost,::1' >> "$SANDBOX_ENV"

# Create remote directories + upload .env
echo "[2/7] Creating remote directories and .env..."
SETUP_DIRS=$(mktemp)
cat > "$SETUP_DIRS" << 'DIREOF'
#!/bin/bash
mkdir -p /sandbox/workspace/core /sandbox/workspace/skills /sandbox/workspace/config /sandbox/workspace/prompts /sandbox/workspace/data /sandbox/.openclaw-data
DIREOF
SETUP_DIRS_BASE=$(basename "$SETUP_DIRS")
openshell sandbox upload "$SANDBOX" "$SETUP_DIRS" /tmp/
echo "bash /tmp/${SETUP_DIRS_BASE}; rm -f /tmp/${SETUP_DIRS_BASE}; exit" | nemoclaw "$SANDBOX" connect 2>/dev/null || true
rm -f "$SETUP_DIRS"

upload "$SANDBOX_ENV" /sandbox/.openclaw-data/
ENVBASE=$(basename "$SANDBOX_ENV")
echo "mv /sandbox/.openclaw-data/${ENVBASE} /sandbox/.openclaw-data/.env; ln -sf /sandbox/.openclaw-data/.env /sandbox/workspace/.env; exit" \
  | nemoclaw "$SANDBOX" connect 2>/dev/null || true
rm -f "$SANDBOX_ENV"
echo "  .env uploaded to sandbox"

# Core modules
echo "[3/7] Core..."
for f in core/llm_client.py core/telegram_bot.py core/stock_data.py \
          core/config_loader.py core/news_fetcher.py \
          core/news_scorer.py core/news_store.py core/__init__.py; do
  upload "$f" "$REMOTE/core/"
done

# Skills
echo "[4/7] Skills..."
for f in skills/*.py; do
  [ -f "$f" ] && upload "$f" "$REMOTE/skills/"
done

# Config
echo "[5/7] Config..."
upload "config.yaml" "$REMOTE/"
for f in config/portfolio.yaml config/theses.yaml \
          config/news_sources.yaml config/keywords.yaml; do
  [ -f "$f" ] && upload "$f" "$REMOTE/config/"
done

# Prompts
echo "[6/7] Prompts..."
for f in prompts/*.txt; do
  [ -f "$f" ] && upload "$f" "$REMOTE/prompts/"
done

# Entry point + requirements + start script
echo "[7/7] main.py + requirements + start + utilities + sandbox setup..."
upload "main.py"          "$REMOTE/"
upload "requirements.txt" "$REMOTE/"
upload "bin/start"        "$REMOTE/"
upload "bin/log"          "/sandbox/"

# Upload and run sandbox setup (venv, deps, start command, PATH)
upload "bin/sandbox-setup.sh" /tmp/
echo "bash /tmp/sandbox-setup.sh; rm -f /tmp/sandbox-setup.sh; exit" | nemoclaw "$SANDBOX" connect 2>/dev/null || true

# Ensure network policy is applied (idempotent)
echo ""
echo "Applying network policy..."
POLICY_FILE="$(dirname "$0")/sandbox-policy.yaml"
if [ -f "$POLICY_FILE" ]; then
  openshell policy set --policy "$POLICY_FILE" "$SANDBOX" --wait 2>&1 | grep -v '^$' || true
else
  echo "  WARNING: $POLICY_FILE not found — sandbox may block outbound traffic"
fi

echo ""
echo "=== Done ==="
echo ""
echo "  NemoClaw:"
echo "  nemoclaw $SANDBOX connect"
echo "  start                          — (re)start bot"
echo "  tail -f /tmp/nemoclaw.log      — watch logs"
echo "  kill \$(cat /tmp/nemoclaw.lock) — stop bot"
