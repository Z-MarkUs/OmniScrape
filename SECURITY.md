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
operator decision, not a consequence of installing Playwright. Enabling it also
requires a non-empty `OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS` policy containing exact,
normalized target hostnames or `host:port` authorities. That policy is checked before
DNS resolution, on HTTP redirects, and during browser navigation; it uses no wildcard
or suffix matching. `OMNISCRAPE_ALLOWED_HOSTS` remains a separate defense for the
inbound HTTP Host header. Enable rendering only for trusted, explicitly authorized
targets and authenticated, rate-limited callers. Rendering arbitrary hostile
third-party pages is outside the supported deployment model.

Code that injects a custom renderer while an outbound allowlist is configured must expose
the identical normalized `outbound_allowed_hosts` policy and enforce it for every
renderer-owned request. OmniScrape rejects policy-unaware or mismatched renderers before
calling them; injected implementations remain trusted code at the network boundary.

URL validation, same-origin routing, request/byte/DOM caps, timeouts, and
`OMNISCRAPE_MAX_RENDER_CONCURRENCY` reduce risk but do not make hostile JavaScript
safe to execute on the API host. Run browser-enabled work under a dedicated OS
account and preferably in a separate container or VM. Enforce CPU, memory, process,
filesystem, and network-egress limits outside the Python process; application-level
semaphores and Chromium flags are not substitutes for OS or orchestrator isolation.
Keep the Chromium sandbox enabled and validate the host's user-namespace and seccomp
support; never add `--no-sandbox` as a deployment workaround. Avoid enabling browser
rendering on a public, multi-tenant deployment.
