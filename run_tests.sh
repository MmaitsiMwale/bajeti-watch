#!/usr/bin/env bash
# =============================================================================
# run_tests.sh — Bajeti Watch ingestion pipeline test runner
#
# Usage:
#   ./run_tests.sh                    # local unit tests only (no keys needed)
#   ./run_tests.sh --integration      # include Supabase + Groq tests
#   ./run_tests.sh --pdf path/to/     # point to your PDF folder
#   ./run_tests.sh --full             # everything
# =============================================================================

set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
RED="\033[0;31m"
RESET="\033[0m"

log()    { echo -e "${GREEN}  ✔  $1${RESET}"; }
info()   { echo -e "${BLUE}  →  $1${RESET}"; }
warn()   { echo -e "${YELLOW}  ⚠  $1${RESET}"; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; }
fail()   { echo -e "${RED}  ✗  $1${RESET}"; }

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------

MODE="local"
PDF_PATH=""

for arg in "$@"; do
  case $arg in
    --integration)  MODE="integration" ;;
    --full)         MODE="full" ;;
    --pdf)          shift; PDF_PATH="$1" ;;
    --help|-h)
      echo "Usage: $0 [--integration] [--full] [--pdf /path/to/pdfs]"
      exit 0 ;;
  esac
done

# ---------------------------------------------------------------------------
# Environment check
# ---------------------------------------------------------------------------

header "Environment"

# Load .env if present
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
  log ".env loaded"
fi

# Set PDF path if provided
if [ -n "$PDF_PATH" ]; then
  export TEST_PDF_PATH="$PDF_PATH"
  info "PDF path set to: $PDF_PATH"
fi

# Auto-discover PDFs
PDF_COUNT=$(find "${TEST_PDF_PATH:-tests/fixtures}" -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PDF_COUNT" -eq 0 ]; then
  PDF_COUNT=$(find . -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
fi

info "PDFs found        : $PDF_COUNT"
info "GROQ_API_KEY set  : $([ -n "$GROQ_API_KEY" ] && echo yes || echo no)"
info "SUPABASE_URL set  : $([ -n "$SUPABASE_URL" ] && echo yes || echo no)"
info "Test mode         : $MODE"

# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------

header "Dependencies"

if ! python -c "import pytest" 2>/dev/null; then
  info "Installing test dependencies..."
  pip install --quiet pytest pytest-asyncio pyyaml requests rich
fi
log "pytest ready"

# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

header "Running tests — mode: $MODE"

mkdir -p tests/fixtures

case $MODE in

  local)
    info "Running unit tests (no external services needed)"
    python -m pytest tests/ingestion/test_cleaner.py tests/ingestion/test_tagger.py -v \
      && python -m pytest tests/ingestion/test_pipeline_integration.py -v -m "local" \
      || true
    ;;

  integration)
    info "Running unit + integration tests (Supabase + Groq)"

    if [ -z "$GROQ_API_KEY" ]; then
      warn "GROQ_API_KEY not set — auto-tag tests will be skipped"
    fi
    if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
      warn "Supabase credentials not set — upload tests will be skipped"
    fi

    python -m pytest tests/ingestion/ -v -m "local or integration" || true
    ;;

  full)
    info "Running full test suite"
    python -m pytest tests/ -v || true
    ;;

esac

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

header "Done"

echo ""
echo -e "  Intermediate files written to ${BLUE}pipeline_work/${RESET} (if integration tests ran)"
echo -e "  To inspect a converted PDF: ${BLUE}cat pipeline_work/01_markdown/<name>.md${RESET}"
echo ""

if [ "$PDF_COUNT" -eq 0 ]; then
  warn "No PDFs were found. To test with your real budget PDFs:"
  echo ""
  echo -e "  Put PDFs in:  ${BLUE}tests/fixtures/${RESET}"
  echo -e "  Or run:       ${BLUE}./run_tests.sh --pdf /path/to/your/pdfs${RESET}"
  echo ""
fi
