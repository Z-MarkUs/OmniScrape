"""Build fail-closed GitHub release notes from a versioned changelog section."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_RELEASE_HEADING_RE = re.compile(
    r"^## \[(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\] - (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$"
)
_VERSION_SECTION_RE = re.compile(r"^## \[[^]]+\](?:\s|$)")


class ReleaseNotesError(ValueError):
    """Raised when the tagged changelog cannot produce trustworthy notes."""


def extract_release_section(changelog: str, version: str) -> str:
    """Return the one non-empty, dated changelog section for ``version``."""

    if not _VERSION_RE.fullmatch(version):
        raise ReleaseNotesError(f"invalid release version: {version!r}")

    lines = changelog.splitlines()
    candidates: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith(f"## [{version}]"):
            candidates.append((index, line))

    if not candidates:
        raise ReleaseNotesError(f"CHANGELOG.md has no exact dated section for [{version}]")
    if len(candidates) != 1:
        raise ReleaseNotesError(
            f"CHANGELOG.md has {len(candidates)} sections for [{version}]; expected exactly one"
        )

    start, raw_heading = candidates[0]
    heading = _RELEASE_HEADING_RE.fullmatch(raw_heading)
    if heading is None or heading.group("version") != version:
        raise ReleaseNotesError(f"CHANGELOG.md section heading for [{version}] is malformed")
    release_date = heading.group("date")
    try:
        date.fromisoformat(release_date)
    except ValueError as exc:
        raise ReleaseNotesError(
            f"CHANGELOG.md section [{version}] has an invalid date: {release_date}"
        ) from exc

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _VERSION_SECTION_RE.match(lines[index]):
            end = index
            break

    section = "\n".join(lines[start + 1 : end]).strip()
    release_items = [
        line.strip()[2:].strip() for line in section.splitlines() if line.strip().startswith("- ")
    ]
    if not any(release_items):
        raise ReleaseNotesError(f"CHANGELOG.md section [{version}] contains no release details")

    return section


def render_release_notes(section: str, version: str, repository: str) -> str:
    """Render changelog details plus reproducible release-verification guidance."""

    if not _VERSION_RE.fullmatch(version):
        raise ReleaseNotesError(f"invalid release version: {version!r}")
    if not _REPOSITORY_RE.fullmatch(repository):
        raise ReleaseNotesError(f"invalid GitHub repository: {repository!r}")
    if not section.strip():
        raise ReleaseNotesError("release section is empty")

    tag = f"v{version}"
    return f"""# OmniScrape {tag}

{section.strip()}

## Verify release integrity

Download the immutable assets, validate their checksums, verify their signed build
provenance, and verify the release itself:

```bash
repository="{repository}"
release_tag="{tag}"
release_dir="release-download-${{release_tag}}"

gh release download "$release_tag" --repo "$repository" --dir "$release_dir"
(cd "$release_dir" && sha256sum --check SHA256SUMS)

for artifact in "$release_dir"/*.whl "$release_dir"/*.tar.gz; do
  gh attestation verify "$artifact" \\
    --repo "$repository" \\
    --source-ref "refs/tags/${{release_tag}}" \\
    --signer-workflow "$repository/.github/workflows/ci.yml"
done

gh release verify "$release_tag" --repo "$repository"
```
"""


def build_release_notes(changelog: str, version: str, repository: str) -> str:
    """Extract and render release notes for one exact version."""

    section = extract_release_section(changelog, version)
    return render_release_notes(section, version, repository)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build GitHub release notes from an exact CHANGELOG.md version section."
    )
    parser.add_argument("--changelog", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the notes file, returning non-zero for every validation failure."""

    args = _parser().parse_args(argv)
    try:
        changelog = args.changelog.read_text(encoding="utf-8")
        notes = build_release_notes(changelog, args.version, args.repository)
        args.output.write_text(notes, encoding="utf-8", newline="\n")
    except (OSError, ReleaseNotesError) as exc:
        print(f"release notes error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
