# Labs Documentation

This directory contains comprehensive documentation for the OmniScrape Labs - an interactive testing environment for ScrapeGraphAI capabilities.

## 🧪 Labs Overview

The Labs page provides a comprehensive testing environment for all ScrapeGraphAI graph types, allowing you to experiment with different extraction methods and configurations.

**Access**: [http://localhost:8000/labs](http://localhost:8000/labs)

## 🔬 Available Graphs

### 1. SmartScraperGraph
**Purpose**: Single-page scraper with custom prompts

**Features**:
- Custom extraction prompts
- Real-time token usage tracking
- JSON output formatting
- Error handling

**Use Cases**:
- Article extraction with specific requirements
- Product information extraction
- Custom data extraction from any webpage

**Example Prompt**:
```
Extract the main title, author, publication date, and key points from this article. 
Include any relevant images and links.
```

### 2. SearchGraph
**Purpose**: Multi-page scraper using search engine results

**Features**:
- Search query-based extraction
- Configurable result count (1-10)
- Batch processing of multiple pages
- Search engine integration

**Requirements**:
- Bing Search API key (`BING_SEARCH_API_KEY`)

**Use Cases**:
- Research on trending topics
- Competitive analysis
- News aggregation
- Market research

**Example Usage**:
- Query: "artificial intelligence news"
- Count: 5
- Prompt: "Extract title, summary, and publication date from each article"

### 3. SpeechGraph
**Purpose**: Audio generation from web content

**Features**:
- Text-to-speech conversion
- Audio file generation
- Content extraction + audio synthesis
- Multiple voice options

**Requirements**:
- OpenAI TTS API access
- Audio processing libraries

**Use Cases**:
- Podcast content generation
- Accessibility features
- Audio summaries
- Voice-over content

**Example Usage**:
- URL: News article
- Prompt: "Convert the main article content to speech"

### 4. ScriptCreatorGraph
**Purpose**: Python script generation for web scraping

**Features**:
- Automated script creation
- Custom library selection
- Code optimization
- Error handling in generated scripts

**Configuration**:
- Library: `requests`, `beautifulsoup4`, `selenium`
- Output format: Executable Python scripts

**Use Cases**:
- Automated scraping script generation
- Code learning and examples
- Custom extraction tools
- Rapid prototyping

**Example Output**:
```python
import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    title = soup.find('h1').text
    content = soup.find('div', class_='content').text
    
    return {
        'title': title,
        'content': content
    }
```

### 5. SmartScraperMultiGraph
**Purpose**: Multi-page extraction with single prompt

**Features**:
- Batch URL processing
- Consistent extraction across pages
- Parallel processing
- Aggregated results

**Use Cases**:
- Multi-page article series
- Product catalog scraping
- News site aggregation
- Content migration

**Example Usage**:
- URLs: Multiple article URLs
- Prompt: "Extract title, author, and main content from each page"

### 6. ScriptCreatorMultiGraph
**Purpose**: Multi-page Python script generation

**Features**:
- Multi-source script generation
- Batch processing capabilities
- Error handling across multiple sources
- Optimized code structure

**Use Cases**:
- Multi-site scraping tools
- Data aggregation scripts
- Content migration tools
- Automated reporting systems

## 🚀 Getting Started

### Prerequisites
1. **OpenAI API Key**: Required for all LLM-powered graphs
2. **Bing Search API Key**: Required for SearchGraph (optional)
3. **Running Server**: OmniScrape server must be running

### Basic Usage
1. Navigate to [http://localhost:8000/labs](http://localhost:8000/labs)
2. Select a graph type
3. Fill in the required fields
4. Click "Run [GraphName]"
5. View results in JSON format

### Configuration
```bash
# Required
export OPENAI_API_KEY="your_openai_api_key"

# Optional
export BING_SEARCH_API_KEY="your_bing_api_key"
export SCRAPEGRAPH_MODEL="gpt-4o-mini"
```

## 📊 API Endpoints

### SmartScraperGraph
```bash
curl -X POST "http://localhost:8000/labs/smart" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "prompt": "Extract title and content"
  }'
```

### SearchGraph
```bash
curl -X POST "http://localhost:8000/labs/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "count": 5,
    "prompt": "Extract key information"
  }'
```

### SpeechGraph
```bash
curl -X POST "http://localhost:8000/labs/speech" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "prompt": "Convert to speech"
  }'
```

### ScriptCreatorGraph
```bash
curl -X POST "http://localhost:8000/labs/script" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "prompt": "Create scraping script"
  }'
```

### Multi-Page Graphs
```bash
curl -X POST "http://localhost:8000/labs/multi" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example1.com", "https://example2.com"],
    "prompt": "Extract from all pages"
  }'
```

## 🔧 Advanced Configuration

### Custom Prompts
Design effective prompts for better extraction:

**Good Prompt Example**:
```
Extract the following information from this webpage:
- Title (main heading)
- Author (byline or author field)
- Publication date (in YYYY-MM-DD format)
- Main content (all paragraphs, preserve structure)
- Images (all image URLs)
- Links (important external links)

Format the output as JSON with these exact field names.
```

**Bad Prompt Example**:
```
Get the stuff from this page
```

### Token Optimization
Monitor and optimize token usage:

```json
{
  "token_usage": {
    "prompt_tokens": 150,
    "completion_tokens": 300,
    "total_tokens": 450,
    "model": "gpt-4o-mini"
  }
}
```

### Error Handling
Common errors and solutions:

#### Regional Restrictions
```json
{
  "success": false,
  "error": "Country, region, or territory not supported"
}
```
**Solution**: Use VPN or different API key

#### Missing API Keys
```json
{
  "success": false,
  "error": "Bing Search API key missing: set BING_SEARCH_API_KEY"
}
```
**Solution**: Set required environment variables

#### Invalid URLs
```json
{
  "success": false,
  "error": "Failed to fetch URL"
}
```
**Solution**: Check URL accessibility and format

## 🧪 Testing Strategies

### Unit Testing
Test individual graph functionality:

```python
import requests

def test_smart_scraper():
    response = requests.post(
        "http://localhost:8000/labs/smart",
        json={
            "url": "https://httpbin.org/html",
            "prompt": "Extract title"
        }
    )
    assert response.status_code == 200
    assert response.json()["success"] == True
```

### Integration Testing
Test multiple graphs together:

```python
def test_labs_integration():
    graphs = ["smart", "script", "speech"]
    for graph in graphs:
        response = requests.post(f"http://localhost:8000/labs/{graph}", ...)
        assert response.status_code == 200
```

### Performance Testing
Monitor response times and resource usage:

```python
import time

def test_performance():
    start_time = time.time()
    response = requests.post("http://localhost:8000/labs/smart", ...)
    end_time = time.time()
    
    assert end_time - start_time < 10  # Should complete within 10 seconds
```

## 📈 Monitoring and Analytics

### Usage Metrics
Track graph usage patterns:
- Most used graphs
- Average response times
- Success/failure rates
- Token consumption

### Performance Metrics
Monitor system performance:
- Memory usage
- CPU utilization
- Network bandwidth
- Database connections

### Error Tracking
Track and analyze errors:
- Error frequency
- Error types
- Failed URLs
- Recovery strategies

## 🛠️ Development

### Adding New Graphs
1. Create graph function in `src/labs/labs_graphs.py`
2. Add API endpoint in `src/api/api.py`
3. Update UI in Labs page
4. Add tests and documentation

### Custom Graph Example
```python
def run_custom_graph(url: str, prompt: str) -> Dict[str, Any]:
    """Custom graph implementation"""
    clear_token_usage()
    
    config = get_base_config()
    # Add custom configuration
    
    try:
        graph = CustomGraph(
            prompt=prompt,
            source=url,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "CustomGraph"
        }
    except Exception as e:
        return {"error": str(e)}
```

## 🔒 Security Considerations

### API Key Management
- Store keys in environment variables
- Never commit keys to version control
- Rotate keys regularly
- Monitor key usage

### Input Validation
- Validate URLs before processing
- Sanitize user prompts
- Limit request size
- Implement rate limiting

### Output Sanitization
- Validate extracted content
- Remove sensitive information
- Filter malicious content
- Implement content policies

## 📚 Additional Resources

- **ScrapeGraphAI Documentation**: [Official Docs](https://scrapegraph-ai.readthedocs.io/)
- **OpenAI API Reference**: [API Docs](https://platform.openai.com/docs)
- **Bing Search API**: [Microsoft Docs](https://docs.microsoft.com/en-us/bing/search-apis/)
- **Main Project README**: [../README.md](../README.md)
