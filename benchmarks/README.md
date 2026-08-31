# Offline benchmarks

`run.py` measures deterministic structured-data extraction over the repository's
synthetic article and product fixtures. It performs warm-up iterations, measures
each case independently with `perf_counter_ns`, and writes machine-readable JSON
containing the median, p95, minimum, maximum, and throughput.

```bash
python benchmarks/run.py --iterations 100 --output benchmarks/results/latest.json
```

The benchmark never performs DNS, HTTP, browser, or provider calls. Results are
useful for detecting local regressions, not for making open-web latency claims.
Compare runs only when the fixture corpus, Python/dependency versions, machine,
warm-up policy, and iteration count are the same. Always run correctness tests
alongside performance measurements.
