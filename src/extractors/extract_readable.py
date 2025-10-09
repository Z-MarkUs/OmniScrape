from readability import Document
from bs4 import BeautifulSoup

def readable_article(html: str):
    doc = Document(html)
    title = doc.short_title()
    content_html = doc.summary()
    text = BeautifulSoup(content_html, "lxml").get_text("\n", strip=True)
    return {"title": title, "text": text}
