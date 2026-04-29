#!/usr/bin/env bash
# =============================================================================
# dev.sh — Start Bajeti Watch locally + expose via ngrok for Twilio testing
#
# What this does:
#   1. Checks your .env has the required keys
#   2. Starts the FastAPI server on port 8000
#   3. Starts ngrok to give it a public HTTPS URL
#   4. Prints the Twilio webhook URL to copy into your Twilio console
#
# Prerequisites:
#   pip install -r requirements.txt
#   ngrok installed: https://ngrok.com/download
#       or: snap install ngrok
#
# Usage:
#   chmod +x dev.sh
#   ./dev.sh
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

PORT=8000

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

header "Environment"

if [ ! -f ".env" ]; then
  echo -e "${RED}  ERROR: .env file not found. Copy .env.example and fill in your keys.${RESET}"
  exit 1
fi

export $(grep -v '^#' .env | xargs)
log ".env loaded"

# Check required keys
MISSING=()
[ -z "$SUPABASE_URL" ]           && MISSING+=("SUPABASE_URL")
[ -z "$SUPABASE_KEY" ]           && MISSING+=("SUPABASE_KEY")
[ -z "$GROQ_API_KEY" ]           && MISSING+=("GROQ_API_KEY")
[ -z "$TWILIO_AUTH_TOKEN" ]      && MISSING+=("TWILIO_AUTH_TOKEN")

if [ ${#MISSING[@]} -gt 0 ]; then
  echo -e "${RED}  ERROR: Missing required .env keys:${RESET}"
  for key in "${MISSING[@]}"; do
    echo -e "    ${RED}✗  $key${RESET}"
  done
  exit 1
fi

log "All required keys present"

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------

header "Dependencies"

command -v uvicorn >/dev/null 2>&1 || { echo "ERROR: uvicorn not found. Run: pip install -r requirements.txt"; exit 1; }
command -v ngrok   >/dev/null 2>&1 || {
  echo -e "${YELLOW}  ngrok not found. Install it:${RESET}"
  echo -e "  ${BLUE}snap install ngrok${RESET}    # Ubuntu"
  echo -e "  ${BLUE}brew install ngrok${RESET}    # macOS"
  echo -e "  or download from https://ngrok.com/download"
  exit 1
}

log "uvicorn and ngrok found"

# ---------------------------------------------------------------------------
# Start FastAPI in the background
# ---------------------------------------------------------------------------

header "Starting FastAPI"

# Set to development mode so Twilio signature check can be bypassed for local tests
export APP_ENV=development

uvicorn api.main:app --reload --port $PORT --log-level info &
UVICORN_PID=$!
log "FastAPI started (PID $UVICORN_PID) on port $PORT"

# Give it a moment to boot
sleep 2

# Verify it's up
if ! curl -sf http://localhost:$PORT/health > /dev/null; then
  echo -e "${RED}  ERROR: FastAPI did not start correctly. Check the logs above.${RESET}"
  kill $UVICORN_PID 2>/dev/null
  exit 1
fi
log "Health check passed"

# ---------------------------------------------------------------------------
# Start ngrok
# ---------------------------------------------------------------------------

header "Starting ngrok"

ngrok http $PORT --log=stdout &
NGROK_PID=$!

info "Waiting for ngrok to get a public URL..."
sleep 3

# Fetch the public URL from ngrok's local API
NGROK_URL=$(curl -sf http://localhost:4040/api/tunnels \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

if [ -z "$NGROK_URL" ]; then
  warn "Could not auto-detect ngrok URL. Check http://localhost:4040 in your browser."
else
  log "ngrok tunnel: $NGROK_URL"
fi

# ---------------------------------------------------------------------------
# Print Twilio setup instructions
# ---------------------------------------------------------------------------

header "Twilio Setup"

echo ""
echo -e "  Copy this URL into your Twilio WhatsApp Sandbox settings:"
echo ""
if [ -n "$NGROK_URL" ]; then
  echo -e "  ${GREEN}${NGROK_URL}/webhook/whatsapp${RESET}"
else
  echo -e "  ${YELLOW}https://<your-ngrok-url>/webhook/whatsapp${RESET}"
  echo -e "  (Get your ngrok URL from: http://localhost:4040)"
fi
echo ""
echo -e "  In Twilio Console:"
echo -e "  ${BLUE}https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn${RESET}"
echo ""
echo -e "  Set: 'When a message comes in' → ${GREEN}${NGROK_URL:-<ngrok_url>}/webhook/whatsapp${RESET}"
echo -e "  Method: ${GREEN}HTTP POST${RESET}"
echo ""

# ---------------------------------------------------------------------------
# Test the local API
# ---------------------------------------------------------------------------

header "Quick local test"

info "Testing agent with a sample message (bypasses Twilio auth locally)..."
echo ""

# Temporarily allow skipping Twilio auth for local curl test
export SKIP_TWILIO_AUTH=true

RESPONSE=$(curl -sf -X POST \
  "http://localhost:$PORT/webhook/whatsapp" \
  -d "Body=Kisumu" \
  -d "From=whatsapp:+254700000000" \
  -d "ProfileName=TestUser" \
  2>/dev/null || echo "FAILED")

if echo "$RESPONSE" | grep -q "<Message>"; then
  log "Agent responded successfully"
  echo ""
  echo -e "  ${BLUE}Response preview:${RESET}"
  echo "$RESPONSE" | python3 -c "
import sys, re
content = sys.stdin.read()
msg = re.search(r'<Message>(.*?)</Message>', content, re.DOTALL)
if msg: print('  ' + msg.group(1)[:200].replace('\n', '\n  '))
"
else
  warn "Could not get a test response. Check server logs above."
fi

# ---------------------------------------------------------------------------
# Keep running
# ---------------------------------------------------------------------------

header "Running — press Ctrl+C to stop"
echo ""
echo -e "  FastAPI  : ${BLUE}http://localhost:$PORT${RESET}"
echo -e "  API docs : ${BLUE}http://localhost:$PORT/docs${RESET}"
echo -e "  ngrok UI : ${BLUE}http://localhost:4040${RESET}"
echo ""

# Cleanup on exit
trap "echo ''; echo 'Stopping...'; kill $UVICORN_PID $NGROK_PID 2>/dev/null; exit 0" INT TERM

# Wait for processes
wait $UVICORN_PID