"""Reproducible, fixture-backed deterministic extraction microbenchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omniscrape import __version__
from omniscrape.extractors import ExtractionCandidate, extract_structured
from omniscrape.models import ContentKind

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DIRECT_DEPENDENCIES = (
    "beautifulsoup4",
    "fastapi",
    "httpx",
    "lxml",
    "pydantic",
    "readability-lxml",
    "typer",
    "uvicorn",
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _digest(candidate: ExtractionCandidate | None) -> str:
    if candidate is None:
        raise RuntimeError("benchmark extraction unexpectedly returned no candidate")
    payload = json.dumps(candidate.values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in DIRECT_DEPENDENCIES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _measure(
    name: str,
    operation: Callable[[], ExtractionCandidate | None],
    *,
    iterations: int,
    warmup: int,
) -> dict[str, Any]:
    expected = _digest(operation())
    for _ in range(warmup):
        if _digest(operation()) != expected:
            raise RuntimeError(f"{name} produced non-deterministic output during warm-up")

    samples_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        actual = _digest(operation())
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        if actual != expected:
            raise RuntimeError(f"{name} produced non-deterministic output")
        samples_ms.append(elapsed_ms)

    total_seconds = sum(samples_ms) / 1_000
    return {
        "name": name,
        "iterations": iterations,
        "warmup_iterations": warmup,
        "result_digest": expected,
        "median_ms": round(statistics.median(samples_ms), 6),
        "p95_ms": round(_percentile(samples_ms, 0.95), 6),
        "min_ms": round(min(samples_ms), 6),
        "max_ms": round(max(samples_ms), 6),
        "throughput_ops_per_second": round(iterations / total_seconds, 3),
    }


def run(iterations: int, warmup: int) -> dict[str, Any]:
    article_html = (FIXTURES / "article.html").read_text(encoding="utf-8")
    product_html = (FIXTURES / "product.html").read_text(encoding="utf-8")
    cases: list[tuple[str, Callable[[], ExtractionCandidate | None]]] = [
        (
            "structured_article",
            lambda: extract_structured(
                article_html,
                "https://news.example.test/stories/solar-workshop",
                ContentKind.ARTICLE,
            ),
        ),
        (
            "structured_product",
            lambda: extract_structured(
                product_html,
                "https://shop.example.test/products/field-notes-lamp",
                ContentKind.PRODUCT,
            ),
        ),
    ]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "omniscrape-offline-benchmark",
        "omniscrape_version": __version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.system(),
        "fixture_policy": "synthetic-offline",
        "fixture_sha256": {
            "article.html": _file_digest(FIXTURES / "article.html"),
            "product.html": _file_digest(FIXTURES / "product.html"),
        },
        "dependency_versions": _dependency_versions(),
        "cases": [
            _measure(name, operation, iterations=iterations, warmup=warmup)
            for name, operation in cases
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=_positive_int, default=100)
    parser.add_argument("--warmup", type=_positive_int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    payload = run(args.iterations, args.warmup)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
