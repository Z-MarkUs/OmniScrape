#!/usr/bin/env python3
"""
OmniScrape API Server

A multi-layered web scraping service that can extract articles and products
from any website using structured data, readability, and LLM fallbacks.

Usage:
    python main.py                    # Start server on localhost:8000
    python main.py --host 0.0.0.0    # Start server on all interfaces
    python main.py --port 8080       # Start server on port 8080
"""

import os
from dotenv import load_dotenv
import uvicorn
from src.api.api import app

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "src.api.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
