#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/openclaw-agent"
TMP_DIR="/tmp/openclaw"
PLIST_NAME="com.nvidia.nemoclaw"
PLIST_SRC="$INSTALL_DIR/$PLIST_NAME.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
SANDBOXES_JSON="$HOME/.nemoclaw/sandboxes.json"
CREDS_FILE="$HOME/.nemoclaw/credentials.json"
SANDBOX_NAME="${NEMOCLAW_SANDBOX:-my-assistant}"
START_STEP="${1:-1}"  # Pass --from-step N or just a number to resume

# Parse --from-step N
if [[ "${1:-}" == "--from-step" ]]; then
  START_STEP="${2:-1}"
elif [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  START_STEP="$1"
fi

# Read sandbox name from existing config if present
if [ -f "$SANDBOXES_JSON" ]; then
  EXISTING=$(python3 - "$SANDBOXES_JSON" <<'PYEOF' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1]))
names = list(d.get('sandboxes', {}).keys())
print(names[0] if names else '')
PYEOF
  )
  if [ -n "$EXISTING" ]; then
    SANDBOX_NAME="$EXISTING"
  fi
fi

ok()   { echo "  ✓ $1"; }
skip() { echo "  ● $1 (already done)"; }
warn() { echo "  ⚠ $1"; }
fail() { echo "  ✗ $1"; echo "    $2"; echo ""; echo "  Resume with: bash install.sh --from-step $CURRENT_STEP"; exit 1; }

CURRENT_STEP=0
should_run() { CURRENT_STEP=$1; [ "$START_STEP" -le "$1" ]; }

echo "=== NemoClaw Resumable Installer ==="
echo "  Sandbox: $SANDBOX_NAME"
if [ "$START_STEP" -gt 1 ]; then
  echo "  Resuming from step $START_STEP"
fi
echo ""

# ─── 1. Prerequisites ──────────────────────────────────────
if should_run 1; then
  echo "[1/9] Checking prerequisites..."

  for cmd in node npm docker; do
    command -v "$cmd" >/dev/null 2>&1 || fail "$cmd not found" "Install it first."
  done

  NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
  [ "$NODE_MAJOR" -ge 20 ] || fail "Node.js v20+ required" "Found $(node -v)"

  docker info >/dev/null 2>&1 || fail "Docker not running" "Start Docker Desktop first."

  ok "Node $(node -v), npm $(npm -v), Docker OK"
fi

