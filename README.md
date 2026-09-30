# FinSimplify AI

An AI-powered financial news simplification platform. FinSimplify AI fetches
recent financial and economic news from **NewsAPI**, analyzes each article
with **Groq's Llama 3.3 70B** model, and presents beginner-friendly, plain
English summaries and key takeaways through a responsive web dashboard.

Target users: students, beginner investors, and busy professionals who want
the gist of financial news without the jargon.

> ⚠️ **Model note:** at the time this project was built, `llama-3.3-70b-versatile`
> was the current, generally-available Groq production model, so it is used
> as the default (`GROQ_MODEL` in `.env`). If Groq deprecates or renames this
> model on your account, update `GROQ_MODEL` to a currently supported model —
> no code changes are required, since the model name is fully configurable.

---

## Features

- 🔎 **Live financial news feed** from NewsAPI (`/v2/everything`), with free-text
  search and curated topic filters (Economy, Stock Market, Banking, Business,
  Technology, Global News).
- 🤖 **"Simplify with AI" button** on every article — sends the article to Groq
  and returns a structured JSON explanation: simple summary, key takeaways,
  why it matters, topic, cautious sentiment, and a glossary of financial terms.
- 🧠 Prompting that treats article text as **untrusted data** (not instructions),
  asks the model to distinguish facts from speculation, and never presents
  output as personalized financial advice.
- 🖥️ **Responsive navy/white dashboard** with skeleton loading states, empty
  states, retry buttons, and a details modal — built with plain HTML/CSS/JS
  (no frontend framework, no build step).
- 🔐 **Security-conscious backend**: secrets only ever live in environment
  variables, a global exception handler prevents stack-trace leakage, input
  is length-validated, and CORS is disabled by default (same-origin frontend).
- 🧪 **Automated tests** with mocked external APIs (no real keys required to
  run the test suite).

---

## Architecture

```
FinSimplify-AI/
  app/
    main.py              # FastAPI app: routing, CORS, error handlers, static/frontend serving
    config.py            # Settings loaded from environment variables (.env supported)
    routes/
      news.py             # /api/health, /api/news, /api/summarize
    services/
      news_service.py      # NewsAPI integration, normalization, deduplication
      ai_service.py         # Groq integration, prompt construction, JSON validation
    models/
      schemas.py            # Pydantic request/response models
    static/
      css/style.css          # Navy/white themed responsive styling
      js/app.js               # Vanilla JS frontend logic (Fetch API, safe DOM rendering)
    templates/
      index.html               # Single-page dashboard shell
  tests/
    test_api.py           # Pytest suite (external calls mocked with respx)
  .env.example           # Template for required environment variables
  .gitignore
  requirements.txt
  README.md
```

**Request flow:**
1. Browser loads `/` → FastAPI serves `app/templates/index.html` (+ static CSS/JS).
2. `app.js` calls `GET /api/news` → `routes/news.py` → `services/news_service.py`
   → NewsAPI → normalized, deduplicated `NewsArticle` list returned as JSON.
3. User clicks "Simplify with AI" → `app.js` calls `POST /api/summarize` →
   `routes/news.py` → `services/ai_service.py` → Groq chat completion (JSON
   mode) → validated `SummarizeResponse` returned as JSON.
4. The frontend caches summaries in memory for the session so the same
   article isn't re-summarized unnecessarily.

---

## Prerequisites

