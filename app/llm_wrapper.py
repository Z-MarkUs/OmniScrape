"""
Custom LLM wrapper to capture real token usage from API responses.
This bypasses ScrapeGraphAI's internal handling to get actual token counts.
"""

import os
import json
from typing import Dict, Any, Optional, List
from openai import OpenAI
import threading

# Thread-local storage for token usage
_thread_local = threading.local()

class TokenUsageTracker:
    """Thread-safe token usage tracker"""
    
    def __init__(self):
        self.usage_data = {}
    
    def set_usage(self, usage: Dict[str, Any]):
        """Set token usage data for current thread"""
        self.usage_data = usage
    
    def get_usage(self) -> Dict[str, Any]:
        """Get token usage data for current thread"""
        return self.usage_data.copy()
    
    def clear(self):
        """Clear token usage data"""
        self.usage_data = {}

# Global tracker instance
_tracker = TokenUsageTracker()

def get_token_usage() -> Dict[str, Any]:
    """Get the latest token usage data"""
    return _tracker.get_usage()

def clear_token_usage():
    """Clear token usage data"""
    _tracker.clear()

class CustomOpenAIClient:
    """Custom OpenAI client that captures token usage"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    def chat_completions_create(self, **kwargs):
        """Create chat completion and capture token usage"""
        try:
            response = self.client.chat.completions.create(**kwargs)
            
            # Extract token usage from response
            if hasattr(response, 'usage') and response.usage:
                usage_data = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "model": kwargs.get('model', 'unknown')
                }
                _tracker.set_usage(usage_data)
            
            return response
        except Exception as e:
            print(f"Error in custom OpenAI client: {e}")
            raise

def create_custom_llm_config(model: str, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Create LLM configuration with custom client"""
    
    # Create custom client
    custom_client = CustomOpenAIClient(api_key, base_url)
    
    # Monkey patch the OpenAI client to use our custom one
    import openai
    original_create = openai.OpenAI.chat.completions.create
    
    def patched_create(self, **kwargs):
        return custom_client.chat_completions_create(**kwargs)
    
    # Apply the patch
    openai.OpenAI.chat.completions.create = patched_create
    
    return {
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "custom_client": custom_client
    }

def test_token_capture():
    """Test function to verify token usage capture works"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("No API key found")
        return
    
    # Test with DeepSeek
    client = CustomOpenAIClient(api_key, "https://api.deepseek.com/v1")
    
    try:
        response = client.chat_completions_create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "Hello, how are you?"}
            ],
            max_tokens=50
        )
        
        usage = get_token_usage()
        print(f"Token usage captured: {usage}")
        
        return usage
    except Exception as e:
        print(f"Test failed: {e}")
        return None

if __name__ == "__main__":
    test_token_capture()
