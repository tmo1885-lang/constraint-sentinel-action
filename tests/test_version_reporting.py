"""Regression coverage for source and CLI version consistency."""

import io
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from constraint_sentinel import __version__
from constraint_sentinel.cli import main


class VersionReportingTests(unittest.TestCase):
    def test_cli_version_matches_project_metadata(self) -> None:
        project = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
                encoding="utf-8"
            )
        )
        expected = project["project"]["version"]
        self.assertEqual(__version__, expected)

        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit_info:
            main(["--version"])

        self.assertEqual(exit_info.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), expected)


if __name__ == "__main__":
    unittest.main()
