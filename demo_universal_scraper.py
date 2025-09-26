#!/usr/bin/env python3
"""
Demo script for the Universal Web Scraper
Shows different use cases and capabilities
"""

import os
import json
from universal_scraper import UniversalWebScraper, ScrapingMethod


def demo_basic_scraping():
    """Demo basic scraping functionality"""
    print("🔍 Demo 1: Basic Web Scraping")
    print("=" * 40)
    
    scraper = UniversalWebScraper()
    
    # Test with your existing URL
    url = "https://36kr.com/p/3482899443506050"
    print(f"Scraping: {url}")
    
    result = scraper.scrape_url(url, ScrapingMethod.AUTO)
    
    if result.success:
        print(f"✅ Success! Method used: {result.method_used}")
        print(f"⏱️ Time taken: {result.execution_time:.2f}s")
        
        data = result.data
        print(f"📰 Title: {data.get('title', 'N/A')}")
        print(f"👤 Authors: {', '.join(data.get('authors', []))}")
        print(f"📝 Text length: {len(data.get('text', ''))} characters")
        print(f"🏷️ Keywords: {', '.join(data.get('keywords', [])[:5])}")
        
        if data.get('summary'):
            print(f"📋 Summary: {data['summary'][:200]}...")
    else:
        print(f"❌ Failed: {result.error}")
    
    scraper.close()
    print()


def demo_scrapegraph_features():
    """Demo ScrapeGraph API specific features (requires API key)"""
    print("🤖 Demo 2: ScrapeGraph API Features")
    print("=" * 40)
    
    # Check if API key is available
    api_key = os.getenv('SCRAPEGRAPH_API_KEY')
    if not api_key:
        print("⚠️ No ScrapeGraph API key found. Set SCRAPEGRAPH_API_KEY environment variable to test.")
        print("   You can get a free API key at: https://scrapegraphai.com/")
        return
    
    scraper = UniversalWebScraper(api_key)
    
    # Test different ScrapeGraph methods
    test_url = "https://example.com"
    
    methods_to_test = [
        (ScrapingMethod.SCRAPEGRAPH_SMART, "Extract the main heading and description"),
        (ScrapingMethod.SCRAPEGRAPH_MARKDOWN, None),
    ]
    
    for method, prompt in methods_to_test:
        print(f"Testing {method.value}...")
        try:
            result = scraper.scrape_url(test_url, method, prompt)
            if result.success:
                print(f"✅ {method.value} succeeded")
                if method == ScrapingMethod.SCRAPEGRAPH_MARKDOWN:
                    print(f"📄 Markdown length: {len(result.data)} characters")
                else:
                    print(f"📊 Data keys: {list(result.data.keys())}")
            else:
                print(f"❌ {method.value} failed: {result.error}")
        except Exception as e:
            print(f"❌ {method.value} error: {e}")
        print()
    
    scraper.close()


def demo_comparison():
    """Demo comparing different scraping methods"""
    print("⚖️ Demo 3: Method Comparison")
    print("=" * 40)
    
    scraper = UniversalWebScraper()
    url = "https://36kr.com/p/3482899443506050"
    
    methods = [ScrapingMethod.NEWSPAPER3K]
    
    # Add ScrapeGraph methods if API key is available
    if os.getenv('SCRAPEGRAPH_API_KEY'):
        methods.extend([
            ScrapingMethod.SCRAPEGRAPH_SMART,
            ScrapingMethod.SCRAPEGRAPH_MARKDOWN
        ])
    
    results = {}
    
    for method in methods:
        print(f"Testing {method.value}...")
        try:
            result = scraper.scrape_url(url, method)
            results[method.value] = {
                'success': result.success,
                'time': result.execution_time,
                'data_size': len(str(result.data)),
                'error': result.error
            }
            
            if result.success:
                print(f"✅ {method.value}: {result.execution_time:.2f}s, {len(str(result.data))} chars")
            else:
                print(f"❌ {method.value}: {result.error}")
                
        except Exception as e:
            print(f"❌ {method.value}: {e}")
            results[method.value] = {'success': False, 'error': str(e)}
    
    # Summary
    print("\n📊 Summary:")
    for method, stats in results.items():
        if stats['success']:
            print(f"  {method}: ✅ {stats['time']:.2f}s")
        else:
            print(f"  {method}: ❌ {stats['error']}")
    
    scraper.close()
    print()


def demo_multiple_urls():
    """Demo scraping multiple URLs"""
    print("🔗 Demo 4: Multiple URL Scraping")
    print("=" * 40)
    
    scraper = UniversalWebScraper()
    
    urls = [
        "https://36kr.com/p/3482899443506050",
        "https://example.com",
        "https://httpbin.org/html"
    ]
    
    print(f"Scraping {len(urls)} URLs...")
    results = scraper.scrape_multiple_urls(urls, ScrapingMethod.AUTO)
    
    successful = sum(1 for r in results if r.success)
    print(f"✅ Successfully scraped {successful}/{len(urls)} URLs")
    
    for i, result in enumerate(results):
        print(f"  {i+1}. {result.url}: {'✅' if result.success else '❌'} ({result.method_used})")
    
    scraper.close()
    print()


def demo_structured_extraction():
    """Demo structured data extraction"""
    print("📋 Demo 5: Structured Data Extraction")
    print("=" * 40)
    
    scraper = UniversalWebScraper()
    
    # Example: Extract specific information from a news article
    url = "https://36kr.com/p/3482899443506050"
    
    # Try with newspaper3k first
    result = scraper.scrape_url(url, ScrapingMethod.NEWSPAPER3K)
    
    if result.success:
        data = result.data
        
        # Create structured output
        structured_data = {
            'article_info': {
                'title': data.get('title'),
                'authors': data.get('authors', []),
                'publish_date': data.get('publish_date'),
                'url': data.get('url')
            },
            'content': {
                'text_length': len(data.get('text', '')),
                'summary': data.get('summary'),
                'keywords': data.get('keywords', [])[:10]  # Top 10 keywords
            },
            'media': {
                'images': len(data.get('images', [])),
                'videos': len(data.get('videos', []))
            },
            'metadata': {
                'scraping_method': result.method_used,
                'execution_time': result.execution_time
            }
        }
        
        print("📊 Structured Data Extracted:")
        print(json.dumps(structured_data, indent=2, ensure_ascii=False))
    else:
        print(f"❌ Failed to extract data: {result.error}")
    
    scraper.close()
    print()


def main():
    """Run all demos"""
    print("🚀 Universal Web Scraper - Comprehensive Demo")
    print("=" * 60)
    print()
    
    try:
        demo_basic_scraping()
        demo_scrapegraph_features()
        demo_comparison()
        demo_multiple_urls()
        demo_structured_extraction()
        
        print("🎉 All demos completed successfully!")
        print("\n💡 Tips:")
        print("  - Set SCRAPEGRAPH_API_KEY environment variable for AI-powered scraping")
        print("  - Use ScrapingMethod.AUTO for automatic method selection")
        print("  - Check the ScrapingResult object for detailed information")
        print("  - Handle errors gracefully in production code")
        
    except KeyboardInterrupt:
        print("\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")


if __name__ == "__main__":
    main()
