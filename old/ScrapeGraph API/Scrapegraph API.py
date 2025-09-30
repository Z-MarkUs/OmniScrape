#!/usr/bin/env python3
"""
ScrapeGraph API Implementation
Demonstrates how to use ScrapeGraph API for web scraping
"""

import os
from scrapegraph_py import Client
from scrapegraph_py.logger import sgai_logger


def scrape_with_scrapegraph(api_key: str, url: str, prompt: str = None):
    """
    Scrape a website using ScrapeGraph API
    
    Args:
        api_key: Your ScrapeGraph API key
        url: URL to scrape
        prompt: Custom prompt for data extraction
    
    Returns:
        Dictionary with scraping results
    """
    # Configure logging
    sgai_logger.set_logging(level="INFO")
    
    # Initialize client
    client = Client(api_key=api_key)
    
    try:
        # Use SmartScraper for intelligent data extraction
        response = client.smartscraper(
            website_url=url,
            user_prompt=prompt or "Extract all relevant information from this webpage"
        )
        
        return {
            'success': True,
            'data': response.get('result', {}),
            'request_id': response.get('request_id'),
            'reference_urls': response.get('reference_urls', [])
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'data': {}
        }
    
    finally:
        # Always close the client
        client.close()


def demo_scrapegraph():
    """Demo function showing ScrapeGraph API usage"""
    print("🤖 ScrapeGraph API Demo")
    print("=" * 30)
    
    # Get API key from environment
    api_key = os.getenv('SCRAPEGRAPH_API_KEY')
    if not api_key:
        print("❌ No API key found!")
        print("Please set SCRAPEGRAPH_API_KEY environment variable")
        print("Get your free API key at: https://scrapegraphai.com/")
        return
    
    # Test URLs
    test_urls = [
        "https://example.com",
        "https://httpbin.org/html"
    ]
    
    for url in test_urls:
        print(f"\n🔍 Scraping: {url}")
        
        # Extract basic information
        result = scrape_with_scrapegraph(
            api_key=api_key,
            url=url,
            prompt="Extract the main heading, description, and any links"
        )
        
        if result['success']:
            print("✅ Success!")
            print(f"📊 Data extracted: {len(str(result['data']))} characters")
            print(f"🆔 Request ID: {result['request_id']}")
            
            # Show some extracted data
            data = result['data']
            if isinstance(data, dict):
                for key, value in list(data.items())[:3]:  # Show first 3 items
                    print(f"  {key}: {str(value)[:100]}...")
        else:
            print(f"❌ Failed: {result['error']}")


if __name__ == "__main__":
    demo_scrapegraph()
