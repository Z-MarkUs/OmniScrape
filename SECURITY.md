# Security policy

## Supported versions

Security fixes are made on the `main` branch. Use the latest release before
reporting a problem that may already have been fixed.

## Reporting a vulnerability

Please use **Security → Report a vulnerability** in this repository so the
report and any proof of concept remain private. Do not include secrets,
personal data, or details of a live third-party system. Please allow a
reasonable period for triage and remediation before public disclosure.

Useful reports include the affected version or commit, impact, minimal
reproduction steps, and a suggested mitigation. You can expect an initial
acknowledgement within seven days and a status update after triage.

## Scope and safe research

In scope are OmniScrape's URL validation, redirect handling, authentication,
content-size limits, secret handling, and dependency supply chain. Test only
systems you own or have explicit permission to assess. Automated scanning or
scraping of third-party services is outside the scope of this policy.

Never put production credentials in an issue, fixture, commit, log, or example.
If a credential is exposed, revoke it first; deleting a file does not remove it
from Git history.

## Browser-renderer deployment

Browser rendering executes JavaScript supplied by the target page. The HTTP API
keeps it disabled by default; setting `OMNISCRAPE_ENABLE_API_RENDERING=true` is an
operator decision, not a consequence of installing Playwright. Enable it only for
trusted, explicitly authorized target domains and authenticated, rate-limited callers.
`OMNISCRAPE_ALLOWED_HOSTS` protects the inbound HTTP Host header; it is not an
outbound target allowlist. Rendering arbitrary hostile third-party pages is outside the
supported deployment model.

URL validation, same-origin routing, request/byte/DOM caps, timeouts, and
`OMNISCRAPE_MAX_RENDER_CONCURRENCY` reduce risk but do not make hostile JavaScript
safe to execute on the API host. Run browser-enabled work under a dedicated OS
account and preferably in a separate container or VM. Enforce CPU, memory, process,
filesystem, and network-egress limits outside the Python process; application-level
semaphores and Chromium flags are not substitutes for OS or orchestrator isolation.
Keep the Chromium sandbox enabled and validate the host's user-namespace and seccomp
support; never add `--no-sandbox` as a deployment workaround. Avoid enabling browser
rendering on a public, multi-tenant deployment.
