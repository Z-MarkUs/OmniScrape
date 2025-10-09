# Source Code Documentation

This directory contains the main source code for the OmniScrape web scraping service, organized into logical modules.

## 📁 Directory Structure

### `core/` - Core Engine Components
- **Pipeline Orchestration**: Main extraction workflow management
- **Browser Engine**: Playwright integration with anti-bot features
- **LLM Wrapper**: Token usage tracking and API management
- **Data Models**: Pydantic schemas for validation

### `api/` - API Layer
- **FastAPI Application**: Main web server and endpoints
- **Request Handling**: Input validation and routing
- **Response Formatting**: JSON responses with metadata
- **UI Integration**: Web interface and Labs page

### `extractors/` - Extraction Methods
- **Structured Data**: JSON-LD, Microdata, OpenGraph parsing
- **Readability**: Clean text extraction
- **Pattern Matching**: Regex-based data extraction
- **LLM Integration**: ScrapeGraphAI with monkey patching

### `labs/` - Labs Implementation
- **Graph Implementations**: All ScrapeGraphAI graph types
- **Interactive Testing**: Real-time graph execution
- **Configuration Management**: Graph-specific settings
- **Async Processing**: Non-blocking graph execution

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- pip package manager
- Git (for development)

### Installation
```bash
# Clone repository
git clone https://github.com/Z-MarkUs/OmniScrape.git
cd OmniScrape

# Install dependencies
pip install -e .

# Install Playwright browsers
playwright install chromium
```

### Configuration
```bash
# Set required environment variables
export OPENAI_API_KEY="your_openai_api_key"
export SCRAPEGRAPH_MODEL="gpt-4o-mini"

# Optional configuration
export BING_SEARCH_API_KEY="your_bing_api_key"
export MAX_RENDER_MS="15000"
```

### Running the Server
```bash
# Start development server
python src/main.py

# Server will be available at:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - Labs: http://localhost:8000/labs
```

## 🧪 Development

### Code Organization
- **Modular Design**: Each component has a specific responsibility
- **Type Hints**: Full type annotation for better IDE support
- **Error Handling**: Comprehensive error management
- **Async Support**: Non-blocking operations where possible

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests

# Run with coverage
pytest --cov=src tests/
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

## 📚 API Documentation

### Core API
- **Extract Endpoint**: `/extract` - Main extraction endpoint
- **Health Check**: `/health` - System health status
- **API Docs**: `/docs` - Swagger documentation

### Labs API
- **SmartScraper**: `/labs/smart` - Single page extraction
- **SearchGraph**: `/labs/search` - Search-based extraction
- **SpeechGraph**: `/labs/speech` - Audio generation
- **ScriptCreator**: `/labs/script` - Script generation
- **Multi-Page**: `/labs/multi` - Multi-page extraction
- **Multi-Script**: `/labs/script-multi` - Multi-page scripts

## 🔧 Configuration

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional
SCRAPEGRAPH_MODEL=gpt-4o-mini
BING_SEARCH_API_KEY=your_bing_api_key
MAX_RENDER_MS=15000
HEADLESS=true
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=https://proxy:8080
```

### Configuration Files
- **pyproject.toml**: Project configuration and dependencies
- **.env**: Environment variables (create from .env.example)
- **config/**: Additional configuration files

## 🚀 Deployment

### Docker Deployment
```bash
# Build image
docker build -t omniscrape .

# Run container
docker run -p 8000:8000 -e OPENAI_API_KEY=your_key omniscrape
```

### Production Deployment
```bash
# Install production dependencies
pip install -e .[production]

# Run with production server
uvicorn src.api.api:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📊 Monitoring

### Health Checks
- **Endpoint**: `GET /health`
- **Response**: `{"ok": true}`
- **Checks**: Database connectivity, external APIs

### Metrics
- **Performance**: Response times, throughput
- **Usage**: API calls, extraction methods
- **Errors**: Failure rates, error types
- **Resources**: CPU, memory, network usage

### Logging
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Format**: Structured JSON logging
- **Context**: Request IDs, user agents, timestamps

## 🔒 Security

### Input Validation
- **URL Validation**: Verify URL format and accessibility
- **Content Sanitization**: Remove malicious content
- **Prompt Filtering**: Validate LLM prompts
- **Size Limits**: Limit request and response sizes

### API Security
- **Rate Limiting**: Prevent abuse and overuse
- **Authentication**: API key validation
- **CORS**: Cross-origin resource sharing
- **HTTPS**: Encrypted communication

## 🛠️ Troubleshooting

### Common Issues

#### Server Won't Start
- Check Python version (3.10+ required)
- Verify all dependencies are installed
- Check for port conflicts (8000)

#### API Errors
- Verify API keys are set correctly
- Check network connectivity
- Review error logs for details

#### Extraction Failures
- Check URL accessibility
- Verify HTML structure
- Try different extraction methods
- Review anti-bot measures

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python src/main.py
```

## 📖 Additional Resources

- **API Documentation**: [docs/api/](../docs/api/)
- **Extractors Guide**: [docs/extractors/](../docs/extractors/)
- **Labs Documentation**: [docs/labs/](../docs/labs/)
- **Architecture Overview**: [docs/architecture/](../docs/architecture/)
- **Main README**: [../README.md](../README.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive tests
- Update documentation for new features
- Use meaningful commit messages
