#!/usr/bin/env bash
# Post-deploy setup — runs inside the sandbox.
# Uploaded and executed by deploy.sh
set -e

# Ensure venv exists with correct Python
if [ ! -f /sandbox/.venv/bin/python3 ]; then
  echo "Creating venv..."
  python3 -m venv /sandbox/.venv 2>/dev/null || /usr/bin/python3 -m venv /sandbox/.venv
fi

# Install deps using venv pip (binary matches network policy)
echo "Installing Python dependencies..."
/sandbox/.venv/bin/pip install -q -r /sandbox/workspace/requirements.txt 2>/dev/null || true

# Ensure start + log scripts are executable
chmod +x /sandbox/workspace/start /sandbox/log 2>/dev/null || true
ln -sf /sandbox/workspace/start ~/start

# Ensure PATH includes home dir for `start` command
grep -q 'PATH=.*HOME' ~/.bashrc 2>/dev/null || echo 'export PATH="$HOME:$PATH"' >> ~/.bashrc

# Log which Python binary the policy needs to allow
REAL_PY=$(readlink -f /sandbox/.venv/bin/python3)
echo "  Python binary: $REAL_PY"
echo "  Policy must allow: /sandbox/.uv/python/** or the exact path above"
echo "Setup complete."
