from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release_notes import (
    ReleaseNotesError,
    build_release_notes,
    extract_release_section,
    main,
)

CHANGELOG = """# Changelog

## [Unreleased]

- Not part of a published release.

## [0.3.0] - 2026-09-01

### Added

- Added a guarded release-note generator.
- Added a second verified feature.

## [0.2.2] - 2026-08-31

### Fixed

- Previous behavior.
"""


def test_extract_release_section_selects_only_exact_version() -> None:
    section = extract_release_section(CHANGELOG, "0.3.0")

    assert "guarded release-note generator" in section
    assert "second verified feature" in section
    assert "Not part of a published release" not in section
    assert "Previous behavior" not in section


@pytest.mark.parametrize(
    ("changelog", "version", "message"),
    [
        (CHANGELOG, "0.4.0", "no exact dated section"),
        (CHANGELOG, "v0.3.0", "invalid release version"),
        (
            "## [0.3.0] - 2026-09-01\n\n## [0.2.2] - 2026-08-31\n\n- Old\n",
            "0.3.0",
            "contains no release details",
        ),
        (
            "## [0.3.0]\n\n- Missing date\n",
            "0.3.0",
            "heading.*malformed",
        ),
        (
            "## [0.3.0] - 2026-02-30\n\n- Invalid date\n",
            "0.3.0",
            "invalid date",
        ),
        (
            "## [0.3.0] - 2026-09-01\n\n- First\n\n## [0.3.0] - 2026-09-02\n\n- Duplicate\n",
            "0.3.0",
            "expected exactly one",
        ),
        (
            "## [0.3.0] - 2026-09-01\n\n- Valid\n\n## [0.3.0]\n\n- Malformed duplicate\n",
            "0.3.0",
            "expected exactly one",
        ),
        (
            "## [0.3.0] - 2026-09-01\n\n### Added\n\n<!-- TODO -->\n---\n",
            "0.3.0",
            "contains no release details",
        ),
    ],
)
def test_extract_release_section_fails_closed(changelog: str, version: str, message: str) -> None:
    with pytest.raises(ReleaseNotesError, match=message):
        extract_release_section(changelog, version)


def test_build_release_notes_includes_required_verification_guidance() -> None:
    notes = build_release_notes(CHANGELOG, "0.3.0", "Z-MarkUs/OmniScrape")

    assert notes.startswith("# OmniScrape v0.3.0\n")
    assert "guarded release-note generator" in notes
    assert "SHA256SUMS" in notes
    assert "sha256sum --check" in notes
    assert "gh attestation verify" in notes
    assert '--source-ref "refs/tags/${release_tag}"' in notes
    assert 'repository="Z-MarkUs/OmniScrape"' in notes
    assert '"$repository/.github/workflows/ci.yml"' in notes
    assert "gh release verify" in notes


def test_main_writes_validated_notes(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "release-notes.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    result = main(
        [
            "--changelog",
            str(changelog),
            "--version",
            "0.3.0",
            "--repository",
            "Z-MarkUs/OmniScrape",
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert "# OmniScrape v0.3.0" in output.read_text(encoding="utf-8")


def test_main_does_not_write_notes_for_mismatched_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "release-notes.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    result = main(
        [
            "--changelog",
            str(changelog),
            "--version",
            "9.9.9",
            "--repository",
            "Z-MarkUs/OmniScrape",
            "--output",
            str(output),
        ]
    )

    assert result == 2
    assert not output.exists()
    assert "no exact dated section for [9.9.9]" in capsys.readouterr().err
