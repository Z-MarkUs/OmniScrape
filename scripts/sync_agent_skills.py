#!/usr/bin/env python3
"""Synchronize portable OmniScrape skill files to the Claude Code mirror."""

from __future__ import annotations

import argparse
import sys
from contextlib import suppress
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL = REPOSITORY_ROOT / ".agents" / "skills" / "omniscrape"
CLAUDE_SKILL = REPOSITORY_ROOT / ".claude" / "skills" / "omniscrape"
CODEX_ONLY_ROOTS = frozenset({"agents"})
IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store"})


def _portable_files(root: Path) -> dict[Path, bytes]:
    if not root.is_dir():
        raise FileNotFoundError(f"canonical skill directory does not exist: {root}")

    files: dict[Path, bytes] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if relative.parts[0] in CODEX_ONLY_ROOTS or any(
            part in IGNORED_NAMES for part in relative.parts
        ):
            continue
        if path.is_symlink():
            raise ValueError(f"portable skill files must not be symlinks: {relative}")
        if path.is_file():
            files[relative] = path.read_bytes()

    if Path("SKILL.md") not in files:
        raise FileNotFoundError(f"canonical skill is missing SKILL.md: {root}")
    return files


def _mirror_files(root: Path) -> dict[Path, bytes]:
    if not root.exists():
        return {}
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Claude skill path must be a real directory: {root}")

    files: dict[Path, bytes] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f"Claude skill mirror must not contain symlinks: {relative}")
        if path.is_file():
            files[relative] = path.read_bytes()
    return files


def _differences(source: dict[Path, bytes], mirror: dict[Path, bytes]) -> list[str]:
    differences: list[str] = []
    for relative in sorted(source.keys() | mirror.keys(), key=Path.as_posix):
        if relative not in source:
            differences.append(f"extra: {relative.as_posix()}")
        elif relative not in mirror:
            differences.append(f"missing: {relative.as_posix()}")
        elif source[relative] != mirror[relative]:
            differences.append(f"changed: {relative.as_posix()}")
    return differences


def _sync(source: dict[Path, bytes], mirror: dict[Path, bytes]) -> None:
    CLAUDE_SKILL.mkdir(parents=True, exist_ok=True)

    for relative in sorted(mirror.keys() - source.keys(), key=Path.as_posix, reverse=True):
        (CLAUDE_SKILL / relative).unlink()

    for relative in sorted(source, key=Path.as_posix):
        destination = CLAUDE_SKILL / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if mirror.get(relative) != source[relative]:
            destination.write_bytes(source[relative])

    directories = sorted(
        (path for path in CLAUDE_SKILL.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        with suppress(OSError):
            directory.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mirror portable .agents OmniScrape skill files into .claude."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without modifying the Claude mirror",
    )
    args = parser.parse_args()

    try:
        source = _portable_files(CANONICAL_SKILL)
        mirror = _mirror_files(CLAUDE_SKILL)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    differences = _differences(source, mirror)
    if args.check:
        if differences:
            print("Claude skill mirror is out of sync:", file=sys.stderr)
            for difference in differences:
                print(f"  {difference}", file=sys.stderr)
            return 1
        print(f"Claude skill mirror is synchronized ({len(source)} portable file(s)).")
        return 0

    _sync(source, mirror)
    destination = CLAUDE_SKILL.relative_to(REPOSITORY_ROOT)
    print(f"Synchronized {len(source)} portable file(s) to {destination}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
