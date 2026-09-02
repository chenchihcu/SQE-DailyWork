from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import build_info


class BuildInfoTests(unittest.TestCase):
    def test_build_label_includes_commit(self) -> None:
        label = build_info.build_label()
        self.assertIn(build_info.__git_commit__, label)

    def test_build_metadata_fields_are_strings_or_bool(self) -> None:
        self.assertIsInstance(build_info.__git_commit__, str)
        self.assertIsInstance(build_info.__build_timestamp__, str)
        self.assertIsInstance(build_info.__dirty_worktree__, bool)

    def test_load_build_metadata_reads_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build-info.json"
            path.write_text(
                json.dumps({"git_commit": "abc1234", "dirty_worktree": False}),
                encoding="utf-8",
            )
            self.assertEqual(
                {"git_commit": "abc1234", "dirty_worktree": False},
                build_info._load_build_metadata(path),
            )

    def test_write_build_info_does_not_mutate_tracked_module(self) -> None:
        tracked_module = Path("src/build_info.py")
        before = tracked_module.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "build-info.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/write_build_info.py",
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["git_commit"])
            self.assertTrue(payload["build_timestamp"])
            self.assertIn("python_version", payload)
            self.assertIn("pyside6_version", payload)
            self.assertIn("pyinstaller_version", payload)
        self.assertEqual(before, tracked_module.read_bytes())


if __name__ == "__main__":
    unittest.main()
