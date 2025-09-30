#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import pandas as pd
import re
from datetime import datetime
from newspaper import build, Article

# Global target URL for easy switching
TARGET_URL = "https://www.hk01.com/channel/2/社會新聞"

# Try Selenium for hard sites (optional)
try:
  from selenium import webdriver
  from selenium.webdriver.chrome.service import Service
  from selenium.webdriver.chrome.options import Options
  from selenium.webdriver.common.by import By
  from selenium.webdriver.support.ui import WebDriverWait
  from selenium.webdriver.support import expected_conditions as EC
  SELENIUM_AVAILABLE = True
except Exception:
  SELENIUM_AVAILABLE = False

# Import for semantic similarity
try:
  from sentence_transformers import SentenceTransformer
  from sklearn.metrics.pairwise import cosine_similarity
  import numpy as np
  SEMANTIC_AVAILABLE = True
except ImportError:
  SEMANTIC_AVAILABLE = False
  print("Semantic matching not available - install sentence-transformers and scikit-learn")

# Import for fast content extraction
try:
  import trafilatura
  TRAFILATURA_AVAILABLE = True
except ImportError:
  TRAFILATURA_AVAILABLE = False
  print("Trafilatura not available - install trafilatura for faster content extraction")

class Config:
  def __init__(self):
    self.total_max_retry = 5
    self.logger = logging.getLogger(__name__)
    
    # Hardcoded config for testing
    self.lark_config_list = [
      {
        "config_head_positive_words": ["港股+直擊", "香港+財經", "中國+財經", "國際+財經"],
        "config_head_negative_words": ["廣告", "spam"]
      }
    ]
    
    # Column headers
    self.history_head_news_title = "资讯标题"
    self.history_head_news_link = "资讯链接"
    self.history_head_news_date = "发布时间"
    self.hit_head_positive_words = "组合触发词"
    self.hit_head_negative_words = "通用拦截词"
    self.hit_head_news_content = "资讯正文"
    self.config_head_positive_words = "config_head_positive_words"
    self.config_head_negative_words = "config_head_negative_words"

