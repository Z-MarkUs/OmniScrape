#!/usr/bin/env python3
"""
Enhanced Universal Web Scraper - Architecture Implementation
Implements the architectural design with advanced features
"""

import os
import json
import time
import hashlib
import asyncio
import threading
from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import re

# ScrapeGraph API imports
from scrapegraph_py import Client
from scrapegraph_py.logger import sgai_logger

# newspaper3k imports
from newspaper import Article, ArticleException
import nltk

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass


class ScrapingMethod(Enum):
    """Enumeration of available scraping methods"""
    SCRAPEGRAPH_SMART = "scrapegraph_smart"
    SCRAPEGRAPH_SEARCH = "scrapegraph_search"
    SCRAPEGRAPH_CRAWLER = "scrapegraph_crawler"
    SCRAPEGRAPH_MARKDOWN = "scrapegraph_markdown"
    NEWSPAPER3K = "newspaper3k"
    AUTO = "auto"


class ScrapingPriority(Enum):
    """Priority levels for scraping methods"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScrapingResult:
    """Enhanced data class to hold scraping results"""
    url: str
    method_used: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    priority: ScrapingPriority = ScrapingPriority.MEDIUM


@dataclass
class CacheEntry:
    """Cache entry for storing results"""
    result: ScrapingResult
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)


class MethodSelectionEngine:
    """Intelligent method selection engine"""
    
    def __init__(self):
        self.url_patterns = {
            'news_sites': [
                'cnn.com', 'bbc.com', 'reuters.com', 'nytimes.com', 
                'washingtonpost.com', 'guardian.com', '36kr.com'
            ],
            'ecommerce_sites': [
                'amazon.com', 'ebay.com', 'shopify.com', 'etsy.com'
            ],
            'social_media': [
                'twitter.com', 'facebook.com', 'linkedin.com', 'instagram.com'
            ],
            'dynamic_sites': [
                'spa', 'react', 'angular', 'vue'
            ]
        }
        
        self.method_preferences = {
            'news_sites': ScrapingMethod.NEWSPAPER3K,
            'ecommerce_sites': ScrapingMethod.SCRAPEGRAPH_SMART,
            'social_media': ScrapingMethod.SCRAPEGRAPH_SMART,
            'dynamic_sites': ScrapingMethod.SCRAPEGRAPH_SMART
        }
    
    def analyze_url(self, url: str) -> Dict[str, float]:
        """Analyze URL and return pattern scores"""
        domain = urlparse(url).netloc.lower()
        scores = {}
        
        for pattern_type, sites in self.url_patterns.items():
            score = 0.0
            for site in sites:
                if site in domain:
                    score = 1.0
                    break
            scores[pattern_type] = score
        
        return scores
    
    def analyze_prompt_complexity(self, prompt: str) -> float:
        """Analyze prompt complexity (0.0 = simple, 1.0 = complex)"""
        if not prompt:
            return 0.0
        
        complexity_indicators = [
            'extract', 'find', 'get', 'retrieve',  # Simple
            'analyze', 'compare', 'structure', 'format',  # Medium
            'intelligent', 'smart', 'complex', 'advanced'  # Complex
        ]
        
        prompt_lower = prompt.lower()
        complexity_score = 0.0
        
        for i, indicator in enumerate(complexity_indicators):
            if indicator in prompt_lower:
                complexity_score += (i + 1) * 0.1
        
        return min(complexity_score, 1.0)
    
    def select_method(self, url: str, prompt: str = None, 
                     scrapegraph_available: bool = True) -> ScrapingMethod:
        """Select the best scraping method based on analysis - TRULY UNIVERSAL"""
        
        # Analyze URL patterns
        url_scores = self.analyze_url(url)
        
        # Analyze prompt complexity
        prompt_complexity = self.analyze_prompt_complexity(prompt)
        
        # Decision logic for UNIVERSAL scraping
        if not scrapegraph_available:
            # Without ScrapeGraph, we're limited to newspaper3k (articles only)
            return ScrapingMethod.NEWSPAPER3K
        
        # NEWSPAPER3K: Only for news articles (optimized for this specific use case)
        if url_scores.get('news_sites', 0) > 0.8 and not prompt:
            # News sites without custom prompts → newspaper3k (free, optimized)
            return ScrapingMethod.NEWSPAPER3K
        
        # SCRAPEGRAPH: Everything else (truly universal)
        # - E-commerce sites
        # - Social media
        # - Forums
        # - Documentation
        # - Complex sites
        # - Custom prompts
        # - Structured data extraction
        # - Dynamic content
        return ScrapingMethod.SCRAPEGRAPH_SMART


class CacheManager:
    """Advanced caching system"""
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self.lock = threading.Lock()
    
    def _generate_key(self, url: str, method: str, prompt: str = None) -> str:
        """Generate cache key"""
        key_data = f"{url}:{method}:{prompt or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, url: str, method: str, prompt: str = None) -> Optional[ScrapingResult]:
        """Get cached result"""
        key = self._generate_key(url, method, prompt)
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # Check if expired
                if datetime.now() > entry.expires_at:
                    del self.cache[key]
                    return None
                
                # Update access info
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                
                return entry.result
        
        return None
    
    def set(self, url: str, method: str, result: ScrapingResult, 
            prompt: str = None, custom_ttl: Optional[timedelta] = None):
        """Cache result"""
        key = self._generate_key(url, method, prompt)
        
        with self.lock:
            # Remove expired entries
            self._cleanup_expired()
            
            # Check cache size
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            # Add new entry
            ttl = custom_ttl or self.ttl
            entry = CacheEntry(
                result=result,
                created_at=datetime.now(),
                expires_at=datetime.now() + ttl
            )
            self.cache[key] = entry
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now > entry.expires_at
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self.cache:
            return
        
        lru_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].last_accessed
        )
        del self.cache[lru_key]
    
    def clear(self):
        """Clear all cache"""
        with self.lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            if not self.cache:
                return {'size': 0, 'hit_rate': 0.0}
            
            total_accesses = sum(entry.access_count for entry in self.cache.values())
            return {
                'size': len(self.cache),
                'total_accesses': total_accesses,
                'avg_access_per_entry': total_accesses / len(self.cache) if self.cache else 0
            }


class PerformanceMonitor:
    """Performance monitoring and analytics"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {
            'execution_times': [],
            'success_rates': [],
            'error_counts': []
        }
        self.method_stats: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
    
    def record_execution(self, method: str, execution_time: float, 
                        success: bool, error: str = None):
        """Record execution metrics"""
        with self.lock:
            # Update general metrics
            self.metrics['execution_times'].append(execution_time)
            self.metrics['success_rates'].append(1.0 if success else 0.0)
            if error:
                self.metrics['error_counts'].append(1)
            
            # Update method-specific stats
            if method not in self.method_stats:
                self.method_stats[method] = {
                    'total_executions': 0,
                    'successful_executions': 0,
                    'total_time': 0.0,
                    'avg_time': 0.0,
                    'success_rate': 0.0,
                    'errors': []
                }
            
            stats = self.method_stats[method]
            stats['total_executions'] += 1
            stats['total_time'] += execution_time
            stats['avg_time'] = stats['total_time'] / stats['total_executions']
            
            if success:
                stats['successful_executions'] += 1
            
            stats['success_rate'] = stats['successful_executions'] / stats['total_executions']
            
            if error:
                stats['errors'].append(error)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        with self.lock:
            if not self.metrics['execution_times']:
                return {'message': 'No data available'}
            
            return {
                'overall': {
                    'total_executions': len(self.metrics['execution_times']),
                    'avg_execution_time': sum(self.metrics['execution_times']) / len(self.metrics['execution_times']),
                    'success_rate': sum(self.metrics['success_rates']) / len(self.metrics['success_rates']),
                    'error_count': len(self.metrics['error_counts'])
                },
                'by_method': self.method_stats
            }


