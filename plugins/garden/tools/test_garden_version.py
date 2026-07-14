from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from plugin_version import (  # noqa: E402
    Version,
    _atomic_write,
    replace_version,
    version_from_text,
)


class PluginVersionTests(unittest.TestCase):
    def test_semver_parser_and_bumps_are_strict(self) -> None:
        version = Version.parse("1.2.3")
        self.assertEqual(Version(1, 2, 4), version.bump("patch"))
        self.assertEqual(Version(1, 3, 0), version.bump("minor"))
        self.assertEqual(Version(2, 0, 0), version.bump("major"))
        for invalid in ("1.2", "v1.2.3", "1.2.3-beta", "01.2.3"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Version.parse(invalid)

    def test_manifest_version_replacement_preserves_json_layout(self) -> None:
        content = '{\n  "name": "garden",\n  "version": "1.2.3",\n  "x": 1\n}\n'
        replaced = replace_version(content, Version(1, 2, 4))
        self.assertEqual("1.2.4", str(version_from_text(replaced)))
        self.assertEqual(content.replace("1.2.3", "1.2.4"), replaced)

    def test_atomic_version_write_preserves_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plugin.json"
            path.write_text("old", encoding="utf-8")
            path.chmod(0o640)
            _atomic_write(path, "new")
            self.assertEqual("new", path.read_text(encoding="utf-8"))
            self.assertEqual(0o640, path.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
