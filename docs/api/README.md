# API Documentation

This directory contains comprehensive documentation for the OmniScrape API endpoints and data models.

## 🌐 API Endpoints

### Core Extraction API

#### `POST /extract`
### Streaming Endpoints

#### `GET /extract-stream`
Server-Sent Events endpoint for real-time extract progress messages.

#### `GET /crawl-stream`
Server-Sent Events endpoint for real-time crawl progress messages.
Main extraction endpoint for articles and products.

**Request Body:**
```json
{
  "url": "https://example.com/article",
  "kind": "article|product",
  "llmMode": "SD|LLM|AUTO"
}
```

**Response:**
```json
{
  "title": "Article Title",
  "author": "Author Name",
  "date_published": "2024-01-01",
  "text": "Article content...",
  "images": ["url1", "url2"],
  "_method_used": "structured_data|readability|llm",
  "_execution_time": 1.23,
  "_llm_usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "model": "gpt-4o-mini"
  }
}
```

### Labs API

#### `POST /labs/smart`
SmartScraperGraph - Single page extraction with custom prompt.

#### `POST /labs/search`
SearchGraph - Multi-page search-based extraction (requires Bing API).

#### `POST /labs/speech`
SpeechGraph - Audio generation from web content.

#### `POST /labs/script`
ScriptCreatorGraph - Python script generation.

#### `POST /labs/multi`
SmartScraperMultiGraph - Multi-page extraction.

#### `POST /labs/script-multi`
ScriptCreatorMultiGraph - Multi-page script generation.

### Utility Endpoints

#### `GET /status`
Status UI page (includes OpenAI RSS incidents).

#### `GET /health.json`
JSON health with system checks and configuration.

#### `GET /docs`
Swagger API documentation.

#### `GET /redoc`
ReDoc API documentation.

#### `GET /labs`
Interactive Labs page.

## 📊 Data Models

### Article Schema
```python
{
  "title": str,
  "author": str,
  "date_published": str,
  "text": str,
  "images": List[str]
}
```

### Product Schema
```python
{
  "name": str,
  "price": str,
  "currency": str,
  "description": str,
  "images": List[str],
  "sku": str
}
```

### LLM Usage Schema
```python
{
  "prompt_tokens": int,
  "completion_tokens": int,
  "total_tokens": int,
  "model": str
}
```

## 🔑 Authentication

All API endpoints require proper configuration:

- **OpenAI API Key**: `OPENAI_API_KEY` (required for LLM features)
- **Bing Search API Key**: `BING_SEARCH_API_KEY` (optional, for SearchGraph)
- **Model Configuration**: `SCRAPEGRAPH_MODEL` (default: "gpt-4o-mini")

## ⚠️ Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "success": false,
  "error": "Invalid request parameters"
}
```

#### 500 Internal Server Error
```json
{
  "success": false,
  "error": "Detailed error message with traceback"
}
```

### Error Codes

- **Missing API Key**: `LLM API key missing: set OPENAI_API_KEY`
- **Regional Restriction**: `Country, region, or territory not supported`
- **Invalid URL**: `Failed to fetch URL`
- **Extraction Failure**: `No content extracted`

## 🚀 Usage Examples

### cURL Examples

```bash
# Extract article
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "kind": "article"}'

# Extract product
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/product", "kind": "product"}'

# Use Labs SmartScraper
curl -X POST "http://localhost:8000/labs/smart" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "prompt": "Extract title and content"}'
```

### Python Examples

```python
import requests

# Extract article
response = requests.post(
    "http://localhost:8000/extract",
    json={"url": "https://example.com/article", "kind": "article"}
)
data = response.json()

# Use Labs API
response = requests.post(
    "http://localhost:8000/labs/smart",
    json={
        "url": "https://example.com",
        "prompt": "Extract the main title and key points"
    }
)
result = response.json()
```

## 🔧 Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional
SCRAPEGRAPH_MODEL=gpt-4o-mini
BING_SEARCH_API_KEY=your_bing_api_key
MAX_RENDER_MS=15000
```

### Model Configuration

Supported models:
- `gpt-4o-mini` (default)
- `gpt-4o`
- `gpt-3.5-turbo`
- Any OpenAI-compatible model

## 📈 Performance

### Response Times
- **Structured Data**: ~100-500ms
- **Readability**: ~200-800ms
- **LLM Extraction**: ~2-10s (depending on content size)

### Rate Limits
- No built-in rate limiting
- Limited by OpenAI API rate limits
- Recommended: Implement client-side throttling

## 🛠️ Development

### Local Development
```bash
# Start server
python src/main.py

# Access API docs
open http://localhost:8000/docs

# Test endpoints
curl http://localhost:8000/health.json
```

### Testing
```bash
# Run tests
pytest tests/

# Test specific endpoint
pytest tests/test_api.py::test_extract_article
```
