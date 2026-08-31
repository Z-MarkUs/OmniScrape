"""The benchmark runner is executable and emits its documented schema."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from omniscrape import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_benchmark_matches_current_package_version() -> None:
    payload = json.loads(
        (ROOT / "benchmarks" / "results" / "latest.json").read_text(encoding="utf-8")
    )

    assert payload["omniscrape_version"] == __version__


def test_benchmark_runner_writes_machine_readable_results(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    subprocess.run(
        [
            sys.executable,
            "benchmarks/run.py",
            "--iterations",
            "3",
            "--warmup",
            "1",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["fixture_policy"] == "synthetic-offline"
    assert set(payload["fixture_sha256"]) == {"article.html", "product.html"}
    assert all(len(digest) == 64 for digest in payload["fixture_sha256"].values())
    assert payload["dependency_versions"]["beautifulsoup4"]
    assert [case["name"] for case in payload["cases"]] == [
        "structured_article",
        "structured_product",
    ]
    assert all(case["iterations"] == 3 for case in payload["cases"])
    assert all(case["median_ms"] > 0 for case in payload["cases"])
