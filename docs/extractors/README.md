# Extractors Documentation

This directory contains detailed documentation for all extraction methods available in OmniScrape.

## 🔍 Extraction Methods Overview

OmniScrape uses a cascading fallback strategy to ensure maximum extraction success:

1. **Structured Data** → 2. **Readability** → 3. **LLM Fallback**

## 📊 Structured Data Extraction

### Supported Formats
- **JSON-LD** - Structured data in `<script type="application/ld+json">`
- **Microdata** - HTML attributes (`itemscope`, `itemprop`, etc.)
- **OpenGraph** - Meta tags (`og:title`, `og:description`, etc.)

### Implementation
- **File**: `src/extractors/extract_structured.py`
- **Library**: `extruct` for parsing structured data
- **Coverage**: Articles, Products, Organizations, Events

### Example Usage
```python
from src.extractors.extract_structured import extract_structured_data

# Extract structured data from HTML
result = extract_structured_data(html_content)
```

### Supported Schemas
- `Article` - News articles, blog posts
- `Product` - E-commerce products
- `Organization` - Company information
- `Event` - Event details
- `Person` - Individual profiles

## 📖 Readability Extraction

### Purpose
Extract clean, readable text from web pages by removing navigation, ads, and other non-content elements.

### Implementation
- **File**: `src/extractors/extract_readable.py`
- **Library**: `readability-lxml` for content extraction
- **Features**: Title extraction, content cleaning, image detection

### Example Usage
```python
from src.extractors.extract_readable import extract_readable_content

# Extract readable content
result = extract_readable_content(html_content, url)
```

### Output Format
```python
{
    "title": "Article Title",
    "text": "Clean article content...",
    "images": ["image1.jpg", "image2.jpg"],
    "author": "Author Name",
    "date_published": "2024-01-01"
}
```

## 🤖 LLM-Powered Extraction

### ScrapeGraphAI Integration
Advanced extraction using Large Language Models for complex or unstructured content.

### Implementation
- **File**: `src/extractors/extract_scrapegraph.py`
- **Library**: `scrapegraphai` for LLM graphs
- **Features**: Custom prompts, token usage tracking, monkey patching

### Example Usage
```python
from src.extractors.extract_scrapegraph import scrapegraph_article

# Extract using LLM
result = scrapegraph_article(url)
```

### Configuration
```python
config = {
    "llm": {
        "model": "gpt-4o-mini",
        "api_key": "your_openai_key"
    },
    "verbose": True,
    "headless": True,
    "model_tokens": 128000
}
```

## 🎯 Pattern Matching

### Purpose
Extract specific data using regex patterns and CSS selectors.

### Implementation
- **File**: `src/extractors/extract_patterns.py`
- **Features**: Price detection, date parsing, URL extraction

### Example Usage
```python
from src.extractors.extract_patterns import extract_patterns

# Extract patterns from content
patterns = extract_patterns(content, url)
```

### Supported Patterns
- **Prices**: `$19.99`, `€25.50`, `¥1000`
- **Dates**: `2024-01-01`, `Jan 1, 2024`
- **URLs**: Links and image sources
- **Emails**: Email addresses
- **Phone Numbers**: Various formats

## 🔄 Extraction Pipeline

### Flow Diagram
```
URL Input
    ↓
Fetch HTML (Playwright)
    ↓
Structured Data Extraction
    ↓ (if insufficient)
Readability Extraction
    ↓ (if insufficient or LLM mode)
LLM Extraction (ScrapeGraphAI)
    ↓
Result Normalization
    ↓
JSON Response
```

### Decision Logic
```python
if llm_mode == "SD":
    # Only structured data + readability
    return structured_data or readability_result
elif llm_mode == "LLM":
    # Only LLM extraction
    return llm_result
else:  # AUTO
    # Cascading fallback
    return structured_data or readability_result or llm_result
```

## ⚙️ Configuration

### Environment Variables
```bash
# LLM Configuration
OPENAI_API_KEY=your_key
SCRAPEGRAPH_MODEL=gpt-4o-mini

# Browser Configuration
MAX_RENDER_MS=15000
HEADLESS=true

# Proxy Configuration (optional)
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=https://proxy:8080
```

### Browser Settings
- **Headless**: `true` (default)
- **Viewport**: `1920x1080`
- **User Agent**: Rotated for anti-detection
- **Resource Blocking**: Images, analytics, tracking

## 🚀 Performance Optimization

### Caching
- **HTML Caching**: Temporary storage of fetched content
- **Result Caching**: Cache extraction results by URL hash
- **LLM Caching**: Token usage tracking and optimization

### Parallel Processing
- **Async Extraction**: Non-blocking extraction calls
- **Thread Pool**: LLM calls in separate threads
- **Concurrent Fetching**: Multiple URL processing

### Resource Management
- **Memory Usage**: Efficient HTML parsing
- **CPU Usage**: Optimized regex patterns
- **Network Usage**: Connection pooling and retries

## 🧪 Testing

### Unit Tests
```bash
# Test structured data extraction
pytest tests/unit/test_structured.py

# Test readability extraction
pytest tests/unit/test_readable.py

# Test LLM extraction
pytest tests/unit/test_scrapegraph.py
```

### Integration Tests
```bash
# Test full extraction pipeline
pytest tests/integration/test_pipeline.py

# Test with real websites
pytest tests/integration/test_real_sites.py
```

## 🔧 Customization

### Adding New Extractors
1. Create new file in `src/extractors/`
2. Implement extraction function
3. Add to pipeline in `src/core/pipeline.py`
4. Update tests and documentation

### Custom Patterns
```python
# Add custom regex patterns
CUSTOM_PATTERNS = {
    "custom_field": r"Custom Pattern: (\w+)",
    "special_format": r"Format: (\d{4}-\d{2}-\d{2})"
}
```

### Custom LLM Prompts
```python
# Modify prompts in extract_scrapegraph.py
CUSTOM_PROMPT = """
Extract the following information:
- Title
- Author
- Publication date
- Main content
- Images
"""
```

## 📈 Monitoring

### Metrics
- **Extraction Success Rate**: Percentage of successful extractions
- **Method Usage**: Distribution of extraction methods
- **Performance**: Average extraction times
- **Token Usage**: LLM API consumption

### Logging
- **Debug Level**: Detailed extraction steps
- **Info Level**: Method selection and results
- **Error Level**: Failed extractions and reasons
- **Warning Level**: Fallback method usage

## 🛠️ Troubleshooting

### Common Issues

#### No Content Extracted
- Check if URL is accessible
- Verify HTML structure
- Try different extraction method
- Check for anti-bot measures

#### LLM Errors
- Verify API key is valid
- Check regional restrictions
- Monitor token usage
- Try different model

#### Performance Issues
- Enable caching
- Optimize patterns
- Use headless browser
- Implement rate limiting
