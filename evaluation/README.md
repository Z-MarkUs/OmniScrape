# Offline extraction-quality evaluation

This directory measures OmniScrape's deterministic extractor against a small,
versioned corpus of original synthetic pages. It is designed for reproducible
regression detection—not as a claim about accuracy on the open web.

## Corpus and license

`gold.json` defines 14 cases: seven articles and seven products. The fixtures
cover JSON-LD (including `@graph` and offer lists), microdata, Open Graph and
product metadata, malformed and conflicting markup, missing optional fields,
relative images, multiple authors, and multilingual Unicode text. Every page
was authored for OmniScrape and is redistributed under the repository's MIT
license; it contains no copied third-party page content.

The manifest is the population. Each case has exactly six evaluated content
fields. `kind` and `url` are request inputs, so they are not scored as extracted
content. Fixture and manifest SHA-256 digests are written into every scorecard.

## Metrics

Values are normalized with Unicode NFKC and whitespace-run collapse, then
compared case-sensitively. Image lists remain ordered and require an exact list
match.

- `present_field_exact_match`: exact matches divided by gold-present fields.
  Expected-absent slots are excluded, so null-heavy cases cannot inflate
  the headline correctness rate.
- `expected_field_completeness`: non-null predictions divided by gold-present
  fields. A wrong non-null prediction is complete but not correct.
- `expected_absence_accuracy`: expected-absent slots correctly left null (or `[]`
  for images) divided by all expected-absent slots. Extraction errors receive no credit.
- `case_pass_rate`: cases whose six fields all match exactly divided by all
  cases.

Every metric stores its numerator, denominator, and `[0, 1]` rate. Results also
include per-kind and per-field breakdowns, predictions, field-level failures,
extraction errors, fixture digests, package and evaluator versions, dependency
versions, and non-sensitive platform metadata.

## Run it

From the repository root with development dependencies installed:

```bash
python -m evaluation.run --check --output build/evaluation-scorecard.json
```

`--check` returns a non-zero exit code when a regression floor fails, making the
command suitable for CI. To refresh the checked-in scorecard after an intentional
extractor or corpus change:

```bash
SOURCE_DATE_EPOCH=1788220800 python -m evaluation.run \
  --check --output evaluation/results/latest.json
```

PowerShell equivalent:

```powershell
$env:SOURCE_DATE_EPOCH = "1788220800"
python -m evaluation.run --check --output evaluation/results/latest.json
```

`SOURCE_DATE_EPOCH` only makes `generated_at` repeatable; scores and digests are
deterministic without it. `thresholds.json` records the observed baseline and
the rationale for its floors. Because the corpus is small, the initial floors
equal the baseline instead of silently allowing one extra lost field.

## Current baseline and limits

The corpus-v1 baseline has 76/76 exact gold-present fields, 76/76 expected
fields present, 8/8 expected-absent slots left absent, no extraction errors, and
14/14 all-fields-exact cases. The corpus includes a leading-headline duplication
case so that regression remains visible to the exact-match gate.

This synthetic, balanced corpus is intentionally narrow. It does not estimate
real-world extraction accuracy, site coverage, rendering performance, or
provider-assisted quality, and exact match gives no partial credit for
semantically equivalent text.
