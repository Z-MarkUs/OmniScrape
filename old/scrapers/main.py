#!/usr/bin/env python3
import asyncio
import os
import sys

# Load .env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from semantic_stream_pipeline import run_pipeline


def main():
    # Allow optional CLI override: python main.py <url>
    url = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_pipeline(url))


if __name__ == "__main__":
    main()
