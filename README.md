# OmniScrape API

A sophisticated, multi-layered web scraping service that can extract articles and products from any website using a cascading fallback strategy.

## Features

- **Multi-layered Extraction**: Structured data → Readability → LLM fallback
- **Article Extraction**: Title, author, content, images, publication date
- **Product Extraction**: Name, price, currency, description, images, SKU
- **Browser Rendering**: Playwright for JavaScript-heavy sites
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Type Safety**: Full Pydantic validation and type hints

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -e .
   playwright install chromium
   ```

2. **Start the server**:
   ```bash
   python main.py
   ```

3. **Access the API**:
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## API Usage

### Extract Article
```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "kind": "article"}'
```

### Extract Product
```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/product", "kind": "product"}'
```

## Environment Variables

- `SCRAPEGRAPH_MODEL`: LLM model for ScrapeGraph AI (default: "gpt-4o-mini")
- `MAX_RENDER_MS`: Maximum page render time in milliseconds (default: 15000)

## Architecture

The extraction pipeline uses a cascading fallback strategy:

### For Articles:
1. **Structured Data** - JSON-LD, Microdata, OpenGraph
2. **Readability** - Clean text extraction using readability-lxml
3. **LLM Fallback** - ScrapeGraph AI for complex cases

### For Products:
1. **Structured Data** - JSON-LD Product schemas
2. **Pattern Matching** - Regex-based price detection
3. **LLM Fallback** - ScrapeGraph AI for complex product pages

## Development

The codebase is organized into modular components:

- `app/api.py` - FastAPI web service
- `app/pipeline.py` - Core extraction orchestration
- `app/schemas.py` - Pydantic data models
- `app/fetcher.py` - Browser rendering with Playwright
- `app/extract_*.py` - Specialized extraction modules

## System Architecture and Technical Walkthrough

### High-level Flow

1) User submits an extraction request from the UI or via API
2) `app/api.py` receives the request and calls `app/pipeline.py`
3) `pipeline.extract` orchestrates a cascading strategy:
   - Try Structured Data (JSON-LD/Microdata/OpenGraph)
   - If insufficient, try Readability-based clean extraction
   - If still insufficient (or LLM mode requires), invoke LLM via ScrapeGraphAI
4) `app/fetcher.py` renders pages (Playwright) with anti-bot/stealth and proxy options
5) Results are normalized to Pydantic schemas and returned with metadata

### Request → Response Path

- UI (served in `app/api.py`) → POST `/extract` → `pipeline.extract`
- Fetch HTML: `fetcher.fetch_rendered` (Playwright, stealth, proxies)
- Non-LLM paths:
  - Articles: `extract_readable.py` + `extract_patterns.py`
  - Products: `extract_structured.py` + `extract_patterns.py`
- LLM path (fallback or direct): `extract_scrapegraph.py` (ScrapeGraphAI)
- Return payload includes `_method_used`, optional `_execution_time`, and `_llm_usage` (token counts)

### LLM Modes (UI)

- SD (Structured Data Only): JSON-LD + Readability, never calls LLM
- LLM (LLM Only): Directly uses LLM-based extraction
- AUTO (Smart Fallback): SD first; if content insufficient, fallback to LLM

### Key Technologies

- FastAPI: API server, UI hosting, request handling
- Playwright: Headless Chromium page rendering with stealth and human-like behavior
- ScrapeGraphAI: LLM graph for complex extraction tasks
- LangChain (via ScrapeGraphAI): Chat model plumbing used by ScrapeGraphAI
- DeepSeek LLM (OpenAI-compatible): Primary LLM backend
- Pydantic: Input/output validation
- Tenacity: Robust retries for fetching

### DeepSeek Integration and Real Token Usage

- Model selection via env `SCRAPEGRAPH_MODEL` (e.g., `deepseek-chat`)
- API key via `DEEPSEEK_API_KEY` (or `OPENAI_API_KEY`)
- Base URL for DeepSeek: `https://api.deepseek.com/v1`
- Real token usage is captured without modifying ScrapeGraphAI by a safe, targeted monkey patch:
  - ScrapeGraphAI uses LangChain's `ChatOpenAI._generate` under the hood
  - We temporarily wrap `_generate` to:
    - Filter unsupported params (e.g., `provider`) to prevent 500s
    - Read `result.llm_output.token_usage` and expose it up to the API response
  - Implementation lives in `app/extract_scrapegraph.py`
  - Output surface: `_llm_usage = { input_tokens, output_tokens, total_tokens, model }`

