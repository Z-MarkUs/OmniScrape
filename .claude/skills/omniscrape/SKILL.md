---
name: omniscrape
description: Run, test, debug, extend, benchmark, or integrate the OmniScrape hybrid web-extraction project through its CLI, Python API, HTTP API, or MCP server. Use for OmniScrape implementation work, extraction-mode decisions, regressions, performance claims, and consumer integrations.
---

# OmniScrape

Work from the repository root and inspect the current code and `--help` output before changing public behavior. Keep the CLI, Python, HTTP, and MCP surfaces consistent when a shared contract changes.

## Safety boundary

- Default to repository-owned offline fixtures and mocked transports. Do not invent or probe a live target.
- Use a live URL only when the user has authorized that exact target or domain and the intended operation. Keep request volume and concurrency within that authorization.
- Respect applicable law, site terms, robots directives, access controls, copyright, privacy, and data-retention limits. Stop when authorization or permitted use is unclear.
- Do not bypass authentication, paywalls, CAPTCHAs, anti-bot controls, or rate limits. Do not weaken SSRF protections to make a test pass.
- Treat rendering, `auto`, and `llm` as potential network operations. LLM modes may also send page content to a provider and incur cost.
- Never commit credentials or put secrets in commands, fixtures, logs, exceptions, benchmark results, or examples. Use environment variables and redact sensitive headers and content.
- Bind development services to `127.0.0.1` unless the user explicitly requests and secures broader exposure. Preserve API authentication when configured.

## Choose the extraction mode deliberately

| Mode | Behavior | Use when |
| --- | --- | --- |
| `deterministic` | Provider-free structured-data, readability, and heuristic extraction. Legacy `none`, `sd`, and `local` values are accepted as aliases. | Default for development, CI, reproducible tests, private content, and cost-free runs. |
| `auto` | Runs deterministic extraction first and calls the configured LLM provider only when required fields remain incomplete. | The user accepts conditional data egress, latency, and cost. |
| `llm` | Returns provider-extracted data. Deterministic parsers may still run after the shared fetch for diagnostics and completeness metadata, but they do not fill the provider output. | The task explicitly needs provider-backed extraction and the user has supplied or approved credentials and cost. |

`--render` controls browser rendering independently of extraction mode. Leave it off unless JavaScript rendering is required and the target is authorized.

## Set up only what the task needs

```bash
python -m pip install -e ".[dev]"
```

Add optional extras only for the selected surface:

```bash
python -m pip install -e ".[dev,browser]"  # Playwright rendering
python -m pip install -e ".[dev,llm]"      # provider-backed modes
python -m pip install -e ".[dev,mcp]"      # MCP server
```

After installing the browser extra, install Chromium only when a render test is required:

```bash
python -m playwright install chromium
```

## Route the task to the supported surface

### CLI

Inspect the installed contract with `python -m omniscrape --help` and `python -m omniscrape extract --help`.

```bash
python -m omniscrape extract URL --kind article --mode deterministic --compact
python -m omniscrape extract URL --kind product --mode auto --render --pretty
python -m omniscrape serve --host 127.0.0.1 --port 8000
python -m omniscrape mcp
```

`URL` must be a user-authorized target. Do not substitute an arbitrary public example for a smoke test; exercise offline fixtures through tests instead.

### HTTP API

- `GET /health` (`/healthz` is a compatibility alias)
- `POST /v1/extract` (`/extract` is a compatibility alias)
- `POST /v1/extract/stream` (`/extract-stream` is a compatibility alias)
- Request JSON: `{"url":"...","kind":"article|product","mode":"deterministic|auto|llm","render":false}`
- Omitting `mode` defaults to `deterministic`; `auto` and `llm` must be selected explicitly.
- Legacy request field `llmMode` remains accepted for compatibility.
- The API rejects `render: true` with `403 rendering_disabled` unless `OMNISCRAPE_ENABLE_API_RENDERING=true`. Enable it only for trusted, authorized targets in an externally CPU- and memory-limited browser deployment; keep `OMNISCRAPE_MAX_RENDER_CONCURRENCY` at `1` or `2`.
- Health reports policy separately from readiness: `renderer_enabled=false` always means `renderer_available=false` and skips the browser probe.
- When server authentication is configured, send `X-API-Key` or a Bearer token. Never place the value in tracked examples.
- The streaming route emits named server-sent events with JSON payloads and terminates with `complete` or `error`; clients must handle both terminal events and disconnects.

