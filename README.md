# Universal Web Scraping Tool

A powerful web scraping tool that combines **ScrapeGraph API** and **newspaper3k** to provide comprehensive web scraping capabilities with AI-powered extraction and traditional article parsing.

## 🌟 Features

- **AI-Powered Extraction**: Uses ScrapeGraph API for intelligent, natural language-based data extraction
- **Traditional Article Parsing**: Leverages newspaper3k for reliable news article extraction
- **Automatic Method Selection**: Intelligently chooses the best scraping method based on URL and requirements
- **Multiple Scraping Methods**: Support for SmartScraper, SearchScraper, SmartCrawler, Markdownify, and newspaper3k
- **Comprehensive Error Handling**: Robust fallback mechanisms and detailed error reporting
- **Batch Processing**: Scrape multiple URLs efficiently
- **Structured Output**: Consistent data format across all methods

## 🚀 Quick Start

### Installation

```bash
pip install newspaper3k scrapegraph-py lxml_html_clean
```

### Basic Usage

```python
from universal_scraper import UniversalWebScraper, ScrapingMethod

# Initialize scraper
scraper = UniversalWebScraper()

# Scrape a single URL (auto-selects best method)
result = scraper.scrape_url("https://example.com")

if result.success:
    print(f"Title: {result.data.get('title')}")
    print(f"Method used: {result.method_used}")
    print(f"Execution time: {result.execution_time:.2f}s")
else:
    print(f"Error: {result.error}")

scraper.close()
```

### With ScrapeGraph API Key

```python
import os
from universal_scraper import UniversalWebScraper, ScrapingMethod

# Set your API key
os.environ['SCRAPEGRAPH_API_KEY'] = 'your-api-key-here'

scraper = UniversalWebScraper()

# Use AI-powered extraction
result = scraper.scrape_url(
    url="https://example.com",
    method=ScrapingMethod.SCRAPEGRAPH_SMART,
    prompt="Extract product name, price, and description"
)

scraper.close()
```

## 📋 Available Scraping Methods

### ScrapeGraph API Methods (Requires API Key)

1. **SmartScraper**: AI-powered extraction from single pages
2. **SearchScraper**: Search and extract data across the web
3. **SmartCrawler**: Crawl entire websites with depth control
4. **Markdownify**: Convert web content to clean Markdown

### Traditional Methods

5. **newspaper3k**: Reliable article extraction with NLP analysis
6. **AUTO**: Automatically selects the best method

## 🔧 Configuration

### Environment Variables

```bash
export SCRAPEGRAPH_API_KEY="your-api-key-here"
```

### Getting ScrapeGraph API Key