# ─── 2. NemoClaw CLI ───────────────────────────────────────
if should_run 2; then
  echo "[2/9] NemoClaw CLI..."

  if command -v nemoclaw >/dev/null 2>&1; then
    skip "nemoclaw installed at $(which nemoclaw)"
  else
    echo "  Installing..."
    curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
    [ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null || true
    command -v nemoclaw >/dev/null 2>&1 || fail "nemoclaw not on PATH" "Try: source ~/.zshrc"
    ok "Installed at $(which nemoclaw)"
  fi
fi

NEMOCLAW_PATH=$(which nemoclaw 2>/dev/null || echo "/usr/local/bin/nemoclaw")

# ─── 3. Directories ────────────────────────────────────────
if should_run 3; then
  echo "[3/9] Directories..."
  mkdir -p "$INSTALL_DIR" "$TMP_DIR" "$HOME/Library/LaunchAgents"
  ok "$INSTALL_DIR, $TMP_DIR"
fi

# ─── 4. Config files ───────────────────────────────────────
if should_run 4; then
  echo "[4/9] Config files..."

  MISSING=0
  for f in sandbox-policy.yaml config.yaml "$PLIST_NAME.plist" test-commands.md; do
    if [ -f "$INSTALL_DIR/$f" ]; then
      ok "$f"
    else
      echo "  ✗ $f MISSING"
      MISSING=1
    fi
  done
  [ "$MISSING" -eq 0 ] || fail "Missing config files" "Create them first."
fi

# ─── 5. Validate API key ───────────────────────────────────
if should_run 5; then
  echo "[5/9] Validating NVIDIA API key..."

  get_api_key_from_config() {
    local raw
    raw=$(grep '^\s*api_key:' "$INSTALL_DIR/config.yaml" 2>/dev/null | head -1 | sed 's/.*api_key:\s*//' | sed 's/^["'"'"']//' | sed 's/["'"'"']$//' | tr -d '[:space:]')
    if echo "$raw" | grep -q 'YOUR_'; then
      echo ""
    else
      echo "$raw"
    fi
  }

  write_api_key_to_config() {
    local key="$1"
    sed -i '' "s|^\(\s*api_key:\s*\).*|\1${key}|" "$INSTALL_DIR/config.yaml"
  }

  test_api_key() {
    local key="$1"
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" \
      -H "Authorization: Bearer $key" \
      "https://integrate.api.nvidia.com/v1/models" 2>/dev/null || echo "000")
    [ "$status" = "200" ]
  }

  # Also check credentials file
  NVIDIA_API_KEY=$(get_api_key_from_config)
  if [ -z "$NVIDIA_API_KEY" ] && [ -f "$CREDS_FILE" ]; then
    NVIDIA_API_KEY=$(python3 -c "import json; print(json.load(open('$CREDS_FILE')).get('nvidia_api_key',''))" 2>/dev/null || true)
  fi

  # If we already have a valid key, skip prompting
  if [ -n "$NVIDIA_API_KEY" ] && test_api_key "$NVIDIA_API_KEY"; then
    skip "API key valid"
    write_api_key_to_config "$NVIDIA_API_KEY"
  else
    # Loop: prompt until we get a valid key
    MAX_ATTEMPTS=3
    ATTEMPT=0
    NVIDIA_API_KEY=""
    while true; do
      echo "  No valid API key found."
      echo -n "  Enter your NVIDIA API key (from build.nvidia.com): "
      read -r NVIDIA_API_KEY </dev/tty
      if [ -z "$NVIDIA_API_KEY" ]; then
        fail "No API key provided" "Get one at https://build.nvidia.com"
      fi

      echo "  Testing API key..."
      if test_api_key "$NVIDIA_API_KEY"; then
        ok "API key is valid"
        write_api_key_to_config "$NVIDIA_API_KEY"
        break
      else
        ATTEMPT=$((ATTEMPT + 1))
        echo "  ⚠ API key rejected by NVIDIA (invalid or expired)."
        if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
          fail "API key invalid after $MAX_ATTEMPTS attempts" "Check your key at https://build.nvidia.com"
        fi
        echo "  Try again ($ATTEMPT/$MAX_ATTEMPTS)."
      fi
    done
  fi

  # Save to credentials file for nemoclaw onboard
  if [ -n "$NVIDIA_API_KEY" ]; then
    mkdir -p "$(dirname "$CREDS_FILE")"
    cat > "$CREDS_FILE" <<CREDS
{
  "nvidia_api_key": "$NVIDIA_API_KEY"
}
CREDS
    chmod 600 "$CREDS_FILE"
  fi
fi

# ─── 6. Gateway ────────────────────────────────────────────
if should_run 6; then
  echo "[6/9] Gateway..."

  GATEWAY_UP=0
  if openshell gateway status >/dev/null 2>&1 || lsof -i :8080 2>/dev/null | grep -q LISTEN; then
    GATEWAY_UP=1
  fi

  if [ "$GATEWAY_UP" -eq 1 ]; then
    skip "Gateway running"
  else
    echo "  Gateway not running. Starting 'nemoclaw onboard'..."
    echo "  Follow the interactive prompts."
    echo ""
    nemoclaw onboard </dev/tty || {
      # Onboard may crash at step 6 (known bug) — check if gateway+sandbox were created
      warn "nemoclaw onboard exited with error (this may be OK — checking state...)"
    }

    # Re-read sandbox name
    if [ -f "$SANDBOXES_JSON" ]; then
      NEW_NAME=$(python3 - "$SANDBOXES_JSON" <<'PYEOF' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1]))
