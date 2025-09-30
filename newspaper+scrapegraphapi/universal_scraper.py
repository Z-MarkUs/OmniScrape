#!/usr/bin/env python3
"""
Universal Web Scraping Tool - Single Entrypoint

This module re-exports the enhanced engine to provide a single canonical API.
"""

from typing import List

# Re-export the enhanced implementation for backwards compatibility
from enhanced_universal_scraper import (
    EnhancedUniversalWebScraper as UniversalWebScraper,
    ScrapingMethod,
)

__all__ = [
    "UniversalWebScraper",
    "ScrapingMethod",
]


def main():
    """Example usage of the Universal Web Scraper (enhanced engine)"""
    print("🚀 Universal Web Scraper Demo (Enhanced)")
    print("=" * 50)

    scraper = UniversalWebScraper()
    print(f"📋 Available methods: {', '.join(scraper.get_available_methods())}")
    print()

    test_urls: List[str] = [
        "https://36kr.com/p/3482899443506050",
        "https://example.com",
    ]

    for url in test_urls:
        print(f"🔍 Scraping: {url}")
        print("-" * 30)
        result = scraper.scrape_url(url, ScrapingMethod.AUTO)
        if result.success:
            print(f"✅ Success using {result.method_used}")
            print(f"⏱️ Execution time: {result.execution_time:.2f}s")
        else:
            print(f"❌ Failed: {result.error}")
        print()

    scraper.close()
    print("✅ Demo completed!")


if __name__ == "__main__":
    main()