Prefer FastAPI's in-process test client or an HTTP mock for integration tests. Start the local server only when process-level behavior is under test.

### Python

Use the async convenience function or client instead of importing internal modules:

```python
from omniscrape import OmniScrape, extract

result = await extract(
    "https://authorized.example/article",
    kind="article",
    mode="deterministic",
    render=False,
)

async with OmniScrape() as client:
    result = await client.extract(
        "https://authorized.example/product",
        kind="product",
        mode="deterministic",
        render=False,
    )
```

Both Python extraction callables default to deterministic mode. The top-level `extract(...)` convenience function reads environment-backed settings, but an ambient `OPENAI_API_KEY` only configures a lazy provider: deterministic calls do not import the optional SDK or construct its client. A directly constructed `OmniScrape()` client is deterministic-only unless a provider is injected; use `OmniScrape.from_settings(Settings.from_env())` when an environment-configured provider is intentional. Internally created OpenAI clients are closed with the service; injected clients remain caller-owned unless ownership is explicitly transferred.

Use `create_app(...)` for ASGI embedding and lazy `create_mcp_server(...)` for programmatic MCP integration. Do not depend on private `omniscrape.*` implementation modules from consumer code.

### MCP

Launch the stdio server with `python -m omniscrape mcp`. It exposes `extract` with arguments `url: str`, `kind: article|product = article`, `mode: deterministic|auto|llm = deterministic`, and `render: bool = false`. Inspect the connected server's advertised schema before relying on it, pass only an authorized URL, and do not silently escalate to `auto`, `llm`, or rendering.

Relevant environment configuration uses the `OMNISCRAPE_` prefix. `OMNISCRAPE_API_KEY` protects the HTTP service; `OPENAI_API_KEY` and `OMNISCRAPE_OPENAI_MODEL` enable the OpenAI adapter. Use `Settings.from_env()` rather than reading environment variables throughout the code. Never add an allow-private-network bypass; keep loopback and private-address blocking in the URL policy.

## Development workflow

1. Reproduce against the smallest offline article or product fixture in deterministic mode.
2. Locate the failing layer: input/URL policy, fetch, optional render, structured parsing, readability or heuristics, completeness policy, provider adapter, schema, or transport serialization.
3. Add or update a fixture and a regression test before or with the fix. Mock network and provider responses; make paid-service tests opt-in.
4. Preserve stable field semantics and compatibility aliases unless the user requested a breaking change. Update every public surface affected by a contract change.
5. Run the focused test while iterating, then the relevant verification gate below.

Do not solve fixture failures by loosening security checks, adding target-specific bypasses, or hiding errors behind LLM fallback. Keep provider usage observable through real metadata; never fabricate token, cost, latency, or extraction-quality values.

## Verification gates

For ordinary changes, run the checks that cover the touched surface and finish with the full local gate:

```bash
python -m pytest -m "not live" -q
python -m ruff check src tests benchmarks
python -m ruff format --check src tests benchmarks
python -m mypy src/omniscrape
python -m build
```

Use `make check` when the repository's Make target maps to the same gate. Run tests marked `live` only with explicit live-target authorization; absence of credentials or network is not a reason to weaken or skip offline coverage.

For a behavioral claim, name the test that proves it and report the exact command and result. A passing narrow unit test does not prove all transports or extraction modes.

## Benchmarking and performance claims

Run the fixture-backed benchmark without external network access:

```bash
python benchmarks/run.py --iterations 100 --output benchmarks/results/latest.json
```

Before claiming a speed, quality, or reliability improvement:

- compare before and after with the same fixture corpus, mode, dependency set, machine, warm-up policy, and iteration count;
- retain the machine-readable result and report the command, sample count, and relevant median/tail metrics;
- run the correctness tests as well as the benchmark so a faster regression is not called an improvement;
- distinguish measured results from hypotheses and do not generalize fixture results to the open web.

## Keep the portable skill synchronized

`.agents/skills/omniscrape` is canonical. After changing portable skill content, run:

```bash
python scripts/sync_agent_skills.py
python scripts/sync_agent_skills.py --check
```

The Claude mirror must remain byte-identical for portable files. Codex-only `agents/openai.yaml` metadata intentionally stays under the canonical skill.
