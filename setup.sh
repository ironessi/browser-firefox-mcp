#!/usr/bin/env bash
# ===========================================================================
# browser-firefox-mcp — Kali Linux automated installer
# Usage: bash setup.sh [--prefix /opt] [--uv]
# ===========================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
err()   { echo -e "${RED}[✗]${RESET} $*" >&2; }

PREFIX="${HOME}/cyberstrike"
USE_UV=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix=*) PREFIX="${2}"; shift 2;;
    --prefix *)  PREFIX="${2}"; shift 2;;
    --uv)        USE_UV=true; shift;;
    -h|--help)
      echo "Usage: $0 [--prefix DIR] [--uv]"
      echo ""
      echo "  --prefix DIR   Install path (default: ~/cyberstrike)"
      echo "  --uv           Use uv instead of pip for package install"
      exit 0;;
    *) err "Unknown arg: $1"; exit 1;;
  esac
done

mkdir -p "$PREFIX"
DIR="$PREFIX/browser-firefox-mcp"

if [ -d "$DIR/.git" ]; then
  warn "Directory already exists: $DIR"
else
  info "Cloning to $DIR ..."
  git clone https://github.com/ironessi/browser-firefox-mcp.git "$DIR"
fi

cd "$DIR"

# ---- Python environment ----------------------------------------------------
PY=$(which python3 || true)
if [[ -z "$PY" ]]; then
  err "Python 3 not found. Install: sudo apt install python3"
  exit 1
fi
info "Python: $($PY --version)"

if $USE_UV; then
  # Optional fast path
  if ! command -v uv &>/dev/null; then
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>&1 | tail -2
    export PATH="$HOME/.local/bin:$PATH"
  fi
  info "Creating virtualenv with uv..."
  uv venv
  source .venv/bin/activate
  info "Installing packages with uv..."
  uv pip install -e .
else
  # Default: pure pip + venv
  VENV="$DIR/.venv"
  if [ ! -d "$VENV" ]; then
    info "Creating virtualenv at $VENV..."
    python3 -m venv "$VENV"
  fi
  source "$VENV/bin/activate"
  info "Installing packages with pip..."
  pip install -e .
fi

# ---- Playwright Firefox ----------------------------------------------------
info "Installing Playwright Firefox binary + dependencies..."
PLAYWRIGHT_BROWSERS_PATH=0 playwright install --with-deps firefox 2>&1 | tail -5

info ""
info "=============================================="
info "  Installation complete!"
info "=============================================="
echo ""
echo "  Test: cd $DIR && python server.py"
echo ""
echo "  Add to cyberstrikeai config:"
echo "  {\"mcp_servers\": {"
echo "    \"firefox-browser\": {"
echo "      \"command\": \"python\","
echo "      \"args\": [\"server.py\"],"
echo "      \"cwd\": \"$DIR\""
echo "    }"
echo "  }}"
echo ""
