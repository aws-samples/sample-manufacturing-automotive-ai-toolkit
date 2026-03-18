#!/usr/bin/env bash
# SFC Launch Package — run.sh (Linux)
# One-click launcher: checks Java & uv, installs if missing, then runs the agent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CORRETTO_URL="https://corretto.aws/downloads/latest/amazon-corretto-21-x64-linux-jdk.tar.gz"
JAVA_LOCAL_DIR="$SCRIPT_DIR/.java"

# ── helpers ──────────────────────────────────────────────────────────────────
ask() {
    read -r -p "$1 [Y/n] " ans
    case "$ans" in
        [nN]*) return 1 ;;
        *)     return 0 ;;
    esac
}

# ── 1. Java check ─────────────────────────────────────────────────────────────
if ! command -v java &>/dev/null; then
    echo ""
    echo "⚠️  Java not found."
    echo "   Amazon Corretto 21 will be downloaded and extracted locally"
    echo "   into: $JAVA_LOCAL_DIR  (no system-wide changes)"
    echo ""
    if ask "Install Amazon Corretto 21 now?"; then
        mkdir -p "$JAVA_LOCAL_DIR"
        TMP_TAR="$JAVA_LOCAL_DIR/corretto21.tar.gz"
        echo "→ Downloading Corretto 21 …"
        curl -fsSL "$CORRETTO_URL" -o "$TMP_TAR"
        echo "→ Extracting …"
        tar -xzf "$TMP_TAR" -C "$JAVA_LOCAL_DIR" --strip-components=1
        rm -f "$TMP_TAR"
        export JAVA_HOME="$JAVA_LOCAL_DIR"
        export PATH="$JAVA_HOME/bin:$PATH"
        echo "✅ Corretto 21 installed at $JAVA_LOCAL_DIR"
    else
        echo "❌ Java is required. Aborting."
        exit 1
    fi
else
    echo "✅ Java found: $(java -version 2>&1 | head -1)"
fi

# ── 2. uv check ──────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo ""
    echo "⚠️  uv (Python package manager) not found."
    echo ""
    if ask "Install uv now?"; then
        echo "→ Installing uv …"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Source the cargo/uv env if the installer added it
        if [ -f "$HOME/.cargo/env" ]; then
            # shellcheck source=/dev/null
            source "$HOME/.cargo/env"
        fi
        # Also try the uv-managed path
        export PATH="$HOME/.local/bin:$PATH"
        if ! command -v uv &>/dev/null; then
            echo "⚠️  uv installed but not yet on PATH."
            echo "   Please open a new terminal and re-run this script."
            exit 1
        fi
        echo "✅ uv installed: $(uv --version)"
    else
        echo "❌ uv is required. Aborting."
        exit 1
    fi
else
    echo "✅ uv found: $(uv --version)"
fi

# ── 3. Run the agent ─────────────────────────────────────────────────────────
echo ""
echo "💡 Starting SFC runner …"
echo ""
cd "$SCRIPT_DIR/runner"
uv run runner.py
