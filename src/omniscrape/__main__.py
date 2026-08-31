"""Allow ``python -m omniscrape`` to behave like the console script."""

from .cli import app

if __name__ == "__main__":
    app()
