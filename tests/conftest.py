"""Shared, offline-only test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURES


@pytest.fixture
def article_html(fixture_dir: Path) -> str:
    return (fixture_dir / "article.html").read_text(encoding="utf-8")


@pytest.fixture
def product_html(fixture_dir: Path) -> str:
    return (fixture_dir / "product.html").read_text(encoding="utf-8")


@pytest.fixture
def redirect_target_html(fixture_dir: Path) -> str:
    return (fixture_dir / "redirect-target.html").read_text(encoding="utf-8")


@pytest.fixture
def hostile_html(fixture_dir: Path) -> str:
    return (fixture_dir / "security.html").read_text(encoding="utf-8")