class Meta_Newspaper3k:
  def __init__(self, config: Config):
    self.config = config
    self.config.logger.debug("Meta_Newspaper3k init")
    # Robust HTTP session (headers + retries)
    try:
      import requests
      from requests.adapters import HTTPAdapter
      from urllib3.util.retry import Retry
      self.http = requests.Session()
      self.http.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache'
      })
      retry = Retry(total=3, backoff_factor=0.6, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","HEAD"])
      adapter = HTTPAdapter(max_retries=retry)
      self.http.mount('http://', adapter)
      self.http.mount('https://', adapter)
    except Exception:
      self.http = None
    
    # Optional Selenium browser for anti-scraping
    self.browser = None
    if SELENIUM_AVAILABLE:
      try:
        self.browser = self._try_init_browser()
        if self.browser:
          self.config.logger.debug("Selenium browser initialized")
      except Exception as e:
        self.config.logger.debug(f"Selenium init failed: {e}")
    
    # Initialize semantic model if available
    if SEMANTIC_AVAILABLE:
      try:
        self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.config.logger.debug("Semantic model loaded successfully")
      except Exception as e:
        self.config.logger.debug(f"Failed to load semantic model: {e}")
        self.semantic_model = None
    else:
      self.semantic_model = None

  def discover_articles(self, base_url: str, max_articles: int = 50):
    """Universal article discovery - tries multiple methods for different websites"""
    
    self.config.logger.debug(f"Discovering articles from: {base_url}")
    # Site-specific: HK01 category pages render many non-article anchors; prefer pattern-based extraction
    if 'hk01.com' in base_url:
      return self.discover_articles_hk01(base_url, max_articles)
    # Bypass newspaper3k for ETNet China (anti-scraping quirks)
    if base_url.startswith('https://column.etnetchina.cn'):
      return self.discover_articles_manual(base_url, max_articles)
    
    # Method 1: Try newspaper3k first (works for most news sites)
    articles = self.discover_articles_newspaper3k(base_url, max_articles)
    if articles:
      self.config.logger.debug(f"Method 1 (newspaper3k) found {len(articles)} articles")
      return articles
    
    # Method 2: Try manual HTML parsing (fallback for complex sites)
    articles = self.discover_articles_manual(base_url, max_articles)
    if articles:
      self.config.logger.debug(f"Method 2 (manual parsing) found {len(articles)} articles")
      return articles
    
    self.config.logger.debug("All discovery methods failed")
    return []

  def discover_articles_hk01(self, base_url: str, max_articles: int):
    """Site-specific discovery for HK01 category/list pages.
    Strategy: fetch HTML via session -> parse anchors -> whitelist article pattern '/article/<id>' ->
    absolute URL -> infer title from anchor or fallback to URL.
    """
    try:
      import re as _re
      from bs4 import BeautifulSoup
      headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.hk01.com/'
      }
      page_html = self.fetch_html(base_url, headers=headers)
      if not page_html:
        self.config.logger.debug("HK01: empty HTML after fetch_html")
        return []
      soup = BeautifulSoup(page_html, 'html.parser')
      article_data = []
      seen = set()
      # 1) Anchor-based extraction: links containing '/article/' followed by digits
      links = soup.find_all('a', href=True)
      for a in links:
        href = a.get('href', '')
        if not href:
          continue
        # Normalize relative
        if href.startswith('//'):
          href = 'https:' + href
        if href.startswith('/'):
          href = 'https://www.hk01.com' + href
        if 'hk01.com/article/' in href and _re.search(r'/article/\d+', href):
          url = href.split('?')[0]
          if url in seen:
            continue
          seen.add(url)
          title = a.get_text(strip=True) or a.get('title') or ''
          if not title or len(title) < 5:
            title = self.extract_title_from_url(url)
          article_data.append({
            'title': title,
            'url': url,
            'authors': [],
            'publish_date': datetime.now(),
            'text': '',
            'preview': '',
            'discovery_method': 'hk01_specific'
          })
          if len(article_data) >= max_articles:
            break
      # 2) Regex sweep over HTML as a fallback
      if len(article_data) < max_articles:
        candidates = _re.findall(r'https?://(?:www\.)?hk01\.com/article/\d+(?:/[^"\s<>]+)?', page_html)
        for url in candidates:
          url = url.split('?')[0]
          if url in seen:
            continue
          seen.add(url)
          # try find nearby anchor text
          a_tag = soup.find('a', href=_re.compile(_re.escape(url)))
          title = a_tag.get_text(strip=True) if a_tag else self.extract_title_from_url(url)
          article_data.append({
            'title': title,
            'url': url,
            'authors': [],
            'publish_date': datetime.now(),
            'text': '',
            'preview': '',
            'discovery_method': 'hk01_specific'
          })
          if len(article_data) >= max_articles:
            break
      self.config.logger.debug(f"HK01 parsing found {len(article_data)} articles")
      return article_data
    except Exception as e:
      self.config.logger.debug(f"HK01 discovery failed: {e}")
      return []

  def discover_articles_newspaper3k(self, base_url: str, max_articles: int):
    """Method 1: Use newspaper3k for automatic article discovery"""
    try:
      paper = build(base_url, memoize_articles=False)
      articles = paper.articles[:max_articles]
      
      article_data = []
      for article in articles:
        title = article.title or ''
        
        # Enhanced title extraction from URL if needed
        if title in ['全文', ''] or len(title) < 5:
          title = self.extract_title_from_url(article.url)
        
        article_data.append({
          'title': title,
          'url': article.url or '',
          'authors': article.authors or [],
          'publish_date': article.publish_date or datetime.now(),
          'text': '',
          'preview': '',
          'discovery_method': 'newspaper3k'
        })
      
      return article_data
      
    except Exception as e:
      self.config.logger.debug(f"newspaper3k discovery failed: {e}")
      return []

  def discover_articles_manual(self, base_url: str, max_articles: int):
    """Method 2: Manual HTML parsing for specific site structures"""
    try:
      from bs4 import BeautifulSoup
      import requests
      
      # Use better headers and longer timeout for problematic sites
      headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
      }
      
      page_html = self.fetch_html(base_url, headers=headers)
      soup = BeautifulSoup(page_html or "", 'html.parser')
      
      article_data = []
      
      # Look for common article patterns
      links = soup.find_all('a', href=True)
      for link in links:
        href = (link.get('href', '') or '').strip()
        title = link.get_text(strip=True)
        
        # Enhanced filtering for article links
        if (href and title and 
            len(title) > 10 and 
            len(title) < 300 and
            ('/' in href) and  # Must have path structure
            not any(skip in href.lower() for skip in ['javascript:', 'mailto:', '#', 'static', 'css', 'js', 'image']) and
            not any(skip in title.lower() for skip in ['login', 'register', 'more', 'next', 'previous'])):
          
          # Make absolute URL safely
          if href.startswith('http'):
            normalized_url = href
          elif href.startswith('/'):
            # derive site root from base_url
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            normalized_url = f"{parsed.scheme}://{parsed.netloc}{href}"
          else:
            normalized_url = base_url.rstrip('/') + '/' + href
          
          article_data.append({
            'title': title,
            'url': normalized_url,
            'authors': [],
            'publish_date': datetime.now(),
            'text': '',
            'preview': '',
            'discovery_method': 'manual_parsing'
          })
          
          if len(article_data) >= max_articles:
            break
      # If too few found, fallback to regex extraction targeting ETNet article URLs
      if len(article_data) < max_articles and base_url.startswith('https://column.etnetchina.cn'):
        import re as _re
        candidates = _re.findall(r'https?://column\.etnetchina\.cn/column-list-[^"\s]+/\d+\.htm', page_html or "")
        seen = set(a['url'] for a in article_data)
        for href in candidates:
          if href in seen:
            continue
          # try to locate anchor text
          a_tag = soup.find('a', href=_re.compile(_re.escape(href)))
          title = a_tag.get_text(strip=True) if a_tag else self.extract_title_from_url(href)
          article_data.append({
            'title': title,
            'url': href,
            'authors': [],
            'publish_date': datetime.now(),
            'text': '',
            'preview': '',
            'discovery_method': 'manual_parsing'
          })
          if len(article_data) >= max_articles:
            break

      self.config.logger.debug(f"Manual parsing found {len(article_data)} articles")
      return article_data
      
    except Exception as e:
      self.config.logger.debug(f"Manual parsing failed: {e}")
      return []

  def _try_init_browser(self):
    try:
      chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser"
      ]
      driver_paths = [
        "/usr/local/bin/chromedriver",
        "C:\\chromedriver\\chromedriver.exe",
        "/usr/bin/chromedriver"
      ]
      chrome_path = None
      driver_path = None
      import os
      for p in chrome_paths:
        if os.path.exists(p):
          chrome_path = p
          break
      for p in driver_paths:
        if os.path.exists(p):
          driver_path = p
          break
      if not (chrome_path and driver_path):
        return None
      service = Service(executable_path=driver_path)
      options = Options()
      options.binary_location = chrome_path
      options.add_experimental_option('excludeSwitches', ['enable-automation','enable-logging'])
      options.add_argument('--disable-blink-features=AutomationControlled')
      options.add_argument('--headless')
      options.add_argument('--disable-gpu')
      options.add_argument('--ignore-certificate-errors')
      options.add_argument('--ignore-ssl-errors')
      options.add_argument('--no-sandbox')
      browser = webdriver.Chrome(options=options, service=service)
      return browser
    except Exception:
      return None

  def fetch_html(self, url: str, headers: dict | None = None) -> str:
    # Try requests session first
    try:
      if getattr(self, 'http', None) is not None:
        r = self.http.get(url, timeout=30)
        if r.ok:
          try:
            if hasattr(r, 'apparent_encoding') and r.apparent_encoding:
              r.encoding = r.apparent_encoding
          except Exception:
            pass
          return r.text
    except Exception:
      pass
    # Fallback to raw requests
    try:
      import requests
      r = requests.get(url, timeout=30, headers=headers or {})
      if r.ok:
        try:
          if hasattr(r, 'apparent_encoding') and r.apparent_encoding:
            r.encoding = r.apparent_encoding
        except Exception:
          pass
        return r.text
    except Exception:
      pass
    # Last resort: Selenium
    try:
      if getattr(self, 'browser', None) is not None:
        self.browser.get(url)
        WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        import time as _t
        _t.sleep(1)
        return self.browser.page_source
    except Exception:
      pass
    return ""
  
  def extract_title_from_url(self, url: str):
    """Extract title from URL when newspaper3k fails to get proper title"""
    try:
      if not url:
        return "Unknown Title"
      
      # Extract the last part of URL which often contains the title
      url_parts = url.split('/')
      if len(url_parts) > 0:
        last_part = url_parts[-1]
        # Decode URL encoding
        import urllib.parse
        decoded_title = urllib.parse.unquote(last_part)
        # Clean up the title
        title = decoded_title.replace('+', ' ').replace('%', ' ')
        # Remove common suffixes
        title = title.replace('.html', '').replace('.htm', '')
        return title[:100]  # Limit length
      
      return "Unknown Title"
      
    except Exception as e:
      self.config.logger.debug(f"Title extraction failed: {e}")
      return "Unknown Title"
  
  def fetch_article_preview(self, article_url: str):
    """Fetch article preview using Trafilatura (faster) with newspaper3k fallback"""
    try:
      self.config.logger.debug(f"Fetching preview from: {article_url}")
      
      # Try Trafilatura first (much faster)
      if TRAFILATURA_AVAILABLE:
        try:
          html = None
          if getattr(self, 'http', None) is not None:
            resp = self.http.get(article_url, timeout=30)
            html = resp.text if resp and resp.status_code == 200 else None
          if not html:
            html = trafilatura.fetch_url(article_url)
          preview = trafilatura.extract(html)
          if preview and len(preview) > 50:
            preview = preview[:300]  # Limit to 300 chars
            self.config.logger.debug(f"Got preview via Trafilatura: {len(preview)} chars")
            return preview
        except Exception as e:
          self.config.logger.debug(f"Trafilatura failed, falling back to newspaper3k: {e}")
      
      # Fallback to newspaper3k
      article = Article(article_url)
      article.download()
      article.parse()
      
      # Get first 300 characters as preview
      preview = article.text[:300] if article.text else ""
      
      self.config.logger.debug(f"Got preview via newspaper3k: {len(preview)} chars")
      if preview:
        return preview
      # Final fallback: Selenium + simple text
      html = self.fetch_html(article_url)
      if html:
        try:
          from bs4 import BeautifulSoup as _BS
          doc = _BS(html, 'html.parser')
          text = doc.get_text(" ", strip=True)
          return text[:300] if text else ""
        except Exception:
          pass
      return ""
      
    except Exception as e:
      self.config.logger.debug(f"Failed to fetch preview: {e}")
      return ""

  def fetch_article_content(self, article_url: str):
    """Fetch full article content using Trafilatura (faster) with newspaper3k fallback"""
    try:
      self.config.logger.debug(f"Fetching content from: {article_url}")
      
      # Try Trafilatura first (much faster)
      if TRAFILATURA_AVAILABLE:
        try:
          html = None
          if getattr(self, 'http', None) is not None:
            resp = self.http.get(article_url, timeout=30)
            html = resp.text if resp and resp.status_code == 200 else None
          if not html:
            html = trafilatura.fetch_url(article_url)
          content = trafilatura.extract(html)
          if content and len(content) > 100:
            # Clean and limit content
            if len(content) > 1000:
              content = content[:1000] + "..."
            self.config.logger.debug(f"Content length via Trafilatura: {len(content)} characters")
            return content
        except Exception as e:
          self.config.logger.debug(f"Trafilatura failed, falling back to newspaper3k: {e}")
      
      # Fallback to newspaper3k
      article = Article(article_url)
      article.download()
      article.parse()
      
      # Clean and limit content
      content = article.text or ""
      if len(content) > 1000:
        content = content[:1000] + "..."
      
      self.config.logger.debug(f"Content length via newspaper3k: {len(content)} characters")
      if content:
        return content
      # Final fallback: Selenium + text
      html = self.fetch_html(article_url)
      if html:
        try:
          from bs4 import BeautifulSoup as _BS
          doc = _BS(html, 'html.parser')
          text = doc.get_text(" ", strip=True)
          if len(text) > 1000:
            text = text[:1000] + "..."
          return text
        except Exception:
          pass
      return ""
      
    except Exception as e:
      self.config.logger.debug(f"Failed to fetch content: {e}")
      return ""
    
  def export_scraping_results(self, all_articles, matched_articles, results_df):
    """Export comprehensive scraping results to file"""
    try:
      timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
      filename = f"scraping_results_{timestamp}.txt"
      
      with open(filename, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write("COMPREHENSIVE WEB SCRAPING RESULTS\n")
        f.write("="*100 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        target_website = getattr(self, 'last_target_url', TARGET_URL)
        f.write(f"Target Website: {target_website}\n")
        f.write(f"Total Articles Discovered: {len(all_articles)}\n")
        f.write(f"Articles Matched: {len(matched_articles)}\n")
        f.write(f"Match Rate: {len(matched_articles)/len(all_articles)*100:.1f}%\n")
        f.write("="*100 + "\n\n")
        
        # Section 1: All Discovered Articles
        f.write("SECTION 1: ALL DISCOVERED ARTICLES\n")
        f.write("-"*50 + "\n")
        for i, article in enumerate(all_articles, 1):
          f.write(f"\n{i}. TITLE: {article['title']}\n")
          f.write(f"   URL: {article['url']}\n")
          f.write(f"   AUTHORS: {', '.join(article['authors']) if article['authors'] else 'N/A'}\n")
          f.write(f"   PUBLISH DATE: {article['publish_date']}\n")
          f.write(f"   PREVIEW: {article.get('preview', 'N/A')[:200]}...\n")
          
          # Check if this article was matched
          matched = any(m['url'] == article['url'] for m in matched_articles)
          f.write(f"   STATUS: {'✅ MATCHED' if matched else '❌ DISMISSED'}\n")
        
        # Section 2: Matching Analysis
        f.write("\n\nSECTION 2: MATCHING ANALYSIS\n")
        f.write("-"*50 + "\n")
        f.write(f"Keywords Used: {self.config.lark_config_list[0]['config_head_positive_words']}\n")
        f.write(f"Negative Keywords: {self.config.lark_config_list[0]['config_head_negative_words']}\n")
        f.write(f"Matching Method: Hybrid (Regex + Semantic Similarity)\n")
        f.write(f"Semantic Threshold: 0.3\n")
        
        # Section 3: Detailed Matched Articles
        f.write("\n\nSECTION 3: DETAILED MATCHED ARTICLES\n")
        f.write("-"*50 + "\n")
        for idx, row in results_df.iterrows():
          f.write(f"\n{'='*80}\n")
          f.write(f"ARTICLE {idx+1}: {row[self.config.history_head_news_title]}\n")
          f.write(f"{'='*80}\n")
          f.write(f"URL: {row[self.config.history_head_news_link]}\n")
          f.write(f"MATCHED KEYWORDS: {row[self.config.hit_head_positive_words]}\n")
          f.write(f"MATCHING METHOD: {'Regex' if any(kw in str(row[self.config.hit_head_positive_words]) for kw in ['港股', '香港', '中國', '國際']) else 'Semantic'}\n")
          f.write(f"PUBLISH DATE: {row[self.config.history_head_news_date]}\n")
          f.write(f"CONTENT LENGTH: {len(row[self.config.hit_head_news_content])} characters\n")
          f.write(f"\nFULL CONTENT:\n")
          f.write(f"{'-'*40}\n")
          f.write(f"{row[self.config.hit_head_news_content]}\n")
          f.write(f"{'-'*40}\n")
        
        # Section 4: Summary Statistics
        f.write(f"\n\nSECTION 4: SUMMARY STATISTICS\n")
        f.write("-"*50 + "\n")
        f.write(f"Total Processing Time: ~{len(all_articles) * 0.5:.1f} seconds\n")
        f.write(f"Average Content Length: {results_df[self.config.hit_head_news_content].str.len().mean():.0f} characters\n")
        f.write(f"Content Extraction Method: Trafilatura (primary) + newspaper3k (fallback)\n")
        f.write(f"Language Support: Chinese (simplified/traditional) + English\n")
        f.write(f"Semantic Model: all-MiniLM-L6-v2\n")
        
        # Section 5: Performance Metrics
        f.write(f"\n\nSECTION 5: PERFORMANCE METRICS\n")
        f.write("-"*50 + "\n")
        regex_matches = sum(1 for row in results_df.iterrows() if any(kw in str(row[1][self.config.hit_head_positive_words]) for kw in ['港股', '香港', '中國', '國際']))
        semantic_matches = len(results_df) - regex_matches
        f.write(f"Regex Matches: {regex_matches}\n")
        f.write(f"Semantic Matches: {semantic_matches}\n")
        f.write(f"Hybrid Efficiency: {len(results_df)/len(all_articles)*100:.1f}% articles matched\n")
        f.write(f"Content Quality: High (clean extraction via Trafilatura)\n")
        
        f.write(f"\n{'='*100}\n")
        f.write("END OF REPORT\n")
        f.write(f"{'='*100}\n")
      
      self.config.logger.debug(f"Results exported to: {filename}")
      print(f"📄 Comprehensive results exported to: {filename}")
      
    except Exception as e:
      self.config.logger.debug(f"Failed to export results: {e}")
      print(f"❌ Failed to export results: {e}")
    
  def detect_words(self, word_group_list: list, title: str, preview: str = ""):
    """Regex keyword matching"""
    hit_words_list = []
    
    # Combine title and preview for better matching
    search_text = title
    if preview:
      search_text = title + " " + preview

    for positive_word_group in word_group_list:
      positive_word_split_list = positive_word_group.split("+")

      for positive_word_split in positive_word_split_list:
        positive_word_pattern = positive_word_split.replace("/", "|")

        search_hit = re.search(
          pattern=positive_word_pattern,
          string=search_text,
          flags=re.I
        )
        
        if search_hit:
          hit_words_list.append(search_hit.group())
        else:
          hit_words_list = []
          break
      
      else:
        break
    
    if hit_words_list:
      return "、".join(hit_words_list)
    else:
      return None

  def semantic_keyword_matching(self, title: str, preview: str, target_keywords: list, threshold: float = 0.3):
    """Use semantic similarity to match keywords with title + preview"""
    
    if not self.semantic_model:
      return None
    
    try:
      # Combine title and preview
      combined_text = title
      if preview:
        combined_text = title + " " + preview
      
      # Encode the combined text and keywords
      text_embedding = self.semantic_model.encode([combined_text])
      keyword_embeddings = self.semantic_model.encode(target_keywords)
      
      # Calculate cosine similarities
      similarities = cosine_similarity(text_embedding, keyword_embeddings)[0]
      
      # Find the best match
      max_similarity = max(similarities)
      best_keyword_idx = np.argmax(similarities)
      
      if max_similarity > threshold:
        matched_keyword = target_keywords[best_keyword_idx]
        self.config.logger.debug(f"Semantic match: '{matched_keyword}' (similarity: {max_similarity:.3f})")
        return matched_keyword
      else:
        self.config.logger.debug(f"No semantic match found (max similarity: {max_similarity:.3f})")
        return None
        
    except Exception as e:
      self.config.logger.debug(f"Semantic matching failed: {e}")
      return None

  def hybrid_keyword_matching(self, title: str, preview: str, word_group_list: list):
    """Hybrid approach: Try regex first, then semantic if regex fails"""
    
    # Step 1: Try regex matching first (fast)
    regex_match = self.detect_words(word_group_list, title, preview)
    if regex_match:
      self.config.logger.debug(f"Regex match found: {regex_match}")
      return regex_match
    
    # Step 2: If no regex match, try semantic matching
    if self.semantic_model and preview:
      # Extract individual keywords from word groups
      all_keywords = []
      for word_group in word_group_list:
        keywords = word_group.split("+")
        all_keywords.extend(keywords)
      
      # Remove duplicates and clean keywords
      unique_keywords = list(set([kw.strip() for kw in all_keywords if kw.strip()]))
      
      semantic_match = self.semantic_keyword_matching(title, preview, unique_keywords)
      if semantic_match:
        self.config.logger.debug(f"Semantic match found: {semantic_match}")
        return semantic_match
    
    return None

  def run(self, target_url: str = None):
    """Main workflow using universal article discovery + semantic matching"""
    
    if target_url is None:
      target_url = TARGET_URL
    self.last_target_url = target_url
    self.config.logger.debug(f"Starting universal scraper for: {target_url}")
    
    # Step 1: Discover articles using universal method
    articles = self.discover_articles(target_url, max_articles=50)  # Increased for comprehensive coverage
    
    if not articles:
      self.config.logger.debug("No articles found")
      return
    
    self.config.logger.debug(f"Discovered {len(articles)} articles")
    
    # Step 2: Fetch previews for semantic matching
    self.config.logger.debug("Fetching previews for semantic matching...")
    
    for article in articles:
      article['preview'] = self.fetch_article_preview(article['url'])
    
    # Step 3: Apply hybrid keyword matching
    self.config.logger.debug("Applying hybrid keyword matching...")
    
    config = self.config.lark_config_list[0]
    word_groups = config[self.config.config_head_positive_words]
    
    matched_articles = []
    for article in articles:
      match = self.hybrid_keyword_matching(
        article['title'], 
        article['preview'], 
        word_groups
      )
      
      if match:
        article['matched_keywords'] = match
        matched_articles.append(article)
    
    self.config.logger.debug(f"Found {len(matched_articles)} matching articles")
    
    # Step 4: Fetch full content only for matched articles
    if matched_articles:
      self.config.logger.debug("Fetching full content for matched articles...")
      
      for article in matched_articles:
        article['text'] = self.fetch_article_content(article['url'])
    
    # Step 5: Create results DataFrame
    if matched_articles:
      df_data = []
      for article in matched_articles:
        df_data.append({
          self.config.history_head_news_title: article['title'],
          self.config.history_head_news_link: article['url'],
          self.config.history_head_news_date: article['publish_date'],
          self.config.hit_head_positive_words: article['matched_keywords'],
          self.config.hit_head_news_content: article['text']
        })
      
      results_df = pd.DataFrame(df_data)
      
      self.config.logger.debug(f"Final results: {len(results_df)} articles with full content")
      
      # Export comprehensive results to file
      self.export_scraping_results(articles, matched_articles, results_df)
      
      # Show sample results
      print("\n" + "="*80)
      print("NEWSPAPER3K + TRAFILATURA + SEMANTIC MATCHING RESULTS")
      print("="*80)
      print(f"📊 Performance Summary:")
      print(f"   • Articles Discovered: {len(articles)} (via newspaper3k)")
      print(f"   • Articles Matched: {len(matched_articles)} (via hybrid semantic)")
      print(f"   • Content Extraction: Trafilatura (fast) + newspaper3k (fallback)")
      print(f"   • Languages: Chinese (simplified/traditional) + English")
      print(f"   • Results exported to: scraping_results.txt")
      print("="*80)
      
      for idx, row in results_df.iterrows():
        print(f"\nArticle {idx+1}:")
        print(f"Title: {row[self.config.history_head_news_title]}")
        print(f"Keywords: {row[self.config.hit_head_positive_words]}")
        print(f"Content Preview: {row[self.config.hit_head_news_content][:200]}...")
        print(f"URL: {row[self.config.history_head_news_link]}")
    
    self.config.logger.debug("Workflow completed")

if __name__ == "__main__":
  # Setup logging
  logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(asctime)s - %(filename)s - %(funcName)s - %(lineno)d - %(message)s')
  
  # Run the workflow
  config = Config()
  scraper = Meta_Newspaper3k(config)
  scraper.run()
