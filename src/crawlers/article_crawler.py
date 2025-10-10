"""
Universal Article List Crawler
Implements cascading fallback strategy similar to web scraping pipeline
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

from src.core.fetcher import fetch_rendered
from src.extractors.extract_scrapegraph import scrapegraph_article
from src.core.llm_wrapper import get_token_usage, clear_token_usage


def extract_structured_articles(url: str) -> List[Dict[str, Any]]:
    """
    Step 1: Extract articles using structured data (JSON-LD, Microdata, OpenGraph)
    """
    try:
        # Fetch the page
        html = fetch_rendered(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        articles = []
        
        # Try JSON-LD structured data
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                    for item in items:
                        if isinstance(item, dict) and item.get('@type') == 'ListItem':
                            article_data = item.get('item', {})
                            if article_data.get('@type') in ['Article', 'NewsArticle']:
                                articles.append({
                                    'title': article_data.get('headline', ''),
                                    'url': article_data.get('url', ''),
                                    'author': article_data.get('author', {}).get('name', '') if isinstance(article_data.get('author'), dict) else '',
                                    'published_date': article_data.get('datePublished', ''),
                                    'description': article_data.get('description', ''),
                                    'method': 'structured_data'
                                })
                elif isinstance(data, list):
                    for item in data:
                        if item.get('@type') in ['Article', 'NewsArticle']:
                            articles.append({
                                'title': item.get('headline', ''),
                                'url': item.get('url', ''),
                                'author': item.get('author', {}).get('name', '') if isinstance(item.get('author'), dict) else '',
                                'published_date': item.get('datePublished', ''),
                                'description': item.get('description', ''),
                                'method': 'structured_data'
                            })
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Try Microdata
        microdata_items = soup.find_all(attrs={'itemtype': re.compile(r'.*Article.*')})
        for item in microdata_items:
            title_elem = item.find(attrs={'itemprop': 'headline'}) or item.find(attrs={'itemprop': 'name'})
            url_elem = item.find('a', href=True) or item.find(attrs={'itemprop': 'url'})
            author_elem = item.find(attrs={'itemprop': 'author'})
            date_elem = item.find(attrs={'itemprop': 'datePublished'})
            
            if title_elem and url_elem:
                title = title_elem.get_text(strip=True)
                url = url_elem.get('href') or url_elem.get('content', '')
                if url and not url.startswith('http'):
                    url = urljoin(url, url)
                
                articles.append({
                    'title': title,
                    'url': url,
                    'author': author_elem.get_text(strip=True) if author_elem else '',
                    'published_date': date_elem.get_text(strip=True) if date_elem else '',
                    'description': '',
                    'method': 'microdata'
                })
        
        return articles
        
    except Exception as e:
        print(f"Structured data extraction failed: {e}")
        return []


def extract_pattern_articles(url: str) -> List[Dict[str, Any]]:
    """
    Step 2: Extract articles using common HTML patterns
    """
    try:
        html = fetch_rendered(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        articles = []
        
        # Common patterns for article lists
        patterns = [
            # Pattern 1: Article cards with links
            {'selector': 'article', 'title': 'h1, h2, h3, h4', 'link': 'a'},
            # Pattern 2: List items with links
            {'selector': 'li', 'title': 'a', 'link': 'a'},
            # Pattern 3: Div containers with article links
            {'selector': '.article, .post, .news-item', 'title': 'a, h1, h2, h3', 'link': 'a'},
            # Pattern 4: Table rows with article links
            {'selector': 'tr', 'title': 'a, td', 'link': 'a'},
        ]
        
        for pattern in patterns:
            containers = soup.select(pattern['selector'])
            
            for container in containers:
                # Find title element
                title_elem = container.select_one(pattern['title'])
                if not title_elem:
                    continue
                
                # Find link element
                link_elem = container.select_one(pattern['link'])
                if not link_elem or not link_elem.get('href'):
                    continue
                
                title = title_elem.get_text(strip=True)
                url = link_elem.get('href')
                
                # Make URL absolute
                if url and not url.startswith('http'):
                    url = urljoin(url, url)
                
                # Skip if title is too short or URL is invalid
                if len(title) < 5 or not url:
                    continue
                
                # Try to find author and date in the container
                author_elem = container.select_one('.author, .byline, [class*="author"], [class*="byline"]')
                date_elem = container.select_one('.date, .time, [class*="date"], [class*="time"], time')
                
                articles.append({
                    'title': title,
                    'url': url,
                    'author': author_elem.get_text(strip=True) if author_elem else '',
                    'published_date': date_elem.get_text(strip=True) if date_elem else '',
                    'description': '',
                    'method': 'pattern_based'
                })
            
            # If we found articles with this pattern, use them
            if articles:
                break
        
        return articles
        
    except Exception as e:
        print(f"Pattern-based extraction failed: {e}")
        return []


def ai_extract_articles(url: str, count: int = 10) -> List[Dict[str, Any]]:
    """
    Step 3: AI-powered universal article extraction
    """
    try:
        clear_token_usage()
        
        prompt = f"""
        Extract the top {count} articles from this webpage.
        
        For each article, find and extract:
        - Title/link text (the main headline)
        - Article URL (the href attribute of the link)
        - Author name (if available)
        - Publication date (if available)
        - Brief description/excerpt (if available)
        
        Handle any page layout - vertical lists, horizontal grids, cards, tables, or complex structures.
        Look for common patterns like:
        - Article titles with clickable links
        - Author bylines
        - Publication timestamps
        - Article previews/summaries
        
        Return the results as a JSON array with this structure:
        [
            {{
                "title": "Article title here",
                "url": "https://full-url-here",
                "author": "Author name",
                "published_date": "2024-01-01",
                "description": "Brief description"
            }}
        ]
        
        Make sure URLs are complete and absolute. Extract exactly {count} articles or as many as available.
        """
        
        # Use ScrapeGraphAI for universal extraction
        from scrapegraphai.graphs import SmartScraperGraph
        
        model = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini")
        config = {
            "llm": {
                "model": model,
                "api_key": os.getenv("OPENAI_API_KEY"),
                "temperature": 0.1
            }
        }
        
        graph = SmartScraperGraph(prompt=prompt, source=url, config=config)
        result = graph.run()
        
        # Get token usage
        token_usage = get_token_usage()
        
        # Parse the result
        if isinstance(result, str):
            try:
                articles = json.loads(result)
            except json.JSONDecodeError:
                # Try to extract JSON from the result
                json_match = re.search(r'\[.*\]', result, re.DOTALL)
                if json_match:
                    articles = json.loads(json_match.group())
                else:
                    articles = []
        elif isinstance(result, list):
            articles = result
        else:
            articles = []
        
        # Add method indicator
        for article in articles:
            article['method'] = 'ai_extraction'
        
        return {
            "articles": articles,
            "token_usage": token_usage
        }
        
    except Exception as e:
        print(f"AI extraction failed: {e}")
        return {
            "articles": [],
            "token_usage": {}
        }


def crawl_article_list(url: str, count: int = 10, mode: str = "auto") -> Dict[str, Any]:
    """
    Universal article list crawler with mode selection
    """
    print(f"🕷️ Crawling article list: {url} (mode: {mode})")
    
    if mode == "sd":
        # SD Mode: Only structured data + pattern matching
        print("📊 SD Mode: Using structured data and pattern matching only")
        
        # Step 1: Try Structured Data
        articles = extract_structured_articles(url)
        if len(articles) >= count:
            print(f"✅ Found {len(articles)} articles via structured data")
            return {
                "articles": articles[:count],
                "token_usage": {}
            }
        
        # Step 2: Try Pattern-based extraction
        articles = extract_pattern_articles(url)
        print(f"✅ Found {len(articles)} articles via pattern matching")
        return {
            "articles": articles[:count],
            "token_usage": {}
        }
    
    elif mode == "llm":
        # LLM Mode: Only AI extraction
        print("🤖 LLM Mode: Using AI extraction only")
        result = ai_extract_articles(url, count)
        articles = result if isinstance(result, list) else result.get('articles', [])
        token_usage = result.get('token_usage', {}) if isinstance(result, dict) else {}
        print(f"✅ Found {len(articles)} articles via AI extraction")
        return {
            "articles": articles[:count],
            "token_usage": token_usage
        }
    
    else:  # auto mode
        # Auto Mode: Cascading fallback (SD → Pattern → AI)
        print("🔄 Auto Mode: Using cascading fallback strategy")
        
        # Step 1: Try Structured Data (fastest, most reliable)
        print("📊 Step 1: Trying structured data extraction...")
        articles = extract_structured_articles(url)
        if len(articles) >= count:
            print(f"✅ Found {len(articles)} articles via structured data")
            return {
                "articles": articles[:count],
                "token_usage": {}
            }
        
        # Step 2: Try Pattern-based extraction (fast, common patterns)
        print("🔍 Step 2: Trying pattern-based extraction...")
        articles = extract_pattern_articles(url)
        if len(articles) >= count:
            print(f"✅ Found {len(articles)} articles via pattern matching")
            return {
                "articles": articles[:count],
                "token_usage": {}
            }
        
        # Step 3: AI fallback (universal, handles any structure)
        print("🤖 Step 3: Using AI-powered extraction...")
        result = ai_extract_articles(url, count)
        articles = result if isinstance(result, list) else result.get('articles', [])
        token_usage = result.get('token_usage', {}) if isinstance(result, dict) else {}
        print(f"✅ Found {len(articles)} articles via AI extraction")
        
        return {
            "articles": articles[:count],
            "token_usage": token_usage
        }


async def crawl_with_full_content(url: str, count: int = 10, mode: str = "auto") -> Dict[str, Any]:
    """
    Crawl article list and get full content for each article
    """
    # Get article list
    crawl_result = crawl_article_list(url, count, mode)
    articles = crawl_result.get("articles", [])
    token_usage = crawl_result.get("token_usage", {})
    
    if not articles:
        return {
            "articles": [],
            "token_usage": token_usage
        }
    
    print(f"📄 Getting full content for {len(articles)} articles...")
    
    # Get full content for each article
    full_articles = []
    for i, article in enumerate(articles, 1):
        print(f"📖 Processing article {i}/{len(articles)}: {article['title'][:50]}...")
        
        try:
            # Use existing extraction pipeline for full content
            full_content = await scrapegraph_article(article['url'])
            
            full_articles.append({
                'title': article['title'],
                'url': article['url'],
                'author': article.get('author', ''),
                'published_date': article.get('published_date', ''),
                'description': article.get('description', ''),
                'content': full_content,
                'extraction_method': article.get('method', 'unknown'),
                'crawl_mode': mode,
                'crawled_at': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            print(f"❌ Failed to extract content for {article['url']}: {e}")
            # Still include the article without content
            full_articles.append({
                'title': article['title'],
                'url': article['url'],
                'author': article.get('author', ''),
                'published_date': article.get('published_date', ''),
                'description': article.get('description', ''),
                'content': None,
                'extraction_method': article.get('method', 'unknown'),
                'crawl_mode': mode,
                'error': str(e),
                'crawled_at': datetime.utcnow().isoformat()
            })
    
    return {
        "articles": full_articles,
        "token_usage": token_usage
    }
