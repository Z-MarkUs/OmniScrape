import os
from scrapegraphai.graphs import SmartScraperGraph

def scrapegraph_article(url: str):
    model = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini")
    graph = SmartScraperGraph(
        prompt="Extract the main article title, author, publication date, text, and image URLs.",
        source=url,
        include_links=True,
        engine=model,
        # You can pass schema via "output_schema" to enforce structure
        # output_schema={"title": "str", "author": "str", "date_published": "str", "text": "str", "images": ["str"]}
    )
    return graph.run()

def scrapegraph_product(url: str):
    model = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini")
    graph = SmartScraperGraph(
        prompt="Extract product name, price with currency, sku if any, description, and image URLs.",
        source=url,
        include_links=True,
        engine=model,
    )
    return graph.run()
