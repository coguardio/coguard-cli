"""
Tests that the files the CLI reads at runtime, other than its Python modules,
are part of the package. setuptools only ships those if they are matched by a
pattern in the `[options.package_data]` section of `setup.cfg`, and a file which
is missing there works from a checkout, and fails once installed from PyPI.
"""

import configparser
import glob
import unittest
from pathlib import Path
from coguard_cli.ci_cd.ci_cd_providers.ci_cd_provider_github import WORKFLOWS

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SETUP_CFG = PACKAGE_ROOT.parent.parent / "setup.cfg"

# The files in the package which are not read at runtime, and hence not shipped.
NOT_SHIPPED = frozenset([
    "cloudera_integration/README.md",
])


def _package_data_patterns():
    parser = configparser.ConfigParser()
    parser.read(SETUP_CFG)
    return [
        pattern.strip()
        for pattern in parser.get("options.package_data", "coguard_cli").splitlines()
        if pattern.strip()
    ]


def _shipped_files():
    # The patterns are expanded the way setuptools expands them, with
    # `glob.glob(..., recursive=True)`. `Path.glob` would not do: before Python
    # 3.13, a pattern ending in `**` matches directories only.
    return {
        Path(path).relative_to(PACKAGE_ROOT).as_posix()
        for pattern in _package_data_patterns()
        for path in glob.glob(str(PACKAGE_ROOT / pattern), recursive=True)
        if Path(path).is_file()
    }


@unittest.skipUnless(SETUP_CFG.is_file(),
                     "Only applicable to a source checkout.")
class TestPackaging(unittest.TestCase):
    """
    The class for testing the package data configuration.
    """

    def test_every_data_file_is_shipped(self):
        """
        Every file of the package which is not a Python module is matched by a
        package data pattern, or deliberately not shipped.
        """
        data_files = {
            path.relative_to(PACKAGE_ROOT).as_posix()
            for path in PACKAGE_ROOT.rglob("*")
            if path.is_file()
            and path.suffix not in (".py", ".pyc")
            and "__pycache__" not in path.parts
            and path.relative_to(PACKAGE_ROOT).parts[0] != "tests"
        }
        self.assertSetEqual(data_files - _shipped_files() - NOT_SHIPPED, set())

    def test_github_workflows_are_shipped(self):
        """
        Every workflow the GitHub Actions provider can add is a file of the
        package, and matched by a package data pattern.
        """
        shipped = _shipped_files()
        for source_name, _ in WORKFLOWS.values():
            self.assertIn(f"ci_cd/ci_cd_scripts/github/{source_name}", shipped)