- Python 3.11 or newer
- A [NewsAPI](https://newsapi.org/register) API key (free tier available)
- A [Groq](https://console.groq.com/keys) API key (free tier available)

---

## Setup

### 1. Get the code and enter the project folder

```bash
cd FinSimplify-AI
```

### 2. Create and activate a virtual environment

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Windows (cmd.exe):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your real keys:

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows:**
```cmd
copy .env.example .env
```

Then edit `.env`:

```
NEWSAPI_KEY=your_real_newsapi_key
GROQ_API_KEY=your_real_groq_key
GROQ_MODEL=llama-3.3-70b-versatile
```

`.env` is already listed in `.gitignore` and will never be committed.

**Where to get keys:**
- NewsAPI: sign up at https://newsapi.org/register, then copy your key from
  your account dashboard.
- Groq: sign up at https://console.groq.com, then create a key at
  https://console.groq.com/keys.

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Then open **http://localhost:8000** in your browser.

Without either key configured, the app still starts successfully; the
`/api/health` endpoint will report `"status": "degraded"` and the affected
endpoints will return a clear `503` error explaining which key is missing,
rather than fabricating data.

### 6. Run the tests

```bash
pytest tests/ -v
```

All 20 tests pass without any real API keys — external HTTP calls to NewsAPI
and Groq are mocked with `respx`.

---

## API Reference

### `GET /api/health`
Returns app status and which providers are configured (never the secret
values themselves).

```json
{
  "status": "ok",
  "app_name": "FinSimplify AI",
  "environment": "development",
  "newsapi_configured": true,
  "groq_configured": true,
  "groq_model": "llama-3.3-70b-versatile"
}
```

### `GET /api/news`
Query params (all optional):
- `q` — free-text search (max 200 chars)
- `topic` — one of `economy`, `stock_market`, `banking`, `business`,
  `technology`, `global_news`
- `page_size` — number of articles to return (default 12, max 50)

```bash
curl "http://localhost:8000/api/news?topic=banking&page_size=10"
```

### `POST /api/summarize`
Body:
```json
{
  "title": "Central bank raises interest rates",
  "description": "Optional short description",
  "content": "Optional longer content snippet",
  "url": "https://example.com/article"
}
```

Response:
```json
{
  "simple_summary": "...",
  "key_takeaways": ["...", "...", "..."],
  "why_it_matters": "...",
  "topic": "Banking",
  "sentiment": "neutral",
  "important_terms": [{"term": "Interest rate", "explanation": "..."}],
  "model_used": "llama-3.3-70b-versatile",
  "disclaimer": "AI-generated summary for educational purposes only..."
}
```

### `GET /`
Serves the frontend dashboard.

---

## Common Errors

| Symptom | Cause | Fix |
|---|---|---|
| `/api/news` returns 503 "NewsAPI is not configured" | `NEWSAPI_KEY` missing/blank | Set it in `.env` and restart the server |
| `/api/summarize` returns 503 "AI summarization is not configured" | `GROQ_API_KEY` missing/blank | Set it in `.env` and restart the server |
| `/api/news` returns 502 "NewsAPI rejected the API key" | Invalid/expired NewsAPI key | Verify the key at newsapi.org |
| `/api/summarize` returns 502 "the response we could not parse" | Groq returned non-JSON output | Usually transient; retry. The backend already asks for strict JSON and validates it |
| `429 Too Many Requests` | Free-tier rate limits hit on NewsAPI or Groq | Wait and retry, or upgrade your plan |
| Browser shows blank page | Server not running, or wrong port | Confirm `uvicorn app.main:app` is running and you're on the right port |

---

## Security Notes

- API keys are **only** read from environment variables/`.env` on the server;
  they are never sent to or stored in the browser.
- CORS is disabled by default because the frontend and API share the same
  origin. Only enable it (via `CORS_ALLOWED_ORIGINS`) if you split the
  frontend onto a different domain.
- All external content (news titles/descriptions and AI output) is rendered
  with `textContent`, never `innerHTML`, to avoid DOM-based XSS from
  untrusted third-party content.
- Links to external articles are validated (`http`/`https` only) before being
  made clickable.
- A global exception handler ensures stack traces and internal details are
  never returned to the client.

---

## Deployment Guidance

This is a standard ASGI app and can be deployed with any ASGI-compatible
host:

- **Render / Railway / Fly.io / a VM**: run
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (or use a process
  manager like `gunicorn -k uvicorn.workers.UvicornWorker`), and set
  `NEWSAPI_KEY` / `GROQ_API_KEY` as platform environment variables (not a
  committed `.env` file).
- **Docker**: build an image with `requirements.txt` installed and
  `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`;
  pass secrets via `--env-file` or your orchestrator's secrets manager.
- Set `ENVIRONMENT=production` and configure `CORS_ALLOWED_ORIGINS` only if
  the frontend will be served from a different origin than the API.

---

## Manual Configuration Still Required

- You must supply your own `NEWSAPI_KEY` and `GROQ_API_KEY` in `.env` — no
  working keys are included with this project, and no live data or AI output
  can be produced without them.
- If Groq deprecates `llama-3.3-70b-versatile` in the future, update
  `GROQ_MODEL` in `.env` to a currently supported model.
