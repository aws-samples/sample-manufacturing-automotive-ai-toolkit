#!/usr/bin/env bash
# SFC Launch Package — run.command (macOS)
# One-click launcher: checks Java & uv, installs if missing, then runs the agent.
# Double-click this file in Finder or run it from Terminal.
set -euo pipefail

# macOS Terminal.app opens scripts in $HOME — resolve the real script location.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

JAVA_LOCAL_DIR="$SCRIPT_DIR/.java"

# ── helpers ──────────────────────────────────────────────────────────────────
ask() {
    read -r -p "$1 [Y/n] " ans
    case "$ans" in
        [nN]*) return 1 ;;
        *)     return 0 ;;
    esac
}

# Detect architecture for the right Corretto package
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    CORRETTO_URL="https://corretto.aws/downloads/latest/amazon-corretto-21-aarch64-macos-jdk.tar.gz"
else
    CORRETTO_URL="https://corretto.aws/downloads/latest/amazon-corretto-21-x64-macos-jdk.tar.gz"
fi

# ── 1. Java check ─────────────────────────────────────────────────────────────
if ! command -v java &>/dev/null; then
    echo ""
    echo "⚠️  Java not found."
    echo "   Amazon Corretto 21 will be downloaded and extracted locally"
    echo "   into: $JAVA_LOCAL_DIR  (no system-wide changes, arch: $ARCH)"
    echo ""
    if ask "Install Amazon Corretto 21 now?"; then
        mkdir -p "$JAVA_LOCAL_DIR"
        TMP_TAR="$JAVA_LOCAL_DIR/corretto21.tar.gz"
        echo "→ Downloading Corretto 21 ($ARCH) …"
        curl -fsSL "$CORRETTO_URL" -o "$TMP_TAR"
        echo "→ Extracting …"
        # macOS Corretto tarballs contain a Contents/Home layout inside the .jdk bundle
        tar -xzf "$TMP_TAR" -C "$JAVA_LOCAL_DIR"
        rm -f "$TMP_TAR"
        # Find the actual java binary inside the extracted tree
        JAVA_BIN="$(find "$JAVA_LOCAL_DIR" -name java -type f | grep -m1 '/bin/java')"
        if [ -z "$JAVA_BIN" ]; then
            echo "❌ Could not locate java binary after extraction. Aborting."
            exit 1
        fi
        export JAVA_HOME="$(dirname "$(dirname "$JAVA_BIN")")"
        export PATH="$JAVA_HOME/bin:$PATH"
        echo "✅ Corretto 21 installed at $JAVA_HOME"
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
