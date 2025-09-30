#!/usr/bin/env python3
"""
Universal Web Scraper Demo - Showing TRUE UNIVERSALITY
Demonstrates how ScrapeGraph API + newspaper3k creates a truly universal scraper
"""

import os
from enhanced_universal_scraper import EnhancedUniversalWebScraper, ScrapingMethod


def demo_universal_capabilities():
    """Demo the truly universal capabilities"""
    print("🌍 UNIVERSAL WEB SCRAPER - TRUE UNIVERSALITY DEMO")
    print("=" * 60)
    print()
    
    # Initialize scraper
    scraper = EnhancedUniversalWebScraper()
    
    # Check if ScrapeGraph API is available
    has_scrapegraph = scraper.scrapegraph_client is not None
    print(f"🔧 ScrapeGraph API Available: {'✅ YES' if has_scrapegraph else '❌ NO'}")
    print(f"📋 Available Methods: {', '.join(scraper.get_available_methods())}")
    print()
    
    if not has_scrapegraph:
        print("⚠️  WITHOUT ScrapeGraph API: Limited to newspaper3k (articles only)")
        print("💡 WITH ScrapeGraph API: Truly universal (any website)")
        print()
    
    # Test different types of websites
    test_cases = [
        {
            'name': 'News Article',
            'url': 'https://36kr.com/p/3482899443506050',
            'expected_method': 'newspaper3k',
            'reason': 'News site without custom prompt → newspaper3k (optimized)'
        },
        {
            'name': 'E-commerce Product',
            'url': 'https://example.com/product',
            'expected_method': 'scrapegraph_smart',
            'reason': 'E-commerce → ScrapeGraph (universal)',
            'prompt': 'Extract product name, price, and description'
        },
        {
            'name': 'Social Media Profile',
            'url': 'https://example.com/profile',
            'expected_method': 'scrapegraph_smart',
            'reason': 'Social media → ScrapeGraph (universal)',
            'prompt': 'Extract profile information and recent posts'
        },
        {
            'name': 'Documentation Site',
            'url': 'https://example.com/docs',
            'expected_method': 'scrapegraph_smart',
            'reason': 'Documentation → ScrapeGraph (universal)',
            'prompt': 'Extract all headings and code examples'
        },
        {
            'name': 'Forum Discussion',
            'url': 'https://example.com/forum',
            'expected_method': 'scrapegraph_smart',
            'reason': 'Forum → ScrapeGraph (universal)',
            'prompt': 'Extract discussion topics and user comments'
        },
        {
            'name': 'Complex Dynamic Site',
            'url': 'https://example.com/dashboard',
            'expected_method': 'scrapegraph_smart',
            'reason': 'Dynamic content → ScrapeGraph (universal)',
            'prompt': 'Extract all data tables and charts'
        }
    ]
    
    print("🧪 TESTING UNIVERSAL CAPABILITIES")
    print("=" * 40)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Expected: {test_case['expected_method']}")
        print(f"   Reason: {test_case['reason']}")
        
        if 'prompt' in test_case:
            print(f"   Prompt: {test_case['prompt']}")
        
        # Test method selection
        selected_method = scraper.method_selector.select_method(
            test_case['url'], 
            test_case.get('prompt'),
            scraper.scrapegraph_client is not None
        )
        
        print(f"   Selected: {selected_method.value}")
        
        if selected_method.value == test_case['expected_method']:
            print("   ✅ CORRECT SELECTION")
        else:
            print(f"   ⚠️  Different selection (expected {test_case['expected_method']})")
        
        # If we have ScrapeGraph, show the universal capabilities
        if has_scrapegraph and selected_method.value.startswith('scrapegraph'):
            print("   🌍 UNIVERSAL: Can extract ANY data from ANY website")
        elif selected_method.value == 'newspaper3k':
            print("   📰 SPECIALIZED: Optimized for news articles")
    
    print("\n" + "=" * 60)
    print("🎯 UNIVERSALITY SUMMARY")
    print("=" * 60)
    
    if has_scrapegraph:
        print("✅ TRULY UNIVERSAL:")
        print("   • ScrapeGraph API handles ANY website type")
        print("   • E-commerce, social media, forums, documentation")
        print("   • Dynamic content, JavaScript-heavy sites")
        print("   • Custom data extraction with natural language")
        print("   • Structured data, forms, complex layouts")
        print()
        print("✅ OPTIMIZED FOR ARTICLES:")
        print("   • newspaper3k for news sites (free, optimized)")
        print("   • Built-in NLP analysis")
        print("   • Automatic author, date, keyword extraction")
        print()
        print("🔄 INTELLIGENT SWITCHING:")
        print("   • News articles → newspaper3k (free)")
        print("   • Everything else → ScrapeGraph (universal)")
        print("   • Custom prompts → ScrapeGraph (AI-powered)")
    else:
        print("⚠️  LIMITED WITHOUT ScrapeGraph API:")
        print("   • Only newspaper3k available")
        print("   • Limited to news articles")
        print("   • Cannot handle dynamic content")
        print("   • Cannot extract custom data")
        print()
        print("💡 TO ACHIEVE TRUE UNIVERSALITY:")
        print("   • Get ScrapeGraph API key")
        print("   • Set SCRAPEGRAPH_API_KEY environment variable")
        print("   • Unlock universal scraping capabilities")
    
    scraper.close()


