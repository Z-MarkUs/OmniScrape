import extruct, w3lib.html
from bs4 import BeautifulSoup

def extract_structured(html: str, base_url: str):
    data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld","microdata","opengraph","rdfa"])
    # Prefer JSON-LD product/article blocks
    ld = data.get("json-ld", []) + data.get("microdata", [])
    og = data.get("opengraph", [])
    return {"ld": ld, "og": og}

def extract_rss_links(html: str):
    soup = BeautifulSoup(html, "lxml")
    return [link.get("href") for link in soup.select('link[type="application/rss+xml"], link[type="application/atom+xml"]')]
