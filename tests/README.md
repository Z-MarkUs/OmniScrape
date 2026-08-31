# Test suite

The suite is deliberately offline and deterministic. Every HTML document in
`fixtures/` is original, synthetic test data authored for OmniScrape; no copied
publisher or store content is checked into the repository.

```bash
python -m pytest
python -m pytest -m "not integration"
python -m pytest --cov=omniscrape --cov-report=term-missing
```

Network-facing behavior is normally tested with an in-memory HTTP transport. Tests must
not call the public internet or require an API key. The explicit `browser`-marked
security suite starts a local Chromium instance against a loopback-only fixture server
to verify browser policy; CI runs that controlled exception in its own job.
The source distribution includes this complete offline suite, `conftest.py`, all
synthetic fixtures, and the benchmark runner used by its regression test so the
suite can run after unpacking the archive. The separate `evaluation/` corpus adds
14 original synthetic article/product cases, explicit gold labels, frozen
thresholds, and a machine-readable scorecard; run it with
`python -m evaluation.run --check --output build/evaluation-scorecard.json`.
