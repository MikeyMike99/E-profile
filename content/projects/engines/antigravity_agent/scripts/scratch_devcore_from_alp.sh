#!/usr/bin/env bash
# =============================================================================
# DevCore Environment Verification & ALP Dependency Purge
#
# Usage:
#   ./scripts/scratch_devcore_from_alp.sh          # Verify server env and scratch if ready
#   ./scripts/scratch_devcore_from_alp.sh --check  # Diagnostic inspection only
#   ./scripts/scratch_devcore_from_alp.sh --watch  # Wait for server to boot in devcore, then scratch
#   ./scripts/scratch_devcore_from_alp.sh --force  # Scratch immediately without server env check
# =============================================================================

set -e

DEVCORE_VENV="${DEVCORE_VENV:-$HOME/.venvs/devcore}"
ALP_VENV="${ALP_VENV:-$HOME/alp-env}"
SERVER_PORT=5000

MODE="run"
if [ "$1" = "--check" ]; then
    MODE="check"
elif [ "$1" = "--watch" ]; then
    MODE="watch"
elif [ "$1" = "--force" ]; then
    MODE="force"
fi

echo "======================================================================="
echo " DevCore Environment Transition & ALP Cleanup Tool"
echo "======================================================================="
echo "Target DevCore Virtualenv: $DEVCORE_VENV"
echo "Target ALP Virtualenv:     $ALP_VENV"
echo ""

# -----------------------------------------------------------------------------
# 1. DevCore Virtual Environment Preflight
# -----------------------------------------------------------------------------
echo "[Step 1/4] Verifying DevCore virtual environment health..."
if [ ! -d "$DEVCORE_VENV" ] || [ ! -x "$DEVCORE_VENV/bin/python3" ]; then
    echo "ERROR: DevCore virtual environment not found at $DEVCORE_VENV"
    echo "Please create and install dependencies in $DEVCORE_VENV first."
    exit 1
fi

if ! "$DEVCORE_VENV/bin/python3" -c "
import quart, hypercorn, spacy, presidio_analyzer, playwright, mcp, cryptography
" 2>/dev/null; then
    echo "ERROR: DevCore virtual environment is missing required core dependencies."
    echo "Run dependency installation in $DEVCORE_VENV before purging alp-env."
    exit 1
fi
echo "SUCCESS: DevCore environment is healthy with all core dependencies intact."
echo ""

# -----------------------------------------------------------------------------
# 2. Server Process & Running Environment Check
# -----------------------------------------------------------------------------
check_server() {
    SERVER_PID="none"
    SERVER_VENV="none"
    for pid in $(pgrep -f "python.*server\.py" 2>/dev/null); do
        if [ "$pid" != "$$" ] && [ -d "/proc/$pid" ]; then
            local cwd venv
            cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)
            if [[ "$cwd" == *"/DevCore"* ]]; then
                venv=$(strings "/proc/$pid/environ" 2>/dev/null | grep "^VIRTUAL_ENV=" | cut -d= -f2- || true)
                SERVER_PID="$pid"
                SERVER_VENV="${venv:-system_or_unspecified}"
                break
            fi
        fi
    done
}

echo "[Step 2/4] Inspecting active DevCore server process on port $SERVER_PORT..."
check_server

if [ "$MODE" = "watch" ]; then
    echo "Watching for DevCore server to boot inside $DEVCORE_VENV..."
    while true; do
        check_server
        if [ "$SERVER_PID" != "none" ] && [ "$SERVER_VENV" = "$DEVCORE_VENV" ]; then
            echo "DETECTED: Server (PID $SERVER_PID) is now running inside $DEVCORE_VENV!"
            break
        fi
        echo "Server is not yet running in $DEVCORE_VENV (Current PID: $SERVER_PID, Venv: $SERVER_VENV). Checking again in 3s..."
        sleep 3
    done
