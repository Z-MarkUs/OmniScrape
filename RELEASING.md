# Releasing OmniScrape

OmniScrape releases are deliberately small, auditable, and immutable. A release
tag never bypasses the same quality, browser, packaging, container, and security
gates required on `main`.

## Prepare the release

1. Choose the next [Semantic Versioning](https://semver.org/) version.
2. Update `project.version` in `pyproject.toml` and `__version__` in
   `src/omniscrape/__init__.py` to the same value.
3. Update version-specific install or verification examples in `README.md`.
4. Move the relevant `CHANGELOG.md` entries from `Unreleased` into a dated
   version section and update its comparison links.
5. Do not rewrite historical benchmark metadata merely to match the new package
   version; benchmark results describe the version that produced them.
6. Run the complete local gate from a clean checkout:

   ```bash
   make check
   ```

7. Build into an empty output directory, run Twine, inspect the source archive,
   and install both the wheel and source archive in fresh environments.
8. Open a focused pull request. Merge only after every protected CI and CodeQL
   check succeeds.

## Publish

Create an annotated tag on the verified `main` commit. Use a concise annotation;
the public release notes are generated from the exact tagged version section in
`CHANGELOG.md` and include checksum, provenance, and immutable-release verification
commands. The release workflow fails closed if that dated section is absent, empty,
duplicated, malformed, or does not match the tag version.

```bash
git switch main
git pull --ff-only
release_version="$(python -c \
  'import pathlib, re; print(re.search(r"(?m)^version = \"([^\"]+)\"$", pathlib.Path("pyproject.toml").read_text()).group(1))')"
release_tag="v${release_version}"
git tag --annotate "$release_tag" --message "OmniScrape ${release_tag}"
git push origin "refs/tags/${release_tag}"
```

The tag first runs every normal CI gate. A final no-checkout tag job downloads the
exact distributions from that run, validates their versions, and creates signed SLSA
build-provenance attestations whose identity is the tagged commit. After CI succeeds,
a separate release workflow loaded from protected `main` verifies that the annotated
tag points to the CI-tested commit and that the commit belongs to `main`. It revalidates
the distributions, generates `SHA256SUMS`, and publishes the GitHub release. Before
publishing, it loads the note generator from the protected workflow commit and treats
the tagged commit's `CHANGELOG.md` only as data; it never checks out or executes
tag-controlled repository code. The privileged release job has no OIDC permission.

Do not create a release manually while that workflow is running. Release
immutability locks the tag and uploaded assets after publication; correct a
mistake with a new patch version instead of moving a tag or replacing a file.
If tag CI needs a retry, use **Re-run all jobs** rather than **Re-run failed
jobs** so the attempt-specific distributions are rebuilt and re-attested together.

## Verify the public release

```bash
release_version="$(python -c \
  'import pathlib, re; print(re.search(r"(?m)^version = \"([^\"]+)\"$", pathlib.Path("pyproject.toml").read_text()).group(1))')"
release_tag="v${release_version}"
verified_commit="$(git rev-list --max-count=1 "$release_tag")"
gh release view "$release_tag" --repo Z-MarkUs/OmniScrape
gh release verify "$release_tag" --repo Z-MarkUs/OmniScrape
gh release download "$release_tag" --repo Z-MarkUs/OmniScrape --dir release-download
(cd release-download && sha256sum --check SHA256SUMS)
for artifact in \
  "release-download/omniscrape_zmarkus-${release_version}-py3-none-any.whl" \
  "release-download/omniscrape_zmarkus-${release_version}.tar.gz"; do
  gh attestation verify "$artifact" \
    --repo Z-MarkUs/OmniScrape \
    --source-ref "refs/tags/${release_tag}" \
    --source-digest "$verified_commit" \
    --signer-workflow Z-MarkUs/OmniScrape/.github/workflows/ci.yml
done
```

Also verify `SHA256SUMS`, install the public wheel in a fresh environment, run
`pip check`, and smoke-test the import, CLI, API factory, and packaged web assets.
Record the release URL, tag CI URL, immutable status, and artifact digests in the
release audit.

PyPI publication remains a separate manual decision. Never upload to PyPI or any
other package index without explicit maintainer authorization and a successful
trusted-publisher review.