def demo_scrapegraph_universality():
    """Demo ScrapeGraph API universality"""
    print("\n🚀 SCRAPEGRAPH API UNIVERSALITY DEMO")
    print("=" * 50)
    
    api_key = os.getenv('SCRAPEGRAPH_API_KEY')
    if not api_key:
        print("❌ No ScrapeGraph API key found")
        print("💡 Get your free API key at: https://scrapegraphai.com/")
        print("🔧 Set environment variable: export SCRAPEGRAPH_API_KEY='your-key'")
        return
    
    scraper = EnhancedUniversalWebScraper(api_key)
    
    # Show different ScrapeGraph methods for different use cases
    scrapegraph_methods = [
        {
            'method': ScrapingMethod.SCRAPEGRAPH_SMART,
            'description': 'AI-powered extraction from any webpage',
            'use_cases': ['E-commerce products', 'Social media profiles', 'Any website data']
        },
        {
            'method': ScrapingMethod.SCRAPEGRAPH_SEARCH,
            'description': 'Search and extract data across the entire web',
            'use_cases': ['Market research', 'Competitive analysis', 'Brand monitoring']
        },
        {
            'method': ScrapingMethod.SCRAPEGRAPH_CRAWLER,
            'description': 'Crawl entire websites with intelligent depth control',
            'use_cases': ['Site mapping', 'Documentation analysis', 'Competitor intelligence']
        },
        {
            'method': ScrapingMethod.SCRAPEGRAPH_MARKDOWN,
            'description': 'Convert any webpage to clean Markdown',
            'use_cases': ['Content migration', 'LLM preparation', 'Documentation']
        }
    ]
    
    print("🔧 SCRAPEGRAPH API METHODS:")
    for i, method_info in enumerate(scrapegraph_methods, 1):
        print(f"\n{i}. {method_info['method'].value.upper()}")
        print(f"   Description: {method_info['description']}")
        print(f"   Use Cases: {', '.join(method_info['use_cases'])}")
    
    print("\n🌍 UNIVERSAL CAPABILITIES:")
    print("✅ Any website type (e-commerce, social, forums, docs)")
    print("✅ Dynamic content (JavaScript, React, Angular)")
    print("✅ Natural language data extraction")
    print("✅ Structured data output")
    print("✅ Custom prompts and queries")
    print("✅ Complex layouts and forms")
    print("✅ Real-time data extraction")
    
    scraper.close()


def demo_method_comparison():
    """Compare methods and show when to use each"""
    print("\n⚖️  METHOD COMPARISON & SELECTION")
    print("=" * 40)
    
    print("📊 WHEN TO USE EACH METHOD:")
    print()
    
    print("📰 NEWSPAPER3K:")
    print("   ✅ News articles and blog posts")
    print("   ✅ Free to use (no API costs)")
    print("   ✅ Built-in NLP analysis")
    print("   ✅ Reliable and stable")
    print("   ❌ Limited to article content")
    print("   ❌ Cannot handle dynamic content")
    print("   ❌ No custom data extraction")
    print()
    
    print("🤖 SCRAPEGRAPH API:")
    print("   ✅ ANY website type")
    print("   ✅ Dynamic content and JavaScript")
    print("   ✅ Natural language queries")
    print("   ✅ Custom data extraction")
    print("   ✅ Structured data output")
    print("   ✅ Real-time processing")
    print("   ❌ Requires API key")
    print("   ❌ Pay per use")
    print()
    
    print("🔄 INTELLIGENT SELECTION:")
    print("   • News sites + no custom prompt → newspaper3k")
    print("   • Everything else → ScrapeGraph")
    print("   • Custom prompts → ScrapeGraph")
    print("   • Dynamic content → ScrapeGraph")
    print("   • Cost optimization → newspaper3k for articles")


def main():
    """Run the universal demo"""
    try:
        demo_universal_capabilities()
        demo_scrapegraph_universality()
        demo_method_comparison()
        
        print("\n🎉 UNIVERSAL DEMO COMPLETED!")
        print("=" * 40)
        print("💡 KEY TAKEAWAY:")
        print("   With ScrapeGraph API + newspaper3k:")
        print("   🌍 TRULY UNIVERSAL web scraping")
        print("   📰 Optimized for news articles")
        print("   🤖 AI-powered for everything else")
        print("   🔄 Intelligent automatic selection")
        
    except KeyboardInterrupt:
        print("\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")


if __name__ == "__main__":
    main()