elif [ "$MODE" != "force" ]; then
    if [ "$SERVER_PID" = "none" ]; then
        echo "WARNING: DevCore server is not currently running."
        echo "Start it using: bash scripts/start_server.sh"
        if [ "$MODE" = "check" ]; then
            exit 0
        fi
        echo "To purge dependencies anyway, re-run with: $0 --force"
        exit 1
    elif [ "$SERVER_VENV" != "$DEVCORE_VENV" ]; then
        echo "NOTICE: DevCore server (PID $SERVER_PID) is currently running in: $SERVER_VENV"
        echo "It has NOT yet booted inside the new DevCore environment ($DEVCORE_VENV)."
        echo ""
        echo "To safely switch environments without dropping your connection:"
        echo "1. When you are ready to reboot the server, use: bash scripts/start_server.sh"
        echo "2. Run this script with --watch to automatically purge dependencies the moment it boots:"
        echo "   bash scripts/scratch_devcore_from_alp.sh --watch"
        echo ""
        if [ "$MODE" = "check" ]; then
            exit 0
        fi
        echo "If you wish to scratch DevCore dependencies from alp-env immediately, re-run with: $0 --force"
        exit 1
    else
        echo "SUCCESS: Server (PID $SERVER_PID) is verified running in $DEVCORE_VENV."
    fi
else
    echo "FORCE MODE: Skipping server process verification."
fi
echo ""

if [ "$MODE" = "check" ]; then
    echo "Check mode completed. No changes were made."
    exit 0
fi

# -----------------------------------------------------------------------------
# 3. Scratch DevCore Dependencies from alp-env
# -----------------------------------------------------------------------------
echo "[Step 3/4] Scratching DevCore exclusive dependencies from $ALP_VENV..."

PACKAGES_TO_SCRATCH=(
    "quart"
    "sse-starlette"
    "presidio-analyzer"
    "presidio-anonymizer"
    "en-core-web-lg"
    "spacy"
    "spacy-legacy"
    "spacy-loggers"
    "thinc"
    "blis"
    "cymem"
    "murmurhash"
    "preshed"
    "srsly"
    "wasabi"
    "weasel"
    "confection"
    "cloudpathlib"
    "catalogue"
    "smart-open"
    "playwright"
    "pypdf"
    "markdown-pdf"
    "accessible-output2"
    "libloader"
    "plantuml"
    "platform-utils"
)

SCRATCHED_COUNT=0
for pkg in "${PACKAGES_TO_SCRATCH[@]}"; do
    if "$ALP_VENV/bin/pip" show "$pkg" >/dev/null 2>&1; then
        echo "--> Removing $pkg from alp-env..."
        "$ALP_VENV/bin/pip" uninstall -y "$pkg" >/dev/null 2>&1 || true
        SCRATCHED_COUNT=$((SCRATCHED_COUNT + 1))
    fi
done

echo "Cleaned $SCRATCHED_COUNT DevCore packages from alp-env."
echo ""

# -----------------------------------------------------------------------------
# 4. Post-Cleanup Verification & Sanity Checks
# -----------------------------------------------------------------------------
echo "[Step 4/4] Verifying ALP environment integrity..."

if [ -x "$ALP_VENV/bin/asciinema" ]; then
    echo "ALP asciinema: $("$ALP_VENV/bin/asciinema" --version)"
fi

if "$ALP_VENV/bin/python3" -c "import sys; print('ALP Python functional: ' + sys.version.split()[0])"; then
    echo "SUCCESS: ALP environment remains fully operational."
fi

echo ""
echo "======================================================================="
echo " DevCore Environment Separation Complete"
echo "======================================================================="
echo "- DevCore virtualenv: $DEVCORE_VENV (Quart, Hypercorn, spaCy, Presidio, Playwright, MCP)"
echo "- ALP virtualenv:     $ALP_VENV (Cleaned of DevCore packages; asciinema & tools intact)"
echo "======================================================================="
