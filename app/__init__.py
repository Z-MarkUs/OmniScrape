"""
OmniScrape API

A multi-layered web scraping service that can extract articles and products
from any website using structured data, readability, and LLM fallbacks.
"""

# Load environment variables from a .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; ignore if not installed
    pass

__version__ = "0.1.0"
