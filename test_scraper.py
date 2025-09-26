#!/usr/bin/env python3
"""
Simple test script for the Universal Web Scraper
"""

from universal_scraper import UniversalWebScraper, ScrapingMethod

def test_newspaper3k():
    """Test newspaper3k functionality"""
    print("🧪 Testing newspaper3k...")
    
    scraper = UniversalWebScraper()
    
    # Test with your existing URL
    url = "https://36kr.com/p/3482899443506050"
    result = scraper.scrape_url(url, ScrapingMethod.NEWSPAPER3K)
    
    if result.success:
        print("✅ newspaper3k test passed!")
        print(f"   Title: {result.data.get('title', 'N/A')[:50]}...")
        print(f"   Text length: {len(result.data.get('text', ''))}")
        print(f"   Keywords: {len(result.data.get('keywords', []))}")
    else:
        print(f"❌ newspaper3k test failed: {result.error}")
    
    scraper.close()

def test_auto_method():
    """Test automatic method selection"""
    print("\n🧪 Testing auto method selection...")
    
    scraper = UniversalWebScraper()
    
    url = "https://36kr.com/p/3482899443506050"
    result = scraper.scrape_url(url, ScrapingMethod.AUTO)
    
    if result.success:
        print(f"✅ Auto method test passed! Used: {result.method_used}")
    else:
        print(f"❌ Auto method test failed: {result.error}")
    
    scraper.close()

if __name__ == "__main__":
    print("🚀 Universal Web Scraper - Quick Test")
    print("=" * 40)
    
    test_newspaper3k()
    test_auto_method()
    
    print("\n✅ All tests completed!")
