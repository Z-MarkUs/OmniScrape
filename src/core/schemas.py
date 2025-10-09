from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List

class Article(BaseModel):
    url: HttpUrl
    title: Optional[str] = None
    author: Optional[str] = None
    date_published: Optional[str] = Field(None, description="ISO-8601 preferred")
    text: Optional[str] = None
    images: List[str] = []

class Product(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    price: Optional[str] = None   # keep raw; normalize later to Money
    currency: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []
