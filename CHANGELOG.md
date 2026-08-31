# Changelog

All notable changes to OmniScrape are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.2] - 2026-09-01

### Added

- Added Python 3.11 to the hosted test matrix so every supported interpreter from
  Python 3.10 through 3.13 now runs the offline suite.
- Added enumerated MCP inputs, a discriminated success/error output schema, and
  read-only, non-destructive, idempotent tool annotations.
- Added conditional OpenAPI security schemes for both supported API-key transports,
  an eager CLI `--version` option, and `Retry-After` guidance on busy responses.
- Added a recruiter-focused engineering-evidence summary and a credential-free,
  deterministic console result capture.

### Changed

- Refreshed the checked-in synthetic benchmark under the current package version and
  added a regression test that prevents version-stale benchmark evidence.
- Raised the optional MCP SDK floor to `1.28.1`, which supports the typed contract
  and contains fixes for known advisories, and added a real-SDK CI smoke at that floor.

## [0.2.1] - 2026-09-01

### Added

- Added tag-gated GitHub release publishing with exact-distribution install smokes,
  SHA-256 checksums, and signed SLSA build-provenance attestations after every
  required CI job succeeds.

### Changed

- Limited routine Dependabot updates to supported dependency and container-runtime
  lines so automated maintenance stays aligned with the tested compatibility policy.

### Fixed

- Included `.env.example` in source distributions so the documented configuration
  workflow remains self-contained outside a Git checkout.

## [0.2.0] - 2026-08-31

### Added

- Secure async fetcher with HTTP(S)-only URL policy, DNS and IP validation,
  redirect revalidation, peer checks, size caps, and explicit timeouts.
- Typed article, product, result, metadata, usage, health, and error contracts.
- Deterministic structured-data, readability, and DOM-heuristic extraction.
- Optional Playwright rendering and OpenAI Responses structured-output adapter.
- Reusable async Python client, Typer CLI, FastAPI JSON and SSE endpoints,
  responsive web console, and optional MCP server.
- API-key authentication, bounded concurrency, request IDs, safe errors, and
  security response headers.
- Offline fixture suite, reproducible benchmark, strict lint/type/coverage gates,
  dependency and static security audits, and multi-version CI.
- Hardened non-root container, local-only Compose binding, Dependabot, security
  policy, contribution guide, and MIT license.
- Synchronized project skills for Codex and Claude Code.

### Changed

- Disabled browser rendering on HTTP extraction routes by default. Existing API
  clients that send `render: true` must be limited to trusted targets and run on
  a browser-capable, externally resource-isolated deployment, then opt in with
  `OMNISCRAPE_ENABLE_API_RENDERING=true`.
- Added strict `OMNISCRAPE_MAX_RENDER_CONCURRENCY` validation (`1` or `2`), a
  stable `403 rendering_disabled` error, and separate `renderer_enabled` and
  effective `renderer_available` health fields.
- Replaced the original prototype and duplicate legacy implementations with one
  package under `src/omniscrape`.
- Made deterministic extraction the documented default and isolated browser and
  provider features behind optional dependencies.
- Rebuilt project documentation around auditable behavior and verified claims.

### Fixed

- Made deterministic extraction the actual default across Python, CLI, HTTP,
  MCP, and web-console surfaces while preserving explicit provider modes and
  legacy local-mode aliases.
- Deferred OpenAI SDK import and async-client creation until provider use, bounded
  provider calls, and added explicit owned-versus-injected client shutdown semantics.
- Hardened HTTP and browser isolation against DNS rebinding, shared-IP connection and
  cookie reuse, private side channels, popups, downloads, compression bombs, unbounded
  DNS answers, redirect/request amplification, and slow-loris responses.
- Added MCP lifecycle cleanup and generic exception redaction.
- Included the complete offline test suite and fixtures in source distributions.

### Removed

- Archived scraper copies, generated package metadata, result dumps, editor
  artifacts, stale documentation, and tracked secret files.
- Prototype-only `/health.json`, `/status*`, `/monitor`, `/crawl*`, `/crawler`,
  and `/labs*` routes. Migrate health checks to `/health` and extraction clients
  to `/v1/extract` or `/v1/extract/stream`.

[Unreleased]: https://github.com/Z-MarkUs/OmniScrape/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/Z-MarkUs/OmniScrape/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Z-MarkUs/OmniScrape/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Z-MarkUs/OmniScrape/releases/tag/v0.2.0
