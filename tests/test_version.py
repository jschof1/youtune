import re
import tomllib
from pathlib import Path

import youtune


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_version_matches_package_metadata():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert youtune.__version__ == data["project"]["version"]


def test_readme_example_uses_current_version():
    readme = (ROOT / "README.md").read_text()

    assert f"youtune v{youtune.__version__}" in readme


def test_changelog_has_current_version_entry():
    changelog = (ROOT / "CHANGELOG.md").read_text()

    assert re.search(rf"^## \[{re.escape(youtune.__version__)}\]", changelog, re.MULTILINE)