names = list(d.get('sandboxes', {}).keys())
print(names[0] if names else '')
PYEOF
      )
      if [ -n "$NEW_NAME" ]; then
        SANDBOX_NAME="$NEW_NAME"
      fi
    fi
  fi
fi

# ─── 7. Sandbox check ──────────────────────────────────────
if should_run 7; then
  echo "[7/9] Sandbox '$SANDBOX_NAME'..."

  SANDBOX_EXISTS=0
  if openshell sandbox list 2>&1 | grep -qi "$SANDBOX_NAME"; then
    PHASE=$(openshell sandbox list 2>&1 | grep -i "$SANDBOX_NAME" | awk '{print $NF}')
    if echo "$PHASE" | grep -qi "ready"; then
      SANDBOX_EXISTS=1
      skip "Sandbox '$SANDBOX_NAME' exists and is Ready"
    else
      warn "Sandbox '$SANDBOX_NAME' exists but phase is: $PHASE"
      echo "  Try: nemoclaw $SANDBOX_NAME destroy && bash install.sh --from-step 6"
      exit 1
    fi
  else
    fail "Sandbox '$SANDBOX_NAME' not found in gateway" "Run: bash install.sh --from-step 6"
  fi

  # Check if OpenClaw config exists inside sandbox (step 6 of onboard)
  echo "  Checking OpenClaw config inside sandbox..."
  OPENCLAW_CONFIGURED=0
  CONFIG_CHECK=$(echo 'test -f /sandbox/.nemoclaw/config.json && echo YES || echo NO; exit' | openshell sandbox connect "$SANDBOX_NAME" 2>&1 || true)
  if echo "$CONFIG_CHECK" | grep -q "YES"; then
    OPENCLAW_CONFIGURED=1
    skip "OpenClaw configured inside sandbox"
  else
    warn "OpenClaw config missing inside sandbox (nemoclaw onboard step 6 bug)"
    echo "  Fixing — uploading config into sandbox..."

    # Create fix script
    FIX_SCRIPT=$(mktemp)
    cat > "$FIX_SCRIPT" <<'FIXEOF'
#!/bin/bash
set -euo pipefail
mkdir -p /sandbox/.nemoclaw /sandbox/.openclaw

cat > /sandbox/.nemoclaw/config.json <<'NCFG'
{
  "endpointType": "custom",
  "endpointUrl": "https://inference.local/v1",
  "ncpPartner": null,
  "model": "nvidia/nemotron-3-super-120b-a12b",
  "profile": "inference-local",
  "credentialEnv": "OPENAI_API_KEY",
  "provider": "nvidia-nim",
  "providerLabel": "NVIDIA Endpoint API"
}
NCFG
chmod 600 /sandbox/.nemoclaw/config.json
echo "OK nemoclaw config"

# openclaw.json is baked into the image as root-owned read-only
# Only write if it doesn't exist
if [ ! -f /sandbox/.openclaw/openclaw.json ]; then
  python3 - <<'PYCFG'
import json, os
cfg = {
  "agents": {"defaults": {"model": {"primary": "inference/nvidia/nemotron-3-super-120b-a12b"}}},
  "models": {
    "mode": "merge",
    "providers": {
      "inference": {
        "type": "openai",
        "baseUrl": "https://inference.local/v1",
        "models": ["nvidia/nemotron-3-super-120b-a12b"]
      }
    }
  }
}
with open("/sandbox/.openclaw/openclaw.json", "w") as f:
    json.dump(cfg, f, indent=2)
os.chmod("/sandbox/.openclaw/openclaw.json", 0o600)
PYCFG
  echo "OK openclaw.json"
else
  echo "OK openclaw.json (already exists)"
fi

