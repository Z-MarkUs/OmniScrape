#!/usr/bin/env python3
import asyncio
import logging
import os
from urllib.parse import urlparse
from datetime import datetime

# .env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Generic async crawler
from crawler import Crawler

# HKEX / generic newspaper3k-based (sync)
from newspaper_scraper import Meta_Newspaper3k, Config


# Determine export directory (this script's folder)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _export_full_results(prefix: str, articles):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_results_{timestamp}.txt"
    out_path = os.path.join(_SCRIPT_DIR, filename)
    matched_count = sum(1 for a in articles if a.get('matched'))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=" * 100 + "\n")
        f.write(f"{prefix.upper()} SEMANTIC EXTRACTION RESULTS\n")
        f.write("=" * 100 + "\n")
        f.write(f"Articles Total: {len(articles)}\n")
        f.write(f"Articles Matched: {matched_count}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write("=" * 100 + "\n\n")
        for i, a in enumerate(articles, 1):
            f.write(f"Article {i}:\n")
            f.write(f"Title: {a.get('title','')}\n")
            f.write(f"URL: {a.get('url','')}\n")
            f.write(f"Match: {bool(a.get('matched'))}\n")
            if a.get('matched_keywords'):
                f.write(f"Keywords: {a.get('matched_keywords')}\n")
            if a.get('similarity') is not None:
                try:
                    f.write(f"Similarity: {float(a.get('similarity')):.6f}\n")
                except Exception:
                    f.write(f"Similarity: {a.get('similarity')}\n")
            content = a.get('content') or a.get('text') or a.get('preview') or ''
            display = content if len(content) <= 4000 else (content[:4000] + "...")
            f.write(f"Content Length: {len(content)} characters\n")
            f.write("Content:\n")
            f.write(display + "\n")
            f.write("-" * 100 + "\n\n")
    return out_path


async def run_pipeline(url: str | None):
    logging.basicConfig(level=logging.INFO)

    if not url:
        url = os.getenv("CRAWL_URL")
    if not url:
        raise SystemExit("No URL provided. Set CRAWL_URL in .env or pass as argv.")

    try:
        max_articles = int(os.getenv("MAX_ARTICLES", "50"))
    except Exception:
        max_articles = 50

    host = (urlparse(url).hostname or "").lower()

    # For ETNet or any list page, use the generic async crawler path
    if "etnetchina.cn" in host:
        crawler = Crawler()
        articles = await crawler.discover_articles(url, max_articles=max_articles)
        enriched = []
        if articles:
            for idx, art in enumerate(articles):
                content = await crawler.fetch_article_content(art.get('url', ''))
                art['content'] = content or ''
                art['preview'] = (art['content'][:200] + "...") if len(art['content']) > 200 else art['content']
                match = crawler.hybrid_keyword_matching(art.get('title',''), art['content'] or art['preview'] or '', crawler.target_keywords)
                sem = crawler.semantic_keyword_matching(art.get('title',''), art['content'] or art['preview'] or '', crawler.target_keywords)
                art['similarity'] = sem[1] if sem else 0.0
                if match:
                    art['matched'] = True
                    art['matched_keywords'] = match['keyword']
                else:
                    art['matched'] = False
                logging.info(f"[ETNET] sim={art['similarity']:.6f} matched={art['matched']} title='{art.get('title','')[:42]}'")
                enriched.append(art)
        exported = _export_full_results("etnet_pipeline", enriched)
        print(f"Exported to: {exported}")
        return

    # HKEX / others: use newspaper3k workflow
    config = Config()
    scraper = Meta_Newspaper3k(config)
    print("Discovering articles (newspaper3k)...")
    articles = scraper.discover_articles(url, max_articles=max_articles)

    enriched = []
    if articles:
        cfg = scraper.config.lark_config_list[0] if scraper.config.lark_config_list else {}
        positive_key = getattr(scraper.config, 'config_head_positive_words', 'config_head_positive_words')
        groups = cfg.get(positive_key, ["香港+財經", "中國+財經", "國際+財經"])  # sensible defaults

        scorer = Crawler()
        for idx, art in enumerate(articles):
            preview = scraper.fetch_article_preview(art.get('url', ''))
            content = scraper.fetch_article_content(art.get('url', ''))
            art['preview'] = preview or ''
            art['content'] = content or ''
            regex_match = scraper.hybrid_keyword_matching(art.get('title',''), art['content'] or art['preview'] or '', groups)
            sem = scorer.semantic_keyword_matching(art.get('title',''), art['content'] or art['preview'] or '', scorer.target_keywords)
            if regex_match or (sem and sem[1] >= scorer.semantic_threshold):
                art['matched'] = True
                if isinstance(regex_match, str):
                    art['matched_keywords'] = regex_match
                elif sem:
                    art['matched_keywords'] = sem[0]
            else:
                art['matched'] = False
            art['similarity'] = sem[1] if sem else 0.0
            logging.info(f"[HKEX] sim={art['similarity']:.6f} matched={art['matched']} title='{art.get('title','')[:42]}'")
            enriched.append(art)
    exported = _export_full_results("hkex_pipeline", enriched)
    print(f"Exported to: {exported}")


if __name__ == "__main__":
    import sys
    argv_url = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_pipeline(argv_url))
