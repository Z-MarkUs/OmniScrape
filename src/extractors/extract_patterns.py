import re

PRICE_RE = re.compile(r"(?<!\w)(?:USD|EUR|GBP|\$|€|£)\s?\d[\d,]*(?:\.\d{2})?(?!\w)")
PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{6,}\d")

def find_prices(text: str): return PRICE_RE.findall(text or "")
def find_phones(text: str): return PHONE_RE.findall(text or "")
