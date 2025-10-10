# Status & Health

- Status UI: `GET /status` — OpenAI-inspired status cards with latest incidents.
- Health JSON: `GET /health.json` — local checks (API keys, model, system metrics).
- OpenAI Status Source: `https://status.openai.com/feed.rss`.

Example JSON (abridged):
```json
{
  "status": "healthy",
  "service": "OmniScrape API",
  "checks": {
    "openai_api": {"status": "configured"},
    "model_config": {"status": "configured", "message": "Model configured: gpt-4o-mini"},
    "system": {"status": "healthy", "cpu_percent": 1.2, "memory_mb": 120.5}
  }
}
```
