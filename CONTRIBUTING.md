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
`pytest`, and `python -m build`; see `Makefile` for exact arguments.

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

By contributing, you agree that your work is licensed under the MIT License.

## Security-sensitive changes

URL safety is checked before the first request and after every redirect.
Changes that weaken scheme, credential, DNS, IP-range, timeout, redirect, or
body-size checks need an explicit rationale and dedicated negative tests.
Report undisclosed vulnerabilities privately as described in `SECURITY.md`.

## Maintainer release checklist

1. Update the version and dated changelog entry, then run `make check` from a
   clean checkout.
2. Rebuild `dist/`, run `python -m twine check dist/*`, and install the wheel in
   a fresh environment for CLI, import, API, and package-data smoke tests.
3. Push `main` and wait for both CI and CodeQL to succeed.
4. Create the `v<version>` tag, wait for the tag-triggered CI run, then create
   the GitHub release and attach the verified wheel and source archive.

PyPI publication is intentionally separate and manual. The distribution name is
`omniscrape-zmarkus`; never upload it—or any other external artifact—without the
maintainer's explicit authorization and a successful trusted-publisher check.
