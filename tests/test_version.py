import re
from importlib.metadata import version
from pathlib import Path

from omniscrape import __version__


def test_runtime_version_matches_distribution_metadata() -> None:
    assert __version__ == version("omniscrape-zmarkus")


def test_readme_release_artifacts_match_runtime_version() -> None:
    readme = Path(__file__).parents[1].joinpath("README.md").read_text(encoding="utf-8")
    artifact_versions = set(
        re.findall(
            r"omniscrape_zmarkus-(\d+\.\d+\.\d+)(?:-py3-none-any\.whl|\.tar\.gz)",
            readme,
        )
    )
    tag_versions = set(
        re.findall(
            r"(?:releases/download/|refs/tags/|release verify )v(\d+\.\d+\.\d+)",
            readme,
        )
    )
    assert artifact_versions == {__version__}
    assert tag_versions == {__version__}
