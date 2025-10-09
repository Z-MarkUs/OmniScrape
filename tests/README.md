# Tests

This directory contains comprehensive test suites for the OmniScrape web scraping service.

## 📁 Test Structure

### `unit/` - Unit Tests
- **test_api.py** - API endpoint tests
- **test_pipeline.py** - Pipeline orchestration tests
- **test_fetcher.py** - Browser engine tests
- **test_extractors.py** - Extraction method tests
- **test_labs.py** - Labs functionality tests
- **test_schemas.py** - Data model validation tests

### `integration/` - Integration Tests
- **test_pipeline_integration.py** - Full pipeline tests
- **test_real_sites.py** - Real website extraction tests
- **test_labs_integration.py** - Labs API integration tests
- **test_performance.py** - Performance and load tests

### `fixtures/` - Test Data
- **sample_html/** - Sample HTML files for testing
- **mock_responses/** - Mock API responses
- **test_urls.txt** - Test URLs for various scenarios

## 🚀 Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Set up test environment
export OPENAI_API_KEY="test_key"
export SCRAPEGRAPH_MODEL="gpt-4o-mini"
```

### Basic Test Execution
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only

# Run with coverage
pytest --cov=src tests/

# Run with verbose output
pytest -v tests/
```

### Test Configuration
```bash
# Run tests with specific markers
pytest -m "not slow" tests/  # Skip slow tests
pytest -m "api" tests/       # Run only API tests
pytest -m "integration" tests/  # Run only integration tests

# Run tests in parallel
pytest -n auto tests/

# Run tests with specific output
pytest --tb=short tests/     # Short traceback
pytest --tb=no tests/        # No traceback
```

## 🧪 Unit Tests

### API Tests
```python
# tests/unit/test_api.py
import pytest
import httpx
from fastapi.testclient import TestClient
from src.api.api import app

client = TestClient(app)

def test_health_endpoint():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_extract_article():
    """Test article extraction endpoint"""
    response = client.post(
        "/extract",
        json={
            "url": "https://httpbin.org/html",
            "kind": "article"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "text" in data

def test_extract_product():
    """Test product extraction endpoint"""
    response = client.post(
        "/extract",
        json={
            "url": "https://httpbin.org/html",
            "kind": "product"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "price" in data
```

### Pipeline Tests
```python
# tests/unit/test_pipeline.py
import pytest
from src.core.pipeline import extract

@pytest.mark.asyncio
async def test_extract_article():
    """Test article extraction pipeline"""
    result = await extract(
        url="https://httpbin.org/html",
        kind="article",
        llm_mode="SD"
    )
    assert result is not None
    assert "title" in result
    assert "text" in result

@pytest.mark.asyncio
async def test_extract_product():
    """Test product extraction pipeline"""
    result = await extract(
        url="https://httpbin.org/html",
        kind="product",
        llm_mode="SD"
    )
    assert result is not None
    assert "name" in result
    assert "price" in result
```

### Fetcher Tests
```python
# tests/unit/test_fetcher.py
import pytest
from src.core.fetcher import fetch_rendered

@pytest.mark.asyncio
async def test_fetch_rendered():
    """Test HTML fetching"""
    html = await fetch_rendered("https://httpbin.org/html")
    assert html is not None
    assert "<html>" in html
    assert "</html>" in html

@pytest.mark.asyncio
async def test_fetch_with_stealth():
    """Test fetching with stealth measures"""
    html = await fetch_rendered(
        "https://httpbin.org/html",
        stealth=True
    )
    assert html is not None
```

## 🔗 Integration Tests

### Pipeline Integration
```python
# tests/integration/test_pipeline_integration.py
import pytest
from src.core.pipeline import extract

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_extraction_pipeline():
    """Test complete extraction pipeline"""
    # Test article extraction
    article_result = await extract(
        url="https://httpbin.org/html",
        kind="article",
        llm_mode="AUTO"
    )
    assert article_result is not None
    assert "title" in article_result
    
    # Test product extraction
    product_result = await extract(
        url="https://httpbin.org/html",
        kind="product",
        llm_mode="AUTO"
    )
    assert product_result is not None
    assert "name" in product_result
```

### Real Website Tests
```python
# tests/integration/test_real_sites.py
import pytest
from src.core.pipeline import extract

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_real_news_sites():
    """Test extraction from real news websites"""
    test_urls = [
        "https://httpbin.org/html",
        "https://example.com",
    ]
    
    for url in test_urls:
        result = await extract(
            url=url,
            kind="article",
            llm_mode="SD"
        )
        assert result is not None
        assert "title" in result
```

### Labs Integration
```python
# tests/integration/test_labs_integration.py
import pytest
import httpx
from fastapi.testclient import TestClient
from src.api.api import app

client = TestClient(app)

@pytest.mark.integration
def test_labs_smart_scraper():
    """Test SmartScraperGraph via Labs API"""
    response = client.post(
        "/labs/smart",
        json={
            "url": "https://httpbin.org/html",
            "prompt": "Extract the title and main content"
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert "success" in result

@pytest.mark.integration
def test_labs_script_creator():
    """Test ScriptCreatorGraph via Labs API"""
    response = client.post(
        "/labs/script",
        json={
            "url": "https://httpbin.org/html",
            "prompt": "Create a Python script to extract the title"
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert "success" in result
```

## 📊 Performance Tests

### Load Testing
```python
# tests/integration/test_performance.py
import pytest
import asyncio
import time
from src.core.pipeline import extract

@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_extractions():
    """Test concurrent extraction performance"""
    urls = [
        "https://httpbin.org/html",
        "https://httpbin.org/json",
        "https://example.com"
    ]
    
    start_time = time.time()
    
    tasks = [
        extract(url=url, kind="article", llm_mode="SD")
        for url in urls
    ]
    
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    assert len(results) == len(urls)
    assert execution_time < 30  # Should complete within 30 seconds
    
    for result in results:
        assert result is not None
        assert "title" in result
```

### Memory Usage Tests
```python
# tests/integration/test_memory.py
import pytest
import psutil
import os
from src.core.pipeline import extract

@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage():
    """Test memory usage during extraction"""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Perform multiple extractions
    for _ in range(10):
        await extract(
            url="https://httpbin.org/html",
            kind="article",
            llm_mode="SD"
        )
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # Memory increase should be reasonable (less than 100MB)
    assert memory_increase < 100 * 1024 * 1024
```

## 🔧 Test Configuration

### pytest.ini
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    slow: Slow running tests
    api: API tests
    pipeline: Pipeline tests
    fetcher: Fetcher tests
    extractors: Extractor tests
    labs: Labs tests
```

### conftest.py
```python
# tests/conftest.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from src.api.api import app

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_html():
    """Sample HTML content for testing"""
    return """
    <html>
        <head>
            <title>Test Article</title>
        </head>
        <body>
            <h1>Test Article Title</h1>
            <p>This is a test article content.</p>
            <img src="test.jpg" alt="Test image">
        </body>
    </html>
    """

@pytest.fixture
def sample_product_html():
    """Sample product HTML content for testing"""
    return """
    <html>
        <head>
            <title>Test Product</title>
        </head>
        <body>
            <h1>Test Product Name</h1>
            <p class="price">$19.99</p>
            <p>This is a test product description.</p>
            <img src="product.jpg" alt="Product image">
        </body>
    </html>
    """
```

## 🚀 Continuous Integration

### GitHub Actions
```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.10
    
    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## 📚 Additional Resources

- **API Documentation**: [../docs/api/](../docs/api/)
- **Architecture Overview**: [../docs/architecture/](../docs/architecture/)
- **Main README**: [../README.md](../README.md)
