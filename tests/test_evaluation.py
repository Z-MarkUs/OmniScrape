"""Regression tests for the original offline extraction-quality corpus."""

from __future__ import annotations

import copy
import io
import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from evaluation import run as evaluation


def _latest() -> dict[str, Any]:
    return json.loads(evaluation.DEFAULT_SCORECARD.read_text(encoding="utf-8"))


def test_manifest_is_balanced_original_synthetic_corpus() -> None:
    manifest = evaluation.load_manifest()

    assert len(manifest.cases) == 14
    assert sum(case.kind.value == "article" for case in manifest.cases) == 7
    assert sum(case.kind.value == "product" for case in manifest.cases) == 7
    assert manifest.corpus.license == "MIT"
    assert "no third-party" in manifest.corpus.source_policy

    tags = {tag for case in manifest.cases for tag in case.tags}
    assert {
        "json-ld",
        "microdata",
        "opengraph",
        "malformed-json-ld",
        "conflicting-metadata",
        "missing-optional-fields",
        "multilingual",
        "unicode",
    } <= tags


def test_evaluation_recomputes_frozen_baseline_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("offline evaluator attempted network access")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    monkeypatch.setattr(socket, "socket", unexpected_network)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    payload = evaluation.evaluate()
    baseline = evaluation.load_thresholds().observed_baseline

    assert payload["execution_policy"] == {
        "mode": "deterministic",
        "network": "disabled-by-design",
        "browser": "not-used",
        "provider_or_llm": "not-used",
    }
    aggregate = payload["metrics"]["aggregate"]
    assert aggregate["present_field_exact_match"]["denominator"] == 76
    assert aggregate["present_field_exact_match"]["rate"] == (baseline.present_field_exact_match)
    assert aggregate["expected_field_completeness"]["denominator"] == 76
    assert aggregate["expected_field_completeness"]["rate"] == (
        baseline.expected_field_completeness
    )
    assert aggregate["expected_absence_accuracy"]["denominator"] == 8
    assert aggregate["expected_absence_accuracy"]["rate"] == (baseline.expected_absence_accuracy)
    assert payload["metrics"]["case_pass_rate"]["denominator"] == 14
    assert payload["metrics"]["case_pass_rate"]["rate"] == baseline.case_pass_rate
    assert payload["metrics"]["extraction_errors"] == baseline.extraction_errors
    assert payload["gate_passed"] is True


def test_checked_in_scorecard_matches_environment_independent_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1788220800")
    actual = evaluation.evaluate()
    checked_in = _latest()
    stable_keys = (
        "schema_version",
        "generated_at",
        "tool",
        "evaluator_version",
        "omniscrape_version",
        "execution_policy",
        "population",
        "metric_definitions",
        "metrics",
        "threshold_policy",
        "threshold_checks",
        "gate_passed",
        "cases",
        "failures",
        "limitations",
    )

    assert {key: actual[key] for key in stable_keys} == {
        key: checked_in[key] for key in stable_keys
    }


def test_readme_quality_claims_match_the_checked_in_scorecard() -> None:
    scorecard = _latest()
    aggregate = scorecard["metrics"]["aggregate"]
    cases = scorecard["metrics"]["case_pass_rate"]
    readme = (evaluation.ROOT / "README.md").read_text(encoding="utf-8")

    present = aggregate["present_field_exact_match"]
    absent = aggregate["expected_absence_accuracy"]
    expected_claims = (
        f"{present['numerator']}/{present['denominator']} exact gold-present fields",
        f"{absent['numerator']}/{absent['denominator']} correct expected-absent slots",
        f"{cases['numerator']}/{cases['denominator']} all-fields-exact cases",
    )

    for claim in expected_claims:
        assert claim in readme


@pytest.mark.parametrize(
    "metric",
    (
        "present_field_exact_match",
        "expected_field_completeness",
        "expected_absence_accuracy",
        "case_pass_rate",
        "extraction_errors",
    ),
)
def test_each_threshold_gate_detects_its_own_regression(metric: str) -> None:
    payload = evaluation.evaluate()
    degraded = copy.deepcopy(payload["metrics"])
    if metric == "extraction_errors":
        degraded[metric] += 1
    else:
        target = degraded[metric] if metric == "case_pass_rate" else degraded["aggregate"][metric]
        target["numerator"] -= 1
        target["rate"] = round(target["numerator"] / target["denominator"], 6)

    passed, checks = evaluation._apply_thresholds(degraded, evaluation.load_thresholds())

    assert passed is False
    failed = [check for check in checks if not check["passed"]]
    assert [check["metric"] for check in failed] == [metric]


def test_normalization_and_null_semantics_are_explicit() -> None:
    assert evaluation._normalize_value("  Café\t\uff21  ") == "Café A"
    assert evaluation._normalize_value([" one ", "\uff34\uff57\uff4f"]) == ["one", "Two"]
    assert evaluation._is_present(None) is False
    assert evaluation._is_present([]) is False
    assert evaluation._is_present("  ") is False
    assert evaluation._is_present("0") is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", " \t\n"),
        ("images", ["\u3000"]),
    ],
)
def test_manifest_rejects_normalized_blank_gold_labels(field: str, value: Any) -> None:
    raw = json.loads(evaluation.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    raw["cases"][0]["expected"][field] = value

    with pytest.raises(ValueError, match="normalized-blank"):
        evaluation.GoldManifest.model_validate(raw)


def test_stdout_scorecard_is_safe_for_legacy_windows_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)

    assert evaluation.main(["--without-thresholds"]) == 0
    stream.flush()
    payload = json.loads(buffer.getvalue().decode("cp1252"))
    assert payload["population"]["case_count"] == 14


def test_ci_command_writes_machine_readable_scorecard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1788220800")
    output = tmp_path / "scorecard.json"

    assert evaluation.main(["--check", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["gate_passed"] is True
    assert payload["population"]["case_count"] == 14
