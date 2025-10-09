"""
ScrapeGraphAI Labs Implementation
Provides functional implementations for various ScrapeGraphAI graphs
"""

import os
import asyncio
import concurrent.futures
from typing import List, Dict, Any
from scrapegraphai.graphs import (
    SmartScraperGraph, 
    SearchGraph, 
    SpeechGraph, 
    ScriptCreatorGraph,
    SmartScraperMultiGraph,
    ScriptCreatorMultiGraph
)
from .llm_wrapper import get_token_usage, clear_token_usage


def get_base_config() -> Dict[str, Any]:
    """Get base configuration for ScrapeGraphAI graphs"""
    model = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise RuntimeError("LLM API key missing: set OPENAI_API_KEY")
    
    return {
        "llm": {
            "model": model,
            "api_key": api_key
        },
        "verbose": True,
        "headless": True,
        "model_tokens": 128000
    }


def run_smart_scraper(url: str, prompt: str) -> Dict[str, Any]:
    """Run SmartScraperGraph for single page extraction"""
    clear_token_usage()
    
    config = get_base_config()
    
    try:
        graph = SmartScraperGraph(
            prompt=prompt,
            source=url,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "SmartScraperGraph"
        }
    except Exception as e:
        return {"error": str(e)}


def run_search_graph(query: str, count: int, prompt: str) -> Dict[str, Any]:
    """Run SearchGraph for multi-page search-based extraction"""
    clear_token_usage()
    
    config = get_base_config()
    
    # Check for Bing Search API key
    bing_api_key = os.getenv("BING_SEARCH_API_KEY")
    if not bing_api_key:
        raise RuntimeError("Bing Search API key missing: set BING_SEARCH_API_KEY")
    
    config["search"] = {
        "api_key": bing_api_key,
        "engine": "bing"
    }
    
    try:
        graph = SearchGraph(
            prompt=prompt,
            source=query,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "SearchGraph"
        }
    except Exception as e:
        return {"error": str(e)}


def run_speech_graph(url: str, prompt: str) -> Dict[str, Any]:
    """Run SpeechGraph for audio generation"""
    clear_token_usage()
    
    config = get_base_config()
    config["tts_model"] = {
        "model": "tts-1",
        "api_key": os.getenv("OPENAI_API_KEY")
    }
    
    try:
        graph = SpeechGraph(
            prompt=prompt,
            source=url,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "SpeechGraph"
        }
    except Exception as e:
        return {"error": str(e)}


def run_script_creator(url: str, prompt: str) -> Dict[str, Any]:
    """Run ScriptCreatorGraph for Python script generation"""
    clear_token_usage()
    
    config = get_base_config()
    config["library"] = "requests"
    
    try:
        graph = ScriptCreatorGraph(
            prompt=prompt,
            source=url,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "ScriptCreatorGraph"
        }
    except Exception as e:
        return {"error": str(e)}


def run_smart_scraper_multi(urls: List[str], prompt: str) -> Dict[str, Any]:
    """Run SmartScraperMultiGraph for multi-page extraction"""
    clear_token_usage()
    
    config = get_base_config()
    
    try:
        graph = SmartScraperMultiGraph(
            prompt=prompt,
            source=urls,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "SmartScraperMultiGraph"
        }
    except Exception as e:
        return {"error": str(e)}


def run_script_creator_multi(urls: List[str], prompt: str) -> Dict[str, Any]:
    """Run ScriptCreatorMultiGraph for multi-page Python script generation"""
    clear_token_usage()
    
    config = get_base_config()
    config["library"] = "requests"
    
    try:
        graph = ScriptCreatorMultiGraph(
            prompt=prompt,
            source=urls,
            config=config
        )
        result = graph.run()
        
        token_usage = get_token_usage()
        
        return {
            "result": result,
            "token_usage": token_usage,
            "graph_type": "ScriptCreatorMultiGraph"
        }
    except Exception as e:
        return {"error": str(e)}


# Async wrappers for FastAPI
async def run_graph_async(func, *args, **kwargs):
    """Run a graph function in a thread pool to avoid blocking"""
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, func, *args, **kwargs)
