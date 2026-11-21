# FinSimplify AI

AI-powered financial news simplification platform. Fetches recent financial news from **NewsAPI**, analyzes each article with **Groq (Llama 3.3 70B)**, and shows plain-English summaries, key takeaways, sentiment and a glossary in a responsive dashboard.

> Model note: `llama-3.3-70b-versatile` is the default. If Groq retires it on your account, change `GROQ_MODEL` in `.env` to a supported model; no code change needed.

## Documentation

Full documentation with screenshots of every screen: [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) (also as `docs/FinSimplify-AI-Documentation.pdf`). Screenshots use clearly labeled sample data, not live news.

## Quick start (one click)

1. Install Python 3.11+.
2. Get free keys: NewsAPI https://newsapi.org/register and Groq https://console.groq.com/keys
3. Launch:
   - **Windows:** double-click `start.bat`
   - **macOS:** double-click `start.command` (first time: right-click > Open)
   - **Linux:** run `./start.sh`
4. On first run a `.env` file opens; paste both keys, save, and (macOS/Linux) run the launcher again.

The launcher creates the virtual environment, installs dependencies, starts the server and opens **http://localhost:8000** in Chrome.

## Manual setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
uvicorn app.main:app --reload
```

Run tests (no real keys needed, external APIs are mocked): `pytest tests/ -v`

## Architecture

```
app/main.py            FastAPI app, error handlers, static + frontend serving
app/config.py          Settings from environment / .env
app/routes/news.py     /api/health, /api/news, /api/summarize
app/services/          news_service.py (NewsAPI), ai_service.py (Groq)
app/models/schemas.py  Pydantic models
app/static, templates  Vanilla HTML/CSS/JS frontend
tests/test_api.py      Pytest suite
```

## API

- `GET /api/health` - status and which providers are configured (never secrets)
- `GET /api/news?q=&topic=&page_size=` - topics: economy, stock_market, banking, business, technology, global_news; page_size max 50
- `POST /api/summarize` - body `{title, description, content, url}`; returns simple_summary, key_takeaways, why_it_matters, topic, sentiment, important_terms
- `GET /` - dashboard

## Common errors

| Symptom | Fix |
|---|---|
| 503 "NewsAPI is not configured" | Set `NEWSAPI_KEY` in `.env`, restart |
| 503 "AI summarization is not configured" | Set `GROQ_API_KEY` in `.env`, restart |
| 502 key rejected | Check the key is valid |
| 429 | Provider rate limit; wait and retry |
| Port 8000 in use | Stop the other process or change the port in the launcher |

## Security

Keys live only in server environment variables; article and AI text is rendered with `textContent`; external links are validated (http/https); CORS is off by default; no stack traces reach the client.

## Deployment

Any ASGI host (Render, Railway, Fly.io, Docker): start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT` and set `NEWSAPI_KEY` / `GROQ_API_KEY` as platform environment variables. On a public host, remove `--host 127.0.0.1` from the launchers (they are for local use).