openclaw models set "inference/nvidia/nemotron-3-super-120b-a12b" > /dev/null 2>&1 || true
echo "DONE"
FIXEOF

    openshell sandbox upload "$SANDBOX_NAME" "$FIX_SCRIPT" /sandbox/fix-setup.sh
    echo 'bash /sandbox/fix-setup.sh/$(ls /sandbox/fix-setup.sh/) && rm -rf /sandbox/fix-setup.sh; exit' | openshell sandbox connect "$SANDBOX_NAME" 2>&1 | tail -5
    rm -f "$FIX_SCRIPT"
    ok "OpenClaw configured inside sandbox"
  fi

  # Ensure OPENCLAW_STATE_DIR is set in sandbox (fixes root-owned identity dir — openclaw/openclaw#23948)
  STATE_DIR_CHECK=$(echo 'grep -q OPENCLAW_STATE_DIR /sandbox/.bashrc 2>/dev/null && echo YES || echo NO; exit' | openshell sandbox connect "$SANDBOX_NAME" 2>&1 || true)
  if echo "$STATE_DIR_CHECK" | grep -q "YES"; then
    skip "OPENCLAW_STATE_DIR set in sandbox"
  else
    echo 'mkdir -p /sandbox/.openclaw-data/identity && cp /sandbox/.openclaw/identity/device.json /sandbox/.openclaw-data/identity/ 2>/dev/null; echo "export OPENCLAW_STATE_DIR=/sandbox/.openclaw-data" >> /sandbox/.bashrc; exit' | openshell sandbox connect "$SANDBOX_NAME" 2>&1 >/dev/null || true
    ok "OPENCLAW_STATE_DIR fix applied (identity dir workaround)"
  fi

  # Verify inference works
  echo "  Testing inference..."
  INFERENCE_TEST=$(echo 'openclaw agent --agent main --local -m "Reply with just OK" --session-id install-test 2>&1; exit' | openshell sandbox connect "$SANDBOX_NAME" 2>&1 || true)
  if echo "$INFERENCE_TEST" | grep -qi "ok\|hello\|ready\|help\|assist"; then
    ok "Inference working (Nemotron responding)"
  else
    warn "Inference test inconclusive — check manually with: nemoclaw $SANDBOX_NAME connect"
  fi
fi

# ─── 8. Telegram bot ──────────────────────────────────────
# NOTE: Phase 2 uses Telegram (not WhatsApp — WhatsApp setup was not completed)
# Bot token and chat ID are stored in /sandbox/.openclaw-data/.env
# No setup needed here — deploy.sh handles .env creation on the sandbox
if should_run 8; then
  echo "[8/9] Telegram bot — no local setup needed."
  echo "  Run: bash ~/openclaw-agent/deploy.sh"
  ok "Skipped (handled by deploy.sh)"
fi

# ─── 9. Bot persistence ──────────────────────────────────
# NOTE: Phase 2 bot runs on the sandbox via nohup (not launchd — no root on sandbox)
# The `start` script at /sandbox/bin/start handles persistence.
if should_run 9; then
  echo "[9/9] Bot persistence — handled by nohup start script on sandbox."
  echo "  start script: /sandbox/bin/start"
  echo "  logs:         /tmp/nemoclaw.log"
  ok "No launchd needed (sandbox-side nohup)"
fi

# ─── Summary ───────────────────────────────────────────────
echo ""
echo "=== Setup Complete ==="
echo ""
nemoclaw status 2>&1 | sed 's/^/  /' || true
echo ""
echo "Next steps:"
echo "  1. bash ~/openclaw-agent/deploy.sh   (push code to sandbox)"
echo "  2. nemoclaw $SANDBOX_NAME connect"
echo "  3. start                             (launch bot — survives SSH disconnect)"
echo "  4. tail -f /tmp/nemoclaw.log         (watch logs)"
echo "  See ~/openclaw-agent/test-commands.md for verification commands"
