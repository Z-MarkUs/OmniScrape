# Contributing to OmniScrape

Thanks for helping make extraction safer and more predictable.

## Local setup

Python 3.10 or newer is required.

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the complete local gate before opening a pull request:

```bash
make check
```

The equivalent commands are `ruff check`, `ruff format --check`, `mypy`,
`pytest`, the offline extraction-quality gate, dependency/security audits, and
`python -m build`; see `Makefile` for exact arguments.

## Pull requests

- Keep changes focused and explain the user-visible behavior.
- Add an offline regression test for every bug fix or new extraction rule.
- Use synthetic fixtures that you authored or data with an explicit compatible
  license. Do not commit copied articles, store pages, personal data, cookies,
  access tokens, or API keys.
- Mock DNS and HTTP at the boundary. The default test suite must not contact
  public websites or require a browser or paid provider.
- Update documentation when public API, CLI, configuration, or security
  behavior changes.
- For performance work, include reproducible before-and-after benchmark JSON;
  do not optimize against a single warm run.
- For extraction-quality work, keep gold labels independent of current output,
  inspect every numerator and denominator, and refresh the checked-in scorecard
  only after an intentional extractor or corpus change. Never weaken a threshold
  merely to make a regression pass.

By contributing, you agree that your work is licensed under the MIT License.

## Security-sensitive changes

URL safety and any configured exact outbound target policy are checked before the
first DNS lookup and after every redirect. Changes that weaken allowlist matching,
scheme, credential, DNS, IP-range, timeout, redirect, or body-size checks need an
explicit rationale and dedicated negative tests.
Report undisclosed vulnerabilities privately as described in `SECURITY.md`.

## Maintainer release checklist

Follow [RELEASING.md](RELEASING.md). In short: update the version and dated
changelog in a focused pull request, pass the complete merge gate, then push one
annotated `v<version>` tag. Tag CI and the protected default-branch release workflow
validate, attest, and publish the immutable GitHub release; maintainers must never
replace a published artifact. Public notes are generated from the exact dated
version section in the tagged `CHANGELOG.md`, so that section must be meaningful.

PyPI publication is intentionally separate and manual. The distribution name is
`omniscrape-zmarkus`; never upload it—or any other external artifact—without the
maintainer's explicit authorization and a successful trusted-publisher check.
