#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import pandas as pd
import re
from datetime import datetime
from newspaper import build, Article

# Import for semantic similarity
try:
  from sentence_transformers import SentenceTransformer
  from sklearn.metrics.pairwise import cosine_similarity
  import numpy as np
  SEMANTIC_AVAILABLE = True
except ImportError:
  SEMANTIC_AVAILABLE = False
  print("Semantic matching not available - install sentence-transformers and scikit-learn")

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
    """Use newspaper3k to discover articles from news site"""
    try:
      self.config.logger.debug(f"Discovering articles from: {base_url}")
      
      # Build newspaper object
      paper = build(base_url, memoize_articles=False)
      
      # Get articles
      articles = paper.articles[:max_articles]
      
      self.config.logger.debug(f"Found {len(articles)} articles")
      
      # Extract basic info
      article_data = []
      for article in articles:
        article_data.append({
          'title': article.title or '',
          'url': article.url or '',
          'authors': article.authors or [],
          'publish_date': article.publish_date or datetime.now(),
          'text': '',  # Will be filled later
          'preview': ''  # Will be filled later
        })
      
      return article_data
      
    except Exception as e:
      self.config.logger.debug(f"Article discovery failed: {e}")
      return []

  def fetch_article_preview(self, article_url: str):
    """Fetch article preview using newspaper3k"""
    try:
      self.config.logger.debug(f"Fetching preview from: {article_url}")
      
      article = Article(article_url)
      article.download()
      article.parse()
      
      # Get first 300 characters as preview
      preview = article.text[:300] if article.text else ""
      
      self.config.logger.debug(f"Got preview: {len(preview)} chars")
      return preview
      
    except Exception as e:
      self.config.logger.debug(f"Failed to fetch preview: {e}")
      return ""

  def fetch_article_content(self, article_url: str):
    """Fetch full article content using newspaper3k"""
    try:
      self.config.logger.debug(f"Fetching content from: {article_url}")
      
      article = Article(article_url)
      article.download()
      article.parse()
      
      # Clean and limit content
      content = article.text or ""
      if len(content) > 1000:
        content = content[:1000] + "..."
      
      self.config.logger.debug(f"Content length: {len(content)} characters")
      return content
      
    except Exception as e:
      self.config.logger.debug(f"Failed to fetch content: {e}")
      return ""

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

  def run(self):
    """Main workflow using newspaper3k + semantic matching"""
    
    self.config.logger.debug("Starting newspaper3k + semantic workflow")
    
    # Step 1: Discover articles using newspaper3k
    base_url = "https://www.hkej.com/instantnews"
    articles = self.discover_articles(base_url, max_articles=30)
    
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
      
      # Show sample results
      print("\n" + "="*80)
      print("NEWSPAPER3K + SEMANTIC MATCHING RESULTS")
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
