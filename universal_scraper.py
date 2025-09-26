#!/usr/bin/env python3
"""
Universal Web Scraping Tool
Combines ScrapeGraph API and newspaper3k for comprehensive web scraping capabilities
"""

import os
import json
import time
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum

# ScrapeGraph API imports
from scrapegraph_py import Client
from scrapegraph_py.logger import sgai_logger

# newspaper3k imports
from newspaper import Article, ArticleException
import nltk

# Download required NLTK data for newspaper3k
try:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass  # Continue if download fails


class ScrapingMethod(Enum):
    """Enumeration of available scraping methods"""
    SCRAPEGRAPH_SMART = "scrapegraph_smart"
    SCRAPEGRAPH_SEARCH = "scrapegraph_search"
    SCRAPEGRAPH_CRAWLER = "scrapegraph_crawler"
    SCRAPEGRAPH_MARKDOWN = "scrapegraph_markdown"
    NEWSPAPER3K = "newspaper3k"
    AUTO = "auto"  # Automatically choose the best method


@dataclass
class ScrapingResult:
    """Data class to hold scraping results"""
    url: str
    method_used: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None


class UniversalWebScraper:
    """
    Universal Web Scraper combining ScrapeGraph API and newspaper3k
    
    Features:
    - AI-powered extraction with ScrapeGraph API
    - Traditional article extraction with newspaper3k
    - Automatic method selection
    - Fallback mechanisms
    - Comprehensive error handling
    """
    
    def __init__(self, scrapegraph_api_key: Optional[str] = None):
        """
        Initialize the Universal Web Scraper
        
        Args:
            scrapegraph_api_key: ScrapeGraph API key. If None, will try to get from environment
        """
        self.scrapegraph_api_key = scrapegraph_api_key or os.getenv('SCRAPEGRAPH_API_KEY')
        self.scrapegraph_client = None
        
        # Initialize ScrapeGraph client if API key is available
        if self.scrapegraph_api_key:
            try:
                sgai_logger.set_logging(level="INFO")
                self.scrapegraph_client = Client(api_key=self.scrapegraph_api_key)
                print("✅ ScrapeGraph API client initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize ScrapeGraph client: {e}")
                self.scrapegraph_client = None
        else:
            print("⚠️ No ScrapeGraph API key provided. Only newspaper3k will be available.")
    
    def scrape_url(self, 
                   url: str, 
                   method: ScrapingMethod = ScrapingMethod.AUTO,
                   prompt: Optional[str] = None,
                   **kwargs) -> ScrapingResult:
        """
        Scrape a single URL using the specified method
        
        Args:
            url: URL to scrape
            method: Scraping method to use
            prompt: Custom prompt for ScrapeGraph API (if applicable)
            **kwargs: Additional parameters for specific methods
            
        Returns:
            ScrapingResult object with the scraping results
        """
        start_time = time.time()
        
        # Auto-select method if not specified
        if method == ScrapingMethod.AUTO:
            method = self._select_best_method(url, prompt)
        
        try:
            if method in [ScrapingMethod.SCRAPEGRAPH_SMART, 
                         ScrapingMethod.SCRAPEGRAPH_SEARCH,
                         ScrapingMethod.SCRAPEGRAPH_CRAWLER,
                         ScrapingMethod.SCRAPEGRAPH_MARKDOWN]:
                result = self._scrape_with_scrapegraph(url, method, prompt, **kwargs)
            elif method == ScrapingMethod.NEWSPAPER3K:
                result = self._scrape_with_newspaper3k(url, **kwargs)
            else:
                raise ValueError(f"Unknown scraping method: {method}")
            
            result.execution_time = time.time() - start_time
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ScrapingResult(
                url=url,
                method_used=str(method.value),
                success=False,
                data={},
                error=str(e),
                execution_time=execution_time
            )
    
    def _select_best_method(self, url: str, prompt: Optional[str] = None) -> ScrapingMethod:
        """
        Automatically select the best scraping method based on URL and requirements
        
        Args:
            url: URL to scrape
            prompt: Custom prompt (if any)
            
        Returns:
            Best ScrapingMethod for the given URL
        """
        # If we have ScrapeGraph API and a custom prompt, prefer ScrapeGraph
        if self.scrapegraph_client and prompt:
            return ScrapingMethod.SCRAPEGRAPH_SMART
        
        # For news articles, prefer newspaper3k
        if any(news_domain in url.lower() for news_domain in 
               ['news', 'article', 'blog', 'cnn', 'bbc', 'reuters', 'nytimes']):
            return ScrapingMethod.NEWSPAPER3K
        
        # For complex sites or when we need structured data, use ScrapeGraph
        if self.scrapegraph_client:
            return ScrapingMethod.SCRAPEGRAPH_SMART
        
        # Fallback to newspaper3k
        return ScrapingMethod.NEWSPAPER3K
    
    def _scrape_with_scrapegraph(self, 
                                url: str, 
                                method: ScrapingMethod,
                                prompt: Optional[str] = None,
                                **kwargs) -> ScrapingResult:
        """
        Scrape using ScrapeGraph API
        
        Args:
            url: URL to scrape
            method: ScrapeGraph method to use
            prompt: Custom prompt
            **kwargs: Additional parameters
            
        Returns:
            ScrapingResult object
        """
        if not self.scrapegraph_client:
            raise Exception("ScrapeGraph API client not initialized")
        
        try:
            if method == ScrapingMethod.SCRAPEGRAPH_SMART:
                response = self.scrapegraph_client.smartscraper(
                    website_url=url,
                    user_prompt=prompt or "Extract all relevant information from this webpage",
                    **kwargs
                )
            elif method == ScrapingMethod.SCRAPEGRAPH_SEARCH:
                response = self.scrapegraph_client.searchscraper(
                    user_prompt=prompt or f"Search for information related to: {url}",
                    **kwargs
                )
            elif method == ScrapingMethod.SCRAPEGRAPH_CRAWLER:
                response = self.scrapegraph_client.smartcrawler(
                    website_url=url,
                    user_prompt=prompt or "Crawl and extract information from this website",
                    **kwargs
                )
            elif method == ScrapingMethod.SCRAPEGRAPH_MARKDOWN:
                response = self.scrapegraph_client.markdownify(
                    website_url=url,
                    **kwargs
                )
            else:
                raise ValueError(f"Unsupported ScrapeGraph method: {method}")
            
            return ScrapingResult(
                url=url,
                method_used=str(method.value),
                success=True,
                data=response.get('result', {}),
                metadata={
                    'request_id': response.get('request_id'),
                    'reference_urls': response.get('reference_urls', []),
                    'tokens_used': response.get('metadata', {}).get('tokens_used'),
                    'execution_time': response.get('metadata', {}).get('execution_time')
                }
            )
            
        except Exception as e:
            raise Exception(f"ScrapeGraph API error: {str(e)}")
    
    def _scrape_with_newspaper3k(self, url: str, **kwargs) -> ScrapingResult:
        """
        Scrape using newspaper3k
        
        Args:
            url: URL to scrape
            **kwargs: Additional parameters
            
        Returns:
            ScrapingResult object
        """
        try:
            article = Article(url)
            article.download()
            article.parse()
            
            # Perform NLP analysis
            article.nlp()
            
            # Extract structured data
            data = {
                'title': article.title,
                'authors': article.authors,
                'publish_date': article.publish_date.isoformat() if article.publish_date else None,
                'text': article.text,
                'summary': article.summary,
                'keywords': article.keywords,
                'images': article.images,
                'videos': article.movies,
                'url': article.url,
                'top_image': article.top_image,
                'html': article.html
            }
            
            return ScrapingResult(
                url=url,
                method_used=ScrapingMethod.NEWSPAPER3K.value,
                success=True,
                data=data,
                metadata={
                    'word_count': len(article.text.split()) if article.text else 0,
                    'image_count': len(article.images) if article.images else 0,
                    'video_count': len(article.movies) if article.movies else 0
                }
            )
            
        except ArticleException as e:
            raise Exception(f"Newspaper3k article error: {str(e)}")
        except Exception as e:
            raise Exception(f"Newspaper3k error: {str(e)}")
    
    def scrape_multiple_urls(self, 
                           urls: List[str], 
                           method: ScrapingMethod = ScrapingMethod.AUTO,
                           prompt: Optional[str] = None,
                           **kwargs) -> List[ScrapingResult]:
        """
        Scrape multiple URLs
        
        Args:
            urls: List of URLs to scrape
            method: Scraping method to use
            prompt: Custom prompt for ScrapeGraph API
            **kwargs: Additional parameters
            
        Returns:
            List of ScrapingResult objects
        """
        results = []
        for url in urls:
            try:
                result = self.scrape_url(url, method, prompt, **kwargs)
                results.append(result)
            except Exception as e:
                results.append(ScrapingResult(
                    url=url,
                    method_used=str(method.value),
                    success=False,
                    data={},
                    error=str(e)
                ))
        
        return results
    
    def get_available_methods(self) -> List[str]:
        """
        Get list of available scraping methods
        
        Returns:
            List of available method names
        """
        methods = [ScrapingMethod.NEWSPAPER3K.value]
        
        if self.scrapegraph_client:
            methods.extend([
                ScrapingMethod.SCRAPEGRAPH_SMART.value,
                ScrapingMethod.SCRAPEGRAPH_SEARCH.value,
                ScrapingMethod.SCRAPEGRAPH_CRAWLER.value,
                ScrapingMethod.SCRAPEGRAPH_MARKDOWN.value
            ])
        
        methods.append(ScrapingMethod.AUTO.value)
        return methods
    
    def close(self):
        """Close the ScrapeGraph client if it exists"""
        if self.scrapegraph_client:
            try:
                self.scrapegraph_client.close()
                print("✅ ScrapeGraph client closed")
            except:
                pass