class EnhancedUniversalWebScraper:
    """
    Enhanced Universal Web Scraper with advanced architectural features
    """
    
    def __init__(self, scrapegraph_api_key: Optional[str] = None,
                 cache_size: int = 1000, cache_ttl_hours: int = 24,
                 enable_monitoring: bool = True):
        """
        Initialize the Enhanced Universal Web Scraper
        
        Args:
            scrapegraph_api_key: ScrapeGraph API key
            cache_size: Maximum cache size
            cache_ttl_hours: Cache TTL in hours
            enable_monitoring: Enable performance monitoring
        """
        self.scrapegraph_api_key = scrapegraph_api_key or os.getenv('SCRAPEGRAPH_API_KEY')
        self.scrapegraph_client = None
        
        # Initialize components
        self.method_selector = MethodSelectionEngine()
        self.cache_manager = CacheManager(cache_size, cache_ttl_hours)
        self.performance_monitor = PerformanceMonitor() if enable_monitoring else None
        
        # Initialize ScrapeGraph client
        if self.scrapegraph_api_key:
            try:
                sgai_logger.set_logging(level="INFO")
                self.scrapegraph_client = Client(api_key=self.scrapegraph_api_key)
                print("✅ Enhanced ScrapeGraph API client initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize ScrapeGraph client: {e}")
                self.scrapegraph_client = None
        else:
            print("⚠️ No ScrapeGraph API key provided. Only newspaper3k will be available.")
    
    def scrape_url(self, url: str, method: ScrapingMethod = ScrapingMethod.AUTO,
                   prompt: Optional[str] = None, use_cache: bool = True,
                   priority: ScrapingPriority = ScrapingPriority.MEDIUM,
                   **kwargs) -> ScrapingResult:
        """
        Enhanced URL scraping with caching and monitoring
        """
        start_time = time.time()
        
        # Check cache first
        if use_cache:
            cached_result = self.cache_manager.get(url, str(method.value), prompt)
            if cached_result:
                print(f"📋 Cache hit for {url}")
                return cached_result
        
        # Auto-select method if needed
        if method == ScrapingMethod.AUTO:
            method = self.method_selector.select_method(
                url, prompt, self.scrapegraph_client is not None
            )
        
        # Execute scraping with retry logic
        result = self._execute_with_retry(url, method, prompt, priority, **kwargs)
        result.execution_time = time.time() - start_time
        result.priority = priority
        
        # Record performance metrics
        if self.performance_monitor:
            self.performance_monitor.record_execution(
                str(method.value), result.execution_time, result.success, result.error
            )
        
        # Cache successful results
        if use_cache and result.success:
            self.cache_manager.set(url, str(method.value), result, prompt)
        
        return result
    
    def _execute_with_retry(self, url: str, method: ScrapingMethod,
                           prompt: str = None, priority: ScrapingPriority = ScrapingPriority.MEDIUM,
                           max_retries: int = 3, **kwargs) -> ScrapingResult:
        """Execute scraping with retry logic and fallback"""
        
        for attempt in range(max_retries + 1):
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
                
                result.retry_count = attempt
                return result
                
            except Exception as e:
                if attempt == max_retries:
                    # Final attempt failed, try fallback
                    return self._try_fallback(url, method, prompt, str(e), **kwargs)
                
                # Wait before retry (exponential backoff)
                wait_time = 2 ** attempt
                print(f"⚠️ Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
    
    def _try_fallback(self, url: str, original_method: ScrapingMethod,
                     prompt: str, error: str, **kwargs) -> ScrapingResult:
        """Try fallback method when primary method fails"""
        
        print(f"🔄 Trying fallback method for {url}")
        
        # Determine fallback method
        if original_method in [ScrapingMethod.SCRAPEGRAPH_SMART,
                             ScrapingMethod.SCRAPEGRAPH_SEARCH,
                             ScrapingMethod.SCRAPEGRAPH_CRAWLER,
                             ScrapingMethod.SCRAPEGRAPH_MARKDOWN]:
            fallback_method = ScrapingMethod.NEWSPAPER3K
        else:
            fallback_method = ScrapingMethod.SCRAPEGRAPH_SMART
        
        try:
            if fallback_method == ScrapingMethod.NEWSPAPER3K:
                result = self._scrape_with_newspaper3k(url, **kwargs)
            else:
                result = self._scrape_with_scrapegraph(url, fallback_method, prompt, **kwargs)
            
            result.retry_count = 1
            result.metadata['fallback_used'] = True
            result.metadata['original_error'] = error
            print(f"✅ Fallback successful using {fallback_method.value}")
            return result
            
        except Exception as fallback_error:
            # Both methods failed
            return ScrapingResult(
                url=url,
                method_used=str(original_method.value),
                success=False,
                data={},
                error=f"Primary method failed: {error}. Fallback failed: {str(fallback_error)}",
                retry_count=1,
                metadata={'fallback_failed': True}
            )
    
    def _scrape_with_scrapegraph(self, url: str, method: ScrapingMethod,
                                prompt: Optional[str] = None, **kwargs) -> ScrapingResult:
        """Scrape using ScrapeGraph API with enhanced error handling"""
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
                    'execution_time': response.get('metadata', {}).get('execution_time'),
                    'api_version': 'scrapegraph_v1'
                }
            )
            
        except Exception as e:
            raise Exception(f"ScrapeGraph API error: {str(e)}")
    
    def _scrape_with_newspaper3k(self, url: str, **kwargs) -> ScrapingResult:
        """Enhanced newspaper3k scraping with better error handling"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            
            # Perform NLP analysis
            article.nlp()
            
            # Enhanced data extraction
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
                'html': article.html,
                'word_count': len(article.text.split()) if article.text else 0,
                'reading_time': self._estimate_reading_time(article.text) if article.text else 0
            }
            
            return ScrapingResult(
                url=url,
                method_used=ScrapingMethod.NEWSPAPER3K.value,
                success=True,
                data=data,
                metadata={
                    'word_count': data['word_count'],
                    'image_count': len(article.images) if article.images else 0,
                    'video_count': len(article.movies) if article.movies else 0,
                    'reading_time': data['reading_time'],
                    'nlp_processed': True
                }
            )
            
        except ArticleException as e:
            raise Exception(f"Newspaper3k article error: {str(e)}")
        except Exception as e:
            raise Exception(f"Newspaper3k error: {str(e)}")
    
    def _estimate_reading_time(self, text: str) -> int:
        """Estimate reading time in minutes (average 200 words per minute)"""
        if not text:
            return 0
        word_count = len(text.split())
        return max(1, word_count // 200)
    
    def scrape_multiple_urls(self, urls: List[str], 
                           method: ScrapingMethod = ScrapingMethod.AUTO,
                           prompt: Optional[str] = None,
                           max_concurrent: int = 5,
                           **kwargs) -> List[ScrapingResult]:
        """
        Enhanced batch scraping with concurrency control
        """
        results = []
        
        # Simple concurrent processing (can be enhanced with asyncio)
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i:i + max_concurrent]
            batch_results = []
            
            for url in batch:
                try:
                    result = self.scrape_url(url, method, prompt, **kwargs)
                    batch_results.append(result)
                except Exception as e:
                    batch_results.append(ScrapingResult(
                        url=url,
                        method_used=str(method.value),
                        success=False,
                        data={},
                        error=str(e)
                    ))
            
            results.extend(batch_results)
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.performance_monitor:
            return {'message': 'Performance monitoring disabled'}
        
        stats = self.performance_monitor.get_performance_summary()
        stats['cache_stats'] = self.cache_manager.get_stats()
        return stats
    
    def clear_cache(self):
        """Clear all cached results"""
        self.cache_manager.clear()
        print("🗑️ Cache cleared")
    
    def get_available_methods(self) -> List[str]:
        """Get list of available scraping methods"""
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
        """Close the ScrapeGraph client and cleanup"""
        if self.scrapegraph_client:
            try:
                self.scrapegraph_client.close()
                print("✅ Enhanced ScrapeGraph client closed")
            except:
                pass


def main():
    """Demo the enhanced universal scraper"""
    print("🚀 Enhanced Universal Web Scraper Demo")
    print("=" * 50)
    
    # Initialize enhanced scraper
    scraper = EnhancedUniversalWebScraper(
        cache_size=100,
        cache_ttl_hours=1,
        enable_monitoring=True
    )
    
    # Show available methods
    print(f"📋 Available methods: {', '.join(scraper.get_available_methods())}")
    print()
    
    # Test URLs
    test_urls = [
        "https://36kr.com/p/3482899443506050",
        "https://example.com"
    ]
    
    for url in test_urls:
        print(f"🔍 Scraping: {url}")
        print("-" * 30)
        
        try:
            # Test with auto method
            result = scraper.scrape_url(url, ScrapingMethod.AUTO)
            
            if result.success:
                print(f"✅ Success using {result.method_used}")
                print(f"⏱️ Execution time: {result.execution_time:.2f}s")
                print(f"🔄 Retry count: {result.retry_count}")
                
                # Show some data
                if 'title' in result.data:
                    print(f"📰 Title: {result.data['title'][:50]}...")
                if 'word_count' in result.data:
                    print(f"📊 Word count: {result.data['word_count']}")
            else:
                print(f"❌ Failed: {result.error}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()
    
    # Show performance stats
    print("📊 Performance Statistics:")
    print("-" * 30)
    stats = scraper.get_performance_stats()
    print(json.dumps(stats, indent=2, default=str))
    
    # Close scraper
    scraper.close()
    print("\n✅ Enhanced demo completed!")


if __name__ == "__main__":
    main()
