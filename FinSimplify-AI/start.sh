#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required: https://www.python.org/downloads/"; exit 1
fi

[ -d venv ] || python3 -m venv venv
. venv/bin/activate
echo "Installing dependencies (first run may take a minute)..."
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "A .env file was created. Add your NEWSAPI_KEY and GROQ_API_KEY, save it, then run this script again."
  open -e .env 2>/dev/null || ${EDITOR:-nano} .env
  exit 0
fi

URL="http://localhost:8000"
( sleep 4
  if [ "$(uname)" = "Darwin" ]; then open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"
  else (google-chrome "$URL" || chromium "$URL" || xdg-open "$URL") >/dev/null 2>&1; fi ) &
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