def main():
    """Example usage of the Universal Web Scraper"""
    print("🚀 Universal Web Scraper Demo")
    print("=" * 50)
    
    # Initialize scraper (you'll need to set SCRAPEGRAPH_API_KEY environment variable)
    scraper = UniversalWebScraper()
    
    # Show available methods
    print(f"📋 Available methods: {', '.join(scraper.get_available_methods())}")
    print()
    
    # Example URLs to test
    test_urls = [
        "https://36kr.com/p/3482899443506050",  # Your existing demo URL
        "https://example.com",  # Simple test URL
    ]
    
    for url in test_urls:
        print(f"🔍 Scraping: {url}")
        print("-" * 30)
        
        try:
            # Try auto method first
            result = scraper.scrape_url(url, ScrapingMethod.AUTO)
            
            if result.success:
                print(f"✅ Success using {result.method_used}")
                print(f"⏱️ Execution time: {result.execution_time:.2f}s")
                
                # Show some extracted data
                if 'title' in result.data:
                    print(f"📰 Title: {result.data['title']}")
                if 'summary' in result.data:
                    print(f"📝 Summary: {result.data['summary'][:200]}...")
                if 'keywords' in result.data:
                    print(f"🏷️ Keywords: {', '.join(result.data['keywords'][:5])}")
            else:
                print(f"❌ Failed: {result.error}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()
    
    # Close the scraper
    scraper.close()
    print("✅ Demo completed!")


if __name__ == "__main__":
    main()
