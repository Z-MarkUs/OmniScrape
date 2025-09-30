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
