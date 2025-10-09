# Core Engine Components

This directory contains the core engine components that power the OmniScrape web scraping service.

## 📁 Files Overview

### `pipeline.py` - Main Pipeline Orchestration
**Purpose**: Central orchestration of the extraction workflow

**Key Functions**:
- `extract()` - Main extraction entry point
- `_try_extraction_methods()` - Cascading fallback strategy
- `_normalize_result()` - Result standardization

**Features**:
- Multi-method extraction strategy
- Fallback mechanisms
- Result normalization
- Error handling and recovery

### `fetcher.py` - Browser Engine
**Purpose**: Web page fetching with anti-bot measures

**Key Functions**:
- `fetch_rendered()` - Main page fetching function
- `_setup_browser()` - Browser configuration
- `_apply_stealth_measures()` - Anti-detection techniques

**Features**:
- Playwright integration
- User agent rotation
- Stealth JavaScript injection
- Human behavior simulation
- Proxy support
- Resource blocking

### `llm_wrapper.py` - LLM Integration
**Purpose**: Token usage tracking and API management

**Key Components**:
- `TokenUsageTracker` - Thread-safe token tracking
- `CustomOpenAIClient` - API client with usage capture
- `get_token_usage()` - Retrieve usage statistics

**Features**:
- Real-time token usage tracking
- Parameter filtering
- Error handling
- Thread-safe operations

### `schemas.py` - Data Models
**Purpose**: Pydantic schemas for data validation

**Key Models**:
- `ExtractRequest` - API request validation
- `ArticleData` - Article extraction schema
- `ProductData` - Product extraction schema
- `LLMUsage` - Token usage tracking schema

**Features**:
- Type validation
- Data serialization
- Error reporting
- API documentation

## 🔧 Configuration

### Browser Settings
```python
BROWSER_CONFIG = {
    "headless": True,
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "rotated_agents",
    "stealth": True,
    "proxy": "optional_proxy"
}
```

### LLM Configuration
```python
LLM_CONFIG = {
    "model": "gpt-4o-mini",
    "api_key": "your_openai_key",
    "max_tokens": 128000,
    "temperature": 0.1
}
```

## 🚀 Usage Examples

### Pipeline Usage
```python
from src.core.pipeline import extract

# Extract article
result = await extract(
    url="https://example.com/article",
    kind="article",
    llm_mode="AUTO"
)
```

### Browser Fetching
```python
from src.core.fetcher import fetch_rendered

# Fetch page with anti-bot measures
html_content = await fetch_rendered(
    url="https://example.com",
    max_render_ms=15000
)
```

### LLM Integration
```python
from src.core.llm_wrapper import get_token_usage, clear_token_usage

# Clear previous usage
clear_token_usage()

# Make LLM call
# ... LLM operation ...

# Get usage statistics
usage = get_token_usage()
print(f"Tokens used: {usage['total_tokens']}")
```

## 🧪 Testing

### Unit Tests
```bash
# Test pipeline
pytest tests/unit/test_pipeline.py

# Test fetcher
pytest tests/unit/test_fetcher.py

# Test LLM wrapper
pytest tests/unit/test_llm_wrapper.py

# Test schemas
pytest tests/unit/test_schemas.py
```

### Integration Tests
```bash
# Test full pipeline
pytest tests/integration/test_pipeline_integration.py

# Test with real websites
pytest tests/integration/test_real_sites.py
```

## 🔒 Security Features

### Anti-Bot Measures
- **User Agent Rotation**: Multiple realistic user agents
- **Stealth JavaScript**: Remove automation indicators
- **Human Behavior**: Mouse movements, scrolling, typing
- **Resource Blocking**: Block tracking and analytics
- **Proxy Support**: IP rotation capabilities

### Input Validation
- **URL Validation**: Verify URL format and accessibility
- **Content Sanitization**: Remove malicious content
- **Size Limits**: Prevent memory exhaustion
- **Rate Limiting**: Prevent abuse

## 📊 Performance

### Optimization Strategies
- **Connection Pooling**: Reuse HTTP connections
- **Caching**: Cache HTML content and results
- **Async Processing**: Non-blocking operations
- **Resource Management**: Efficient memory usage

### Monitoring
- **Response Times**: Track extraction performance
- **Success Rates**: Monitor extraction success
- **Resource Usage**: CPU, memory, network monitoring
- **Error Tracking**: Comprehensive error logging

## 🛠️ Troubleshooting

### Common Issues

#### Browser Launch Failures
- Check Playwright installation
- Verify browser dependencies
- Check system permissions
- Review proxy settings

#### LLM API Errors
- Verify API key validity
- Check regional restrictions
- Monitor token usage
- Review rate limits

#### Extraction Failures
- Check URL accessibility
- Verify HTML structure
- Review anti-bot measures
- Try different extraction methods

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable verbose mode
config = {"verbose": True}
```

## 📚 Additional Resources

- **API Documentation**: [../docs/api/](../../docs/api/)
- **Architecture Overview**: [../docs/architecture/](../../docs/architecture/)
- **Main README**: [../README.md](../README.md)
