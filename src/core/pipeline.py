from typing import Literal, Dict, Any
import os
import time
import asyncio
from src.core.bypass import fetch_rendered
from src.extractors.extract_structured import extract_structured
from src.extractors.extract_readable import readable_article
from src.extractors.extract_patterns import find_prices
from src.extractors.extract_scrapegraph import scrapegraph_article, scrapegraph_product
from src.core.schemas import Article, Product
from bs4 import BeautifulSoup

def _first(*vals): 
    return next((v for v in vals if v), None)

async def extract(url: str, kind: Literal["article","product"], llmMode: Literal["none", "llm", "auto"] = "auto") -> Dict[str, Any]:
    start_time = time.time()
    
    # 1) Render
    try:
        html = await fetch_rendered(url)
        if not html or len(html.strip()) < 100:
            # If HTML is empty or too short, fallback to LLM for all modes
            if llmMode == "none":
                # For none mode, return minimal data
                if kind == "article":
                    article = Article(url=url)
                    data = article.model_dump()
                    data["_method_used"] = "Failed to Load Content"
                    exec_ms = int((time.time() - start_time) * 1000)
                    data["_execution_time"] = exec_ms
                    data["_execution_time_unit"] = "ms"
                    data["_error"] = "Page failed to load or returned empty content"
                    return data
                else:  # product
                    product = Product(url=url)
                    data = product.model_dump()
                    data["_method_used"] = "Failed to Load Content"
                    exec_ms = int((time.time() - start_time) * 1000)
                    data["_execution_time"] = exec_ms
                    data["_execution_time_unit"] = "ms"
                    data["_error"] = "Page failed to load or returned empty content"
                    return data
            else:
                # For llm and auto modes, use LLM as fallback
                llmMode = "llm"
    except Exception as e:
        # If fetching completely fails, handle based on mode
        if llmMode == "none":
            if kind == "article":
                article = Article(url=url)
                data = article.model_dump()
                data["_method_used"] = "Failed to Load Content"
                exec_ms = int((time.time() - start_time) * 1000)
                data["_execution_time"] = exec_ms
                data["_execution_time_unit"] = "ms"
                data["_error"] = f"Failed to fetch page: {str(e)}"
                return data
            else:  # product
                product = Product(url=url)
                data = product.model_dump()
                data["_method_used"] = "Failed to Load Content"
                exec_ms = int((time.time() - start_time) * 1000)
                data["_execution_time"] = exec_ms
                data["_execution_time_unit"] = "ms"
                data["_error"] = f"Failed to fetch page: {str(e)}"
                return data
        else:
            # For llm and auto modes, use LLM as fallback
            llmMode = "llm"
            html = ""  # Empty HTML for LLM fallback

    if kind == "article":
        article = Article(url=url)
        
        # Handle different LLM modes
        if llmMode == "llm":
            # LLM Only - Skip other methods, use LLM directly
            # Check for cancellation before expensive LLM call
            await asyncio.sleep(0)  # Allow cancellation
            sg_response = scrapegraph_article(url)
            sg = sg_response.get("result", sg_response)
            token_usage = sg_response.get("token_usage", {})
            
            article.title = _first(article.title, sg.get("title"))
            article.author = _first(article.author, sg.get("author"))
            article.date_published = _first(article.date_published, sg.get("date_published") or sg.get("date"))
            article.text = _first(article.text, sg.get("text") or sg.get("content"))
            imgs = sg.get("images") or []
            if isinstance(imgs, list): article.images = imgs
            
            data = article.model_dump()
            data["_method_used"] = "LLM Direct"
            exec_ms = int((time.time() - start_time) * 1000)
            data["_execution_time"] = exec_ms
            data["_execution_time_unit"] = "ms"
            
            model_name = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini").lower()
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
                output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
                total_tokens = token_usage.get("total_tokens", input_tokens + output_tokens)
                
                data["_llm_usage"] = {
                    "model": model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens
                }
            return data
            
        elif llmMode == "none":
            # Non-LLM Only - Use only structured data and readability
            sd = extract_structured(html, base_url=url)
            # naive mapping from JSON-LD if available
            for item in sd["ld"]:
                t = item.get("@type") or item.get("type")
                if isinstance(t, list): t = next((x for x in t if isinstance(x, str)), None)
                if t in ("NewsArticle","Article","BlogPosting"):
                    article.title = _first(article.title, item.get("headline"), item.get("name"))
                    article.author = _first(article.author, (item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else None)
                    article.date_published = _first(article.date_published, item.get("datePublished"))
                    if item.get("articleBody"): article.text = _first(article.text, item["articleBody"])
            
            # Readability fallback
            r = readable_article(html)
            if r.get("title") and r.get("text"):
                article.title = _first(article.title, r["title"])
                article.text  = _first(article.text,  r["text"])
            
            data = article.model_dump()
            data["_method_used"] = "Structured Data + Readability"
            exec_ms = int((time.time() - start_time) * 1000)
            data["_execution_time"] = exec_ms
            data["_execution_time_unit"] = "ms"
            return data
            
        else:  # llmMode == "auto"
            # Auto (Fallback) - Try structured data first, then LLM if needed
            sd = extract_structured(html, base_url=url)
            
            # Try structured data extraction first
            for item in sd["ld"]:
                t = item.get("@type") or item.get("type")
                if isinstance(t, list): t = next((x for x in t if isinstance(x, str)), None)
                if t in ("NewsArticle","Article","BlogPosting"):
                    article.title = _first(article.title, item.get("headline"), item.get("name"))
                    article.author = _first(article.author, (item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else None)
                    article.date_published = _first(article.date_published, item.get("datePublished"))
                    if item.get("articleBody"): article.text = _first(article.text, item["articleBody"])
            
            # Try readability extraction
            r = readable_article(html)
            if r.get("title") and r.get("text"):
                article.title = _first(article.title, r["title"])
                article.text = _first(article.text, r["text"])
            
            # Check if we have sufficient data, if not, fallback to LLM
            has_sufficient_data = article.title and article.text and len(article.text) > 100
            
            if has_sufficient_data:
                data = article.model_dump()
                data["_method_used"] = "Smart Fallback (Structured Data)"
                exec_ms = int((time.time() - start_time) * 1000)
                data["_execution_time"] = exec_ms
                data["_execution_time_unit"] = "ms"
                return data
            else:
                # Fallback to LLM
                # Check for cancellation before expensive LLM call
                await asyncio.sleep(0)  # Allow cancellation
                sg_response = scrapegraph_article(url)
                sg = sg_response.get("result", sg_response)
                token_usage = sg_response.get("token_usage", {})
                
                article.title = _first(article.title, sg.get("title"))
                article.author = _first(article.author, sg.get("author"))
                article.date_published = _first(article.date_published, sg.get("date_published") or sg.get("date"))
                article.text = _first(article.text, sg.get("text") or sg.get("content"))
                imgs = sg.get("images") or []
                if isinstance(imgs, list): article.images = imgs
                
                data = article.model_dump()
                data["_method_used"] = "Smart Fallback (LLM)"
                exec_ms = int((time.time() - start_time) * 1000)
                data["_execution_time"] = exec_ms
                data["_execution_time_unit"] = "ms"
                
                model_name = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini").lower()
                if token_usage:
                    input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
                    output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
                    total_tokens = token_usage.get("total_tokens", input_tokens + output_tokens)
                    
                    data["_llm_usage"] = {
                        "model": model_name,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens
                    }
                return data

    if kind == "product":
        product = Product(url=url)
        
        # Handle different LLM modes
        if llmMode == "llm":
            # LLM Only - Skip other methods, use LLM directly
            # Check for cancellation before expensive LLM call
            await asyncio.sleep(0)  # Allow cancellation
            sg_response = scrapegraph_product(url)
            sg = sg_response.get("result", sg_response)
            token_usage = sg_response.get("token_usage", {})
            
            product.name = _first(product.name, sg.get("name") or sg.get("title"))
            product.price = _first(product.price, sg.get("price"))
            product.currency = _first(product.currency, sg.get("currency"))
            product.description = _first(product.description, sg.get("description"))
            imgs = sg.get("images") or []
            if isinstance(imgs, list): product.images = imgs

            data = product.model_dump()
            data["_method_used"] = "AI-Powered (Direct LLM)"
            exec_ms = int((time.time() - start_time) * 1000)
            data["_execution_time"] = exec_ms
            data["_execution_time_unit"] = "ms"
            
            model_name = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini").lower()
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
                output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
                total_tokens = token_usage.get("total_tokens", input_tokens + output_tokens)
                
                data["_llm_usage"] = {
                    "model": model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens
                }
            return data
            
        elif llmMode == "none":
            # Non-LLM Only - Use only structured data and readability
            sd = extract_structured(html, base_url=url)
            # JSON-LD mapping
            for item in sd["ld"]:
                t = item.get("@type") or item.get("type")
                if isinstance(t, list): t = next((x for x in t if isinstance(x, str)), None)
                if t in ("Product",):
                    product.name = _first(product.name, item.get("name"))
                    offers = item.get("offers") or {}
                    if isinstance(offers, dict):
                        product.price = _first(product.price, offers.get("price"))
                        product.currency = _first(product.currency, offers.get("priceCurrency"))
                    product.description = _first(product.description, item.get("description"))
            
            # Heuristic: parse visible text for prices
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
            prices = find_prices(text)
            if prices and not product.price:
                product.price = prices[0]
            
            data = product.model_dump()
            data["_method_used"] = "Structured Data + Price Detection"
            exec_ms = int((time.time() - start_time) * 1000)
            data["_execution_time"] = exec_ms
            data["_execution_time_unit"] = "ms"
            return data
            
        else:  # llmMode == "auto"
            # Auto (Fallback) - Try structured data first, then LLM if needed
            sd = extract_structured(html, base_url=url)
            
            # Try structured data extraction first
            for item in sd["ld"]:
                t = item.get("@type") or item.get("type")
                if isinstance(t, list): t = next((x for x in t if isinstance(x, str)), None)
                if t in ("Product",):
                    product.name = _first(product.name, item.get("name"))
                    offers = item.get("offers") or {}
                    if isinstance(offers, dict):
                        product.price = _first(product.price, offers.get("price"))
                        product.currency = _first(product.currency, offers.get("priceCurrency"))
                    product.description = _first(product.description, item.get("description"))
            
            # Try price detection
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
            prices = find_prices(text)
            if prices and not product.price:
                product.price = prices[0]
            
            # Check if we have sufficient data, if not, fallback to LLM
            has_sufficient_data = product.name and (product.price or product.description)
            
            if has_sufficient_data:
                data = product.model_dump()
                data["_method_used"] = "Smart Fallback (Structured Data)"
                exec_ms = int((time.time() - start_time) * 1000)
                data["_execution_time"] = exec_ms
                data["_execution_time_unit"] = "ms"
                return data
            else:
                # Fallback to LLM
                # Check for cancellation before expensive LLM call
                await asyncio.sleep(0)  # Allow cancellation
                sg_response = scrapegraph_product(url)
                sg = sg_response.get("result", sg_response)
                token_usage = sg_response.get("token_usage", {})
                
                product.name = _first(product.name, sg.get("name") or sg.get("title"))
                product.price = _first(product.price, sg.get("price"))
                product.currency = _first(product.currency, sg.get("currency"))
                product.description = _first(product.description, sg.get("description"))
                imgs = sg.get("images") or []
                if isinstance(imgs, list): product.images = imgs

                data = product.model_dump()
                data["_method_used"] = "Smart Fallback (LLM)"
                exec_ms = int((time.time() - start_time) * 1000)
                data["_execution_time"] = exec_ms
                data["_execution_time_unit"] = "ms"
                
                model_name = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini").lower()
                if token_usage:
                    input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
                    output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
                    total_tokens = token_usage.get("total_tokens", input_tokens + output_tokens)
                    
                    data["_llm_usage"] = {
                        "model": model_name,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens
                    }
                return data

    raise ValueError("Unknown kind")