1. Visit [ScrapeGraphAI](https://scrapegraphai.com/)
2. Sign up for a free account
3. Get your API key from the dashboard
4. Set it as an environment variable

## 📊 Data Structure

All scraping methods return a `ScrapingResult` object with:

```python
@dataclass
class ScrapingResult:
    url: str                    # Original URL
    method_used: str           # Method that was used
    success: bool              # Whether scraping succeeded
    data: Dict[str, Any]       # Extracted data
    error: Optional[str]       # Error message if failed
    execution_time: float      # Time taken in seconds
    metadata: Dict[str, Any]   # Additional metadata
```

### newspaper3k Data Structure

```python
{
    'title': 'Article Title',
    'authors': ['Author 1', 'Author 2'],
    'publish_date': '2024-01-01T00:00:00',
    'text': 'Full article text...',
    'summary': 'Article summary...',
    'keywords': ['keyword1', 'keyword2'],
    'images': ['image1.jpg', 'image2.jpg'],
    'videos': ['video1.mp4'],
    'url': 'https://example.com/article',
    'top_image': 'https://example.com/image.jpg',
    'html': '<html>...</html>'
}
```

## 🎯 Use Cases

### 1. News Article Extraction

```python
scraper = UniversalWebScraper()
result = scraper.scrape_url("https://news-site.com/article", ScrapingMethod.NEWSPAPER3K)

if result.success:
    article_data = result.data
    print(f"Title: {article_data['title']}")
    print(f"Authors: {', '.join(article_data['authors'])}")
    print(f"Summary: {article_data['summary']}")
```

### 2. E-commerce Product Data

```python
# Requires ScrapeGraph API key
result = scraper.scrape_url(
    url="https://shop.com/product",
    method=ScrapingMethod.SCRAPEGRAPH_SMART,
    prompt="Extract product name, price, description, availability, and ratings"
)
```

### 3. Batch Processing

```python
urls = [
    "https://site1.com/article1",
    "https://site2.com/article2",
    "https://site3.com/article3"
]

results = scraper.scrape_multiple_urls(urls, ScrapingMethod.AUTO)
successful_count = sum(1 for r in results if r.success)
print(f"Successfully scraped {successful_count}/{len(urls)} URLs")
```

### 4. Structured Data Extraction

```python
result = scraper.scrape_url("https://example.com", ScrapingMethod.AUTO)

if result.success:
    structured_data = {
        'title': result.data.get('title'),
        'content_length': len(result.data.get('text', '')),
        'keywords': result.data.get('keywords', [])[:5],
        'scraping_method': result.method_used,
        'execution_time': result.execution_time
    }
    print(json.dumps(structured_data, indent=2))
```

## 🛠️ Advanced Usage

### Custom Prompts for ScrapeGraph

```python
result = scraper.scrape_url(
    url="https://company.com/about",
    method=ScrapingMethod.SCRAPEGRAPH_SMART,
    prompt="Extract company name, founding year, headquarters location, and main products"
)
```

### Error Handling

```python
try:
    result = scraper.scrape_url(url, ScrapingMethod.AUTO)
    
    if not result.success:
        print(f"Scraping failed: {result.error}")
        # Try fallback method
        fallback_result = scraper.scrape_url(url, ScrapingMethod.NEWSPAPER3K)
        
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Method Selection Logic

The `AUTO` method selects the best approach based on:

- **URL patterns**: News sites → newspaper3k
- **Custom prompts**: Present → ScrapeGraph SmartScraper
- **API availability**: ScrapeGraph available → SmartScraper
- **Fallback**: Always falls back to newspaper3k

## 📁 Project Structure

```
PythonProject1/
├── universal_scraper.py          # Main scraper implementation
├── demo_universal_scraper.py    # Comprehensive demo
├── test_scraper.py              # Quick test script
├── ScrapeGraph API/
│   └── Scrapegraph API.py       # ScrapeGraph API examples
├── newspaper3k/
│   └── newspaper3k_demo_1.py    # newspaper3k examples
└── README.md                     # This file
```

## 🧪 Testing

Run the test script to verify everything works:

```bash
python3 test_scraper.py
```

Run the comprehensive demo:

```bash
python3 demo_universal_scraper.py
```

## 🔍 Comparison: ScrapeGraph API vs newspaper3k

| Feature | ScrapeGraph API | newspaper3k |
|---------|----------------|-------------|
| **AI-Powered** | ✅ Yes | ❌ No |
| **Natural Language Prompts** | ✅ Yes | ❌ No |
| **Dynamic Content** | ✅ Yes | ⚠️ Limited |
| **News Articles** | ✅ Good | ✅ Excellent |
| **Structured Data** | ✅ Excellent | ⚠️ Basic |
| **API Key Required** | ✅ Yes | ❌ No |
| **Cost** | 💰 Pay per use | 🆓 Free |
| **Speed** | ⚡ Fast | 🐌 Slower |
| **Reliability** | ✅ High | ✅ High |

## 🚨 Important Notes

1. **Rate Limits**: ScrapeGraph API has rate limits based on your plan
2. **Costs**: ScrapeGraph API charges per page scraped
3. **Legal Compliance**: Always respect robots.txt and website terms of service
4. **Error Handling**: Implement proper error handling for production use
5. **API Key Security**: Never commit API keys to version control

## 🤝 Contributing

Feel free to contribute by:

1. Adding new scraping methods
2. Improving error handling
3. Adding more use case examples
4. Optimizing performance
5. Adding tests

## 📄 License

This project is open source. Please check individual library licenses:
- [newspaper3k](https://github.com/codelucas/newspaper)
- [ScrapeGraph API](https://scrapegraphai.com/)

## 🆘 Support

- **ScrapeGraph API**: [Documentation](https://docs.scrapegraphai.com/)
- **newspaper3k**: [GitHub](https://github.com/codelucas/newspaper)
- **Issues**: Create an issue in this repository

---

**Happy Scraping! 🕷️**
