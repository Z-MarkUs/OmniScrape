"""Run OmniScrape's deterministic extraction-quality evaluation offline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from omniscrape import __version__
from omniscrape.models import ContentKind
from omniscrape.pipeline import _extract_local

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "evaluation"
DEFAULT_MANIFEST = EVALUATION_DIR / "gold.json"
DEFAULT_THRESHOLDS = EVALUATION_DIR / "thresholds.json"
DEFAULT_SCORECARD = EVALUATION_DIR / "results" / "latest.json"
FIXTURE_DIR = EVALUATION_DIR / "fixtures"
EVALUATOR_VERSION = "1.0.0"

ARTICLE_FIELDS = ("title", "author", "date_published", "text", "description", "images")
PRODUCT_FIELDS = ("name", "price", "currency", "sku", "description", "images")
DIRECT_DEPENDENCIES = (
    "beautifulsoup4",
    "lxml",
    "pydantic",
    "readability-lxml",
)

FieldValue = str | list[str] | None


class CorpusMetadata(BaseModel):
    """Redistribution and scope metadata stored with the gold labels."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    license: Literal["MIT"]
    source_policy: str = Field(min_length=1)


class EvaluationCase(BaseModel):
    """One fixture, extraction request, and explicit gold field set."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    fixture: str = Field(pattern=r"^[a-z0-9-]+\.html$")
    url: str = Field(pattern=r"^https://")
    kind: ContentKind
    tags: list[str] = Field(min_length=1)
    expected: dict[str, FieldValue]

    @model_validator(mode="after")
    def expected_fields_match_kind(self) -> EvaluationCase:
        required = set(ARTICLE_FIELDS if self.kind is ContentKind.ARTICLE else PRODUCT_FIELDS)
        actual = set(self.expected)
        if actual != required:
            missing = sorted(required - actual)
            extra = sorted(actual - required)
            raise ValueError(f"expected fields differ: missing={missing}, extra={extra}")
        for field, value in self.expected.items():
            if field == "images":
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise ValueError("images must be an explicit list of strings")
                if any(not _normalize_scalar(item) for item in value):
                    raise ValueError("images must not contain normalized-blank labels")
            elif value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be a string or null")
            elif isinstance(value, str) and not _normalize_scalar(value):
                raise ValueError(f"{field} must not be a normalized-blank label")
        return self


class GoldManifest(BaseModel):
    """Versioned evaluation corpus manifest."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    corpus: CorpusMetadata
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_and_fixtures_are_unique(self) -> GoldManifest:
        ids = [case.id for case in self.cases]
        fixtures = [case.fixture for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case ids must be unique")
        if len(fixtures) != len(set(fixtures)):
            raise ValueError("fixture paths must be unique")
        return self


class ThresholdBaseline(BaseModel):
    """Observed baseline retained beside its regression floors."""

    model_config = ConfigDict(extra="forbid")

    present_field_exact_match: float = Field(ge=0.0, le=1.0)
    expected_field_completeness: float = Field(ge=0.0, le=1.0)
    expected_absence_accuracy: float = Field(ge=0.0, le=1.0)
    case_pass_rate: float = Field(ge=0.0, le=1.0)
    extraction_errors: int = Field(ge=0)


class MinimumThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present_field_exact_match: float = Field(ge=0.0, le=1.0)
    expected_field_completeness: float = Field(ge=0.0, le=1.0)
    expected_absence_accuracy: float = Field(ge=0.0, le=1.0)
    case_pass_rate: float = Field(ge=0.0, le=1.0)


class MaximumThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction_errors: int = Field(ge=0)


class ThresholdPolicy(BaseModel):
    """Auditable regression policy derived from an observed scorecard."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    rationale: str = Field(min_length=1)
    observed_baseline: ThresholdBaseline
    minimums: MinimumThresholds
    maximums: MaximumThresholds

    @model_validator(mode="after")
    def thresholds_do_not_exceed_observed_baseline(self) -> ThresholdPolicy:
        for name in (
            "present_field_exact_match",
            "expected_field_completeness",
            "expected_absence_accuracy",
            "case_pass_rate",
        ):
            if getattr(self.minimums, name) > getattr(self.observed_baseline, name):
                raise ValueError(f"minimum {name} exceeds the recorded baseline")
        if self.maximums.extraction_errors < self.observed_baseline.extraction_errors:
            raise ValueError("maximum extraction errors is below the recorded baseline")
        return self


@dataclass(slots=True)
class MetricAccumulator:
    """Count numerators and denominators before computing any rates."""

    field_slots: int = 0
    exact_matches: int = 0
    expected_present: int = 0
    present_predictions: int = 0
    correct_present: int = 0
    expected_absent: int = 0
    correct_absent: int = 0
    unexpected_values: int = 0

    def add(
        self,
        *,
        exact: bool,
        expected_present: bool,
        actual_present: bool,
        extraction_succeeded: bool,
    ) -> None:
        self.field_slots += 1
        self.exact_matches += int(exact)
        if expected_present:
            self.expected_present += 1
            self.present_predictions += int(actual_present and extraction_succeeded)
            self.correct_present += int(exact)
        else:
            self.expected_absent += 1
            correctly_absent = extraction_succeeded and not actual_present
            self.correct_absent += int(correctly_absent)
            self.unexpected_values += int(extraction_succeeded and actual_present)

    def payload(self) -> dict[str, Any]:
        return {
            "all_field_exact_match": _metric(self.exact_matches, self.field_slots),
            "present_field_exact_match": _metric(self.correct_present, self.expected_present),
            "expected_field_completeness": _metric(self.present_predictions, self.expected_present),
            "expected_absence_accuracy": _metric(self.correct_absent, self.expected_absent),
            "unexpected_value_count": self.unexpected_values,
        }


def _metric(numerator: int, denominator: int) -> dict[str, int | float | None]:
    rate = None if denominator == 0 else round(numerator / denominator, 6)
    return {"numerator": numerator, "denominator": denominator, "rate": rate}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generated_at() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        try:
            timestamp = int(source_date_epoch)
        except ValueError as exc:
            raise ValueError("SOURCE_DATE_EPOCH must be an integer Unix timestamp") from exc
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in DIRECT_DEPENDENCIES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _normalize_scalar(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _normalize_value(value: FieldValue) -> FieldValue:
    if value is None:
        return None
    if isinstance(value, list):
        return [_normalize_scalar(item) for item in value]
    normalized = _normalize_scalar(value)
    return normalized or None


def _is_present(value: FieldValue) -> bool:
    normalized = _normalize_value(value)
    if isinstance(normalized, list):
        return bool(normalized)
    return normalized is not None


def _prediction_value(value: object, *, field: str) -> FieldValue:
    if field == "images":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise TypeError("predicted images must be a list of strings")
        return list(value)
    if value is None or isinstance(value, str):
        return value
    raise TypeError(f"predicted {field} must be a string or null")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> GoldManifest:
    """Load and validate gold labels plus every referenced fixture path."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = GoldManifest.model_validate(raw)
    except (json.JSONDecodeError, OSError, ValidationError) as exc:
        raise ValueError(f"invalid evaluation manifest {path}: {exc}") from exc

    fixture_root = FIXTURE_DIR.resolve()
    for case in manifest.cases:
        fixture_path = (FIXTURE_DIR / case.fixture).resolve()
        if fixture_path.parent != fixture_root or not fixture_path.is_file():
            raise ValueError(f"case {case.id} references an invalid fixture path")
    return manifest


def load_thresholds(path: Path = DEFAULT_THRESHOLDS) -> ThresholdPolicy:
    """Load and validate the observed-baseline regression policy."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ThresholdPolicy.model_validate(raw)
    except (json.JSONDecodeError, OSError, ValidationError) as exc:
        raise ValueError(f"invalid evaluation thresholds {path}: {exc}") from exc


def _run_case(case: EvaluationCase) -> dict[str, Any]:
    fixture_path = FIXTURE_DIR / case.fixture
    fixture_html = fixture_path.read_text(encoding="utf-8")
    fields = ARTICLE_FIELDS if case.kind is ContentKind.ARTICLE else PRODUCT_FIELDS
    extraction_error: str | None = None
    sources: list[str] = []
    warnings: list[str] = []
    prediction: dict[str, FieldValue] = {}

    try:
        data, candidates, warnings = _extract_local(fixture_html, case.url, case.kind)
        sources = [candidate.source for candidate in candidates]
        dumped = data.model_dump(mode="json")
        prediction = {field: _prediction_value(dumped.get(field), field=field) for field in fields}
    except Exception as exc:  # evaluator records a product failure instead of aborting the corpus
        extraction_error = f"{type(exc).__name__}: {exc}"

    succeeded = extraction_error is None
    accumulator = MetricAccumulator()
    failures: list[dict[str, Any]] = []
    for field in fields:
        expected = case.expected[field]
        actual = prediction.get(field)
        expected_present = _is_present(expected)
        actual_present = _is_present(actual) if succeeded else False
        exact = succeeded and _normalize_value(actual) == _normalize_value(expected)
        accumulator.add(
            exact=exact,
            expected_present=expected_present,
            actual_present=actual_present,
            extraction_succeeded=succeeded,
        )
        if not exact:
            if extraction_error is not None:
                reason = "extraction_error"
            elif expected_present and not actual_present:
                reason = "missing"
            elif not expected_present and actual_present:
                reason = "unexpected"
            else:
                reason = "mismatch"
            failures.append(
                {
                    "field": field,
                    "reason": reason,
                    "expected": expected,
                    "actual": actual,
                }
            )

    return {
        "id": case.id,
        "kind": case.kind.value,
        "fixture": case.fixture,
        "fixture_sha256": _sha256(fixture_path),
        "tags": case.tags,
        "passed": succeeded and not failures,
        "extraction_error": extraction_error,
        "sources": sources,
        "warnings": warnings,
        "metrics": accumulator.payload(),
        "prediction": prediction if succeeded else None,
        "failures": failures,
    }


def _accumulate_case(
    accumulator: MetricAccumulator,
    *,
    case: EvaluationCase,
    result: dict[str, Any],
) -> None:
    fields = ARTICLE_FIELDS if case.kind is ContentKind.ARTICLE else PRODUCT_FIELDS
    succeeded = result["extraction_error"] is None
    raw_prediction = result["prediction"]
    prediction = raw_prediction if isinstance(raw_prediction, dict) else {}
    for field in fields:
        expected = case.expected[field]
        actual = prediction.get(field)
        actual_value = _prediction_value(actual, field=field) if succeeded else None
        expected_present = _is_present(expected)
        actual_present = _is_present(actual_value) if succeeded else False
        exact = succeeded and _normalize_value(actual_value) == _normalize_value(expected)
        accumulator.add(
            exact=exact,
            expected_present=expected_present,
            actual_present=actual_present,
            extraction_succeeded=succeeded,
        )


def _rate(payload: dict[str, Any], metric: str) -> float:
    value = payload[metric]["rate"]
    if not isinstance(value, (int, float)):
        raise ValueError(f"metric {metric} has no denominator")
    return float(value)


def _apply_thresholds(
    metrics: dict[str, Any], policy: ThresholdPolicy
) -> tuple[bool, list[dict[str, Any]]]:
    aggregate = metrics["aggregate"]
    actuals = {
        "present_field_exact_match": _rate(aggregate, "present_field_exact_match"),
        "expected_field_completeness": _rate(aggregate, "expected_field_completeness"),
        "expected_absence_accuracy": _rate(aggregate, "expected_absence_accuracy"),
        "case_pass_rate": _rate(metrics, "case_pass_rate"),
        "extraction_errors": int(metrics["extraction_errors"]),
    }
    checks: list[dict[str, Any]] = []
    for name in (
        "present_field_exact_match",
        "expected_field_completeness",
        "expected_absence_accuracy",
        "case_pass_rate",
    ):
        minimum = float(getattr(policy.minimums, name))
        actual = float(actuals[name])
        checks.append(
            {
                "metric": name,
                "operator": ">=",
                "threshold": minimum,
                "actual": actual,
                "passed": actual >= minimum,
            }
        )
    maximum = policy.maximums.extraction_errors
    errors = int(actuals["extraction_errors"])
    checks.append(
        {
            "metric": "extraction_errors",
            "operator": "<=",
            "threshold": maximum,
            "actual": errors,
            "passed": errors <= maximum,
        }
    )
    return all(bool(check["passed"]) for check in checks), checks


def evaluate(
    manifest_path: Path = DEFAULT_MANIFEST,
    thresholds_path: Path | None = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Evaluate every manifest case and return a machine-readable scorecard."""

    manifest = load_manifest(manifest_path)
    results = [_run_case(case) for case in manifest.cases]
    by_id = {result["id"]: result for result in results}
    aggregate = MetricAccumulator()
    by_kind = {kind.value: MetricAccumulator() for kind in ContentKind}
    by_field: dict[str, MetricAccumulator] = {}
    for case in manifest.cases:
        result = by_id[case.id]
        _accumulate_case(aggregate, case=case, result=result)
        _accumulate_case(by_kind[case.kind.value], case=case, result=result)
        fields = ARTICLE_FIELDS if case.kind is ContentKind.ARTICLE else PRODUCT_FIELDS
        for field in fields:
            key = f"{case.kind.value}.{field}"
            field_accumulator = by_field.setdefault(key, MetricAccumulator())
            succeeded = result["extraction_error"] is None
            prediction = result["prediction"] if isinstance(result["prediction"], dict) else {}
            expected = case.expected[field]
            raw_actual = prediction.get(field)
            actual = _prediction_value(raw_actual, field=field) if succeeded else None
            expected_present = _is_present(expected)
            actual_present = _is_present(actual) if succeeded else False
            exact = succeeded and _normalize_value(actual) == _normalize_value(expected)
            field_accumulator.add(
                exact=exact,
                expected_present=expected_present,
                actual_present=actual_present,
                extraction_succeeded=succeeded,
            )

    passed_cases = sum(bool(result["passed"]) for result in results)
    extraction_errors = sum(result["extraction_error"] is not None for result in results)
    metrics: dict[str, Any] = {
        "aggregate": aggregate.payload(),
        "case_pass_rate": _metric(passed_cases, len(results)),
        "passed_cases": passed_cases,
        "failed_cases": len(results) - passed_cases,
        "extraction_errors": extraction_errors,
        "by_kind": {name: value.payload() for name, value in sorted(by_kind.items())},
        "by_field": {name: value.payload() for name, value in sorted(by_field.items())},
    }

    policy_payload: dict[str, Any] | None = None
    checks: list[dict[str, Any]] = []
    gate_passed: bool | None = None
    if thresholds_path is not None:
        policy = load_thresholds(thresholds_path)
        gate_passed, checks = _apply_thresholds(metrics, policy)
        policy_payload = policy.model_dump(mode="json")

    fixture_digests = {case.fixture: by_id[case.id]["fixture_sha256"] for case in manifest.cases}
    kind_counts = Counter(case.kind.value for case in manifest.cases)
    failures = [
        {
            "id": result["id"],
            "kind": result["kind"],
            "extraction_error": result["extraction_error"],
            "fields": result["failures"],
        }
        for result in results
        if result["failures"]
    ]

    return {
        "schema_version": 1,
        "generated_at": _generated_at(),
        "tool": "omniscrape-offline-quality-evaluator",
        "evaluator_version": EVALUATOR_VERSION,
        "omniscrape_version": __version__,
        "execution_policy": {
            "mode": "deterministic",
            "network": "disabled-by-design",
            "browser": "not-used",
            "provider_or_llm": "not-used",
        },
        "population": {
            "corpus": manifest.corpus.model_dump(mode="json"),
            "case_count": len(manifest.cases),
            "kind_counts": dict(sorted(kind_counts.items())),
            "field_slots_per_case": 6,
            "total_field_slots": len(manifest.cases) * 6,
            "case_ids": [case.id for case in manifest.cases],
            "manifest_sha256": _sha256(manifest_path),
            "fixture_sha256": fixture_digests,
        },
        "metric_definitions": {
            "normalization": (
                "Unicode NFKC, then collapse all whitespace runs to one ASCII space; "
                "comparison remains case-sensitive. Image lists are ordered and compared exactly."
            ),
            "present_field_exact_match": (
                "Gold-present fields whose normalized prediction exactly equals gold, divided by "
                "all gold-present fields. Expected-absent slots are excluded."
            ),
            "expected_field_completeness": (
                "Gold-present fields with any non-null prediction, divided by all gold-present "
                "fields. Wrong non-null values count as present but not correct."
            ),
            "expected_absence_accuracy": (
                "Expected-absent slots that remain null (or empty image lists), divided by all "
                "expected-absent slots. Extraction errors never receive credit for absence."
            ),
            "all_field_exact_match": (
                "All exact field matches divided by all six field slots per case, including "
                "expected-absent slots. Reported as a secondary metric only."
            ),
            "case_pass_rate": " ".join(
                (
                    "Cases with successful extraction and all six fields exactly matching gold,",
                    "divided by all manifest cases.",
                )
            ),
        },
        "metrics": metrics,
        "threshold_policy": policy_payload,
        "threshold_checks": checks,
        "gate_passed": gate_passed,
        "cases": results,
        "failures": failures,
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "operating_system": platform.system(),
            "machine": platform.machine(),
            "dependency_versions": _dependency_versions(),
        },
        "limitations": [
            (
                "The corpus is small, balanced, original, and synthetic; it is not a "
                "representative sample of the open web."
            ),
            (
                "Scores describe only this checked-in corpus and must not be presented as "
                "real-world extraction accuracy."
            ),
            (
                "Exact match intentionally gives no partial credit for semantically equivalent "
                "wording or reordered image lists."
            ),
            (
                "The evaluation exercises deterministic extraction only; rendering and "
                "provider-assisted modes are out of scope."
            ),
        ],
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--without-thresholds",
        action="store_true",
        help="Compute an observed baseline without applying the checked-in regression policy.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when any checked-in regression threshold fails.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    thresholds_path = None if args.without_thresholds else args.thresholds
    if args.check and thresholds_path is None:
        raise SystemExit("--check cannot be combined with --without-thresholds")
    try:
        payload = evaluate(args.manifest, thresholds_path)
    except (OSError, TypeError, ValueError) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2

    rendered = (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=args.output is None,
            sort_keys=True,
        )
        + "\n"
    )
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {args.output}")

    if args.check:
        for check in payload["threshold_checks"]:
            marker = "PASS" if check["passed"] else "FAIL"
            print(
                f"[{marker}] {check['metric']} {check['operator']} "
                f"{check['threshold']} (actual {check['actual']})",
                file=sys.stderr,
            )
        return 0 if payload["gate_passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
