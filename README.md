# OmniScrape API

A sophisticated, multi-layered web scraping service that can extract articles and products from any website using a cascading fallback strategy.

## ✨ Features

- **Multi-layered Extraction**: Structured data → Readability → LLM fallback
- **Article Extraction**: Title, author, content, images, publication date
- **Product Extraction**: Name, price, currency, description, images, SKU
- **Browser Rendering**: Playwright for JavaScript-heavy sites
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Type Safety**: Full Pydantic validation and type hints
- **Interactive Labs**: Test ScrapeGraphAI capabilities with real-time results
- **Token Usage Tracking**: Real-time LLM token consumption monitoring

## 🚀 Quick Start

1. **Install dependencies**:
   ```bash
   pip install -e .
   playwright install chromium
   ```

2. **Configure environment**:
   ```bash
   export OPENAI_API_KEY="your_openai_api_key"
   export SCRAPEGRAPH_MODEL="gpt-4o-mini"
   ```

3. **Start the server**:
   ```bash
   python src/main.py
   ```

4. **Access the services**:
   - **Main API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs
   - **Interactive Labs**: http://localhost:8000/labs
   - **Status Page**: http://localhost:8000/status
   - **Health JSON**: http://localhost:8000/health.json

## 📚 Documentation

### 📖 Comprehensive Documentation
- **[API Documentation](docs/api/)** - Complete API reference and usage examples
- **[Extractors Guide](docs/extractors/)** - Detailed extraction methods documentation
- **[Labs Documentation](docs/labs/)** - Interactive ScrapeGraphAI testing environment
- **[Architecture Overview](docs/architecture/)** - System design and technical details

### 🏗️ Project Structure
```
OmniScrape/
├── src/                    # Source code
│   ├── core/              # Core engine components
│   ├── api/               # FastAPI application
│   ├── extractors/        # Extraction methods
│   └── labs/              # ScrapeGraphAI implementations
├── docs/                  # Comprehensive documentation
│   ├── api/               # API documentation
│   ├── extractors/        # Extraction methods guide
│   ├── labs/              # Labs documentation
│   └── architecture/      # System architecture
├── tests/                 # Test suites
├── examples/              # Usage examples
├── config/                # Configuration files
└── old/                   # Legacy implementations (untouched)
```

## 🔧 API Usage

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

### Interactive Labs
Visit [http://localhost:8000/labs](http://localhost:8000/labs) to test:
- **SmartScraperGraph** - Single page extraction with custom prompts
- **SearchGraph** - Multi-page search-based extraction
- **SpeechGraph** - Audio generation from web content
- **ScriptCreatorGraph** - Python script generation
- **SmartScraperMultiGraph** - Multi-page extraction
- **ScriptCreatorMultiGraph** - Multi-page script generation

## ⚙️ Environment Variables

### Required
- `OPENAI_API_KEY` - OpenAI API key for LLM features

### Optional
- `SCRAPEGRAPH_MODEL` - LLM model (default: "gpt-4o-mini")
- `BING_SEARCH_API_KEY` - Bing Search API key (for SearchGraph)
- `MAX_RENDER_MS` - Maximum page render time (default: 15000)
- `HTTP_PROXY` / `HTTPS_PROXY` - Proxy configuration

## 🏗️ Architecture

The extraction pipeline uses a cascading fallback strategy:

### For Articles:
1. **Structured Data** - JSON-LD, Microdata, OpenGraph
2. **Readability** - Clean text extraction using readability-lxml
3. **LLM Fallback** - ScrapeGraphAI for complex cases

### For Products:
1. **Structured Data** - JSON-LD Product schemas
2. **Pattern Matching** - Regex-based price detection
3. **LLM Fallback** - ScrapeGraphAI for complex product pages

### LLM Modes
- **SD (Structured Data Only)**: JSON-LD + Readability, never calls LLM
- **LLM (LLM Only)**: Directly uses LLM-based extraction
- **AUTO (Smart Fallback)**: SD first; if content insufficient, fallback to LLM

## 🔬 Advanced Features

### Anti-Bot Measures
- User agent rotation
- Stealth JavaScript injection
- Human behavior simulation
- Resource blocking
- Proxy rotation support

### Token Usage Tracking
Real-time monitoring of LLM token consumption:
```json
{
  "_llm_usage": {
    "prompt_tokens": 150,
    "completion_tokens": 300,
    "total_tokens": 450,
    "model": "gpt-4o-mini"
  }
}
```

### Mobile Fallback
- Generic mobile retry for insufficient content
- Site-specific mobile URL mapping (e.g., 36kr)

## 🧪 Development

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
```

### Code Quality
```bash
# Format code
black src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

## 🚀 Deployment

### Docker
```bash
docker build -t omniscrape .
docker run -p 8000:8000 -e OPENAI_API_KEY=your_key omniscrape
```

### Production
```bash
uvicorn src.api.api:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📊 Monitoring

### Health & Status
- **Status UI**: `GET /status` — OpenAI-like status with RSS incidents
- **Health JSON**: `GET /health.json` — service checks and system metrics

### Metrics
- Response times and throughput
- Extraction success rates
- Token usage statistics
- Error tracking and analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **ScrapeGraphAI** - LLM-powered extraction graphs
- **Playwright** - Browser automation
- **FastAPI** - Modern web framework
- **OpenAI** - Language model services

