# Examples

This directory contains usage examples for the OmniScrape API and Labs functionality.

## 📁 Examples Overview

### Basic API Usage
- **article_extraction.py** - Extract articles from news websites
- **product_extraction.py** - Extract product information from e-commerce sites
- **batch_processing.py** - Process multiple URLs in batch

### Labs Examples
- **smart_scraper_example.py** - SmartScraperGraph usage
- **search_graph_example.py** - SearchGraph with Bing API
- **script_creator_example.py** - Generate Python scraping scripts

### Advanced Usage
- **custom_prompts.py** - Custom extraction prompts
- **proxy_rotation.py** - Using proxy rotation
- **error_handling.py** - Comprehensive error handling

## 🚀 Quick Start Examples

### Extract Article
```python
import requests

# Extract article from news website
response = requests.post(
    "http://localhost:8000/extract",
    json={
        "url": "https://example.com/news/article",
        "kind": "article",
        "llmMode": "AUTO"
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Title: {data['title']}")
    print(f"Author: {data['author']}")
    print(f"Content: {data['text'][:200]}...")
```

### Extract Product
```python
import requests

# Extract product information
response = requests.post(
    "http://localhost:8000/extract",
    json={
        "url": "https://example.com/product/123",
        "kind": "product",
        "llmMode": "AUTO"
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Product: {data['name']}")
    print(f"Price: {data['price']} {data['currency']}")
    print(f"Description: {data['description'][:200]}...")
```

### Use Labs SmartScraper
```python
import requests

# Use SmartScraperGraph with custom prompt
response = requests.post(
    "http://localhost:8000/labs/smart",
    json={
        "url": "https://example.com",
        "prompt": "Extract the main title, author, and key points from this article"
    }
)

if response.status_code == 200:
    result = response.json()
    if result["success"]:
        print("Extraction successful!")
        print(f"Data: {result['data']}")
        print(f"Token usage: {result['data']['token_usage']}")
    else:
        print(f"Error: {result['error']}")
```

## 🔧 Configuration Examples

### Environment Setup
```bash
# Required
export OPENAI_API_KEY="your_openai_api_key"

# Optional
export SCRAPEGRAPH_MODEL="gpt-4o-mini"
export BING_SEARCH_API_KEY="your_bing_api_key"
export MAX_RENDER_MS="15000"

# Proxy configuration
export HTTP_PROXY="http://proxy:8080"
export HTTPS_PROXY="https://proxy:8080"
```

### Python Configuration
```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
config = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "model": os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini"),
    "max_render_ms": int(os.getenv("MAX_RENDER_MS", "15000")),
    "proxy": {
        "http": os.getenv("HTTP_PROXY"),
        "https": os.getenv("HTTPS_PROXY")
    }
}
```

## 🧪 Testing Examples

### Unit Testing
```python
import pytest
import requests

def test_extract_article():
    response = requests.post(
        "http://localhost:8000/extract",
        json={
            "url": "https://httpbin.org/html",
            "kind": "article"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "text" in data

def test_labs_smart_scraper():
    response = requests.post(
        "http://localhost:8000/labs/smart",
        json={
            "url": "https://httpbin.org/html",
            "prompt": "Extract title"
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert "success" in result
```

### Integration Testing
```python
import pytest
import requests

@pytest.fixture
def api_client():
    return requests.Session()

def test_full_extraction_pipeline(api_client):
    # Test article extraction
    article_response = api_client.post(
        "http://localhost:8000/extract",
        json={"url": "https://httpbin.org/html", "kind": "article"}
    )
    assert article_response.status_code == 200
    
    # Test product extraction
    product_response = api_client.post(
        "http://localhost:8000/extract",
        json={"url": "https://httpbin.org/html", "kind": "product"}
    )
    assert product_response.status_code == 200
    
    # Test Labs functionality
    labs_response = api_client.post(
        "http://localhost:8000/labs/smart",
        json={"url": "https://httpbin.org/html", "prompt": "Extract title"}
    )
    assert labs_response.status_code == 200
```

## 📊 Monitoring Examples

### Health Check
```python
import requests

def check_health():
    response = requests.get("http://localhost:8000/health")
    if response.status_code == 200:
        print("Service is healthy!")
        return True
    else:
        print(f"Service is unhealthy: {response.status_code}")
        return False

# Run health check
if check_health():
    print("Ready to process requests")
else:
    print("Service not available")
```

### Performance Monitoring
```python
import time
import requests

def monitor_performance():
    start_time = time.time()
    
    response = requests.post(
        "http://localhost:8000/extract",
        json={"url": "https://example.com", "kind": "article"}
    )
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    print(f"Request completed in {execution_time:.2f} seconds")
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if "_execution_time" in data:
            print(f"Server execution time: {data['_execution_time']:.2f}s")
        if "_llm_usage" in data:
            print(f"Token usage: {data['_llm_usage']}")

# Monitor performance
monitor_performance()
```

## 🔒 Security Examples

### Input Validation
```python
import requests
import re

def validate_url(url):
    """Validate URL format"""
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return pattern.match(url) is not None

def safe_extract(url, kind="article"):
    """Safely extract content with validation"""
    if not validate_url(url):
        raise ValueError("Invalid URL format")
    
    if kind not in ["article", "product"]:
        raise ValueError("Kind must be 'article' or 'product'")
    
    response = requests.post(
        "http://localhost:8000/extract",
        json={"url": url, "kind": kind}
    )
    
    return response.json()

# Safe extraction
try:
    result = safe_extract("https://example.com/article")
    print("Extraction successful!")
except ValueError as e:
    print(f"Validation error: {e}")
except requests.RequestException as e:
    print(f"Request error: {e}")
```

## 🚀 Deployment Examples

### Docker Deployment
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install -e .

# Install Playwright browsers
RUN playwright install chromium

# Copy source code
COPY src/ src/

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "src/main.py"]
```

### Production Deployment
```bash
#!/bin/bash
# production_deploy.sh

# Set environment variables
export OPENAI_API_KEY="your_production_key"
export SCRAPEGRAPH_MODEL="gpt-4o-mini"
export MAX_RENDER_MS="15000"

# Install dependencies
pip install -e .[production]

# Run with production server
uvicorn src.api.api:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --access-log \
    --log-level info
```

## 📚 Additional Resources

- **API Documentation**: [../docs/api/](../docs/api/)
- **Labs Documentation**: [../docs/labs/](../docs/labs/)
- **Architecture Overview**: [../docs/architecture/](../docs/architecture/)
- **Main README**: [../README.md](../README.md)