Why monkey patch? It avoids forking or modifying ScrapeGraphAI and remains resilient to upstream changes, while providing accurate usage accounting directly from API responses.

### Anti-bot, Stealth, and Human-like Behavior

Implemented in `app/fetcher.py`:
- Chromium launch args for stealth, reduced fingerprinting, and stability
- JS injection to remove `navigator.webdriver`, mock plugins/languages/WebGL/Canvas
- Advanced headers (`sec-ch-ua*`, `Sec-Fetch-*`, etc.) and viewport tuning
- Human-like behavior simulation: curated mouse moves, scrolls, small delays
- Resource controls and timeouts (configurable via `MAX_RENDER_MS`)

### Proxy Rotation

- Optional support via env:
  - `PROXY_URLS` (comma-separated)
  - `PROXY_ROTATION` = `per_request` | `per_domain`
  - Optional `PROXY_USERNAME`/`PROXY_PASSWORD`
- Different proxies can be used for desktop and mobile retries

### Mobile Retry and 36kr Mobile Fallback

- If initial desktop fetch yields too little content → retry same URL as mobile
- Site-specific: for 36kr articles, fallback to corresponding `https://m.36kr.com/p/<id>`

### UI Behavior

- Three extraction modes (SD, LLM, AUTO) with visual cards
- Animated loading indicator and clear status messages
- Stop button using `AbortController` to cancel long-running requests
- Results enriched with method, execution time, and LLM token usage when applicable

### Error Handling

- Structured error responses with status, message, and traceback (for debug)
- Resilient retries for network/render steps (Tenacity)
- Clean cancellation path for user-initiated stop

### Configuration (.env)

Example:

```bash
SCRAPEGRAPH_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_key
# Optional proxy
PROXY_URLS=http://user:pass@host1:port,http://user:pass@host2:port
PROXY_ROTATION=per_request
MAX_RENDER_MS=15000
```

### Operational Notes

- Port conflicts: kill previous dev server using `kill -9 $(lsof -ti:8000)`
- If DeepSeek returns SSL/EOF errors, ensure system proxies are not leaking into LLM calls; we clear proxy env vars around LLM execution.
- Logs may warn about provider: it’s expected because we strip unsupported params before calling the OpenAI-compatible API.

### Files to Read First

- `app/api.py` – endpoint, UI markup, client-side behavior
- `app/pipeline.py` – orchestrates SD/Readability/LLM flow and mode handling
- `app/fetcher.py` – Playwright rendering, stealth, human-like behavior, proxies
- `app/extract_scrapegraph.py` – ScrapeGraphAI integration and token usage capture

### Architecture Diagram (ASCII)

```
┌──────────────────────┐           ┌──────────────────────────┐
│        Client        │  HTTP     │        FastAPI App       │
│  (Browser/UI or API) ├──────────▶│        app/api.py        │
└──────────────────────┘           └───────────┬──────────────┘
                                               │
                                               ▼
                                     ┌──────────────────────┐
                                     │Pipeline Orchestration│
                                     │     app/pipeline.py  │
                                     └───────────┬──────────┘
                                                 │
         ┌───────────────────────────────┬────────┴─────────┬───────────────────────────────┐
         │                               │                  │                               │
         ▼                               ▼                  ▼                               ▼
┌──────────────────┐           ┌──────────────────┐  ┌──────────────────┐         ┌──────────────────────┐
│ Structured Data  │           │  Readability     │  │  Product Patterns│         │    LLM (ScrapeGraph) │
│ JSON-LD/Microdata│           │  app/extract_... │  │  app/extract_... │         │ app/extract_scrape...│
└─────────┬────────┘           └─────────┬────────┘  └─────────┬────────┘         └───────────┬──────────┘
          │                              │                     │                              │
          └──────────────┬───────────────┴──────────────┬──────┴──────────────┬───────────────┘
                         │                              │                     │
                         ▼                              ▼                     ▼
                 ┌────────────────┐             ┌───────────────┐     ┌────────────────────────┐
                 │  Fetcher       │             │  UI Feedback  │     │ Token Usage (DeepSeek) │
                 │ app/fetcher.py │             │   app/api.py  │     │ via monkey patch       │
                 │ Playwright +   │             │ loading/stop  │     │ app/extract_scrape...  │
                 │ stealth + proxy│             │ summary       │     └────────────────────────┘
                 └────────────────┘             └───────────────┘
```

Mobile fallback: The fetcher performs a generic mobile retry for any page whose initial desktop render is empty or too short. Additionally, 36kr article pages have a targeted mobile mapping (e.g., `https://m.36kr.com/p/<id>`) to maximize success rates.

