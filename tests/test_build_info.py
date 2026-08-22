from __future__ import annotations

import unittest

import build_info


class BuildInfoTests(unittest.TestCase):
    def test_build_label_includes_commit(self) -> None:
        label = build_info.build_label()
        self.assertIn(build_info.__git_commit__, label)

    def test_build_metadata_fields_are_strings_or_bool(self) -> None:
        self.assertIsInstance(build_info.__git_commit__, str)
        self.assertIsInstance(build_info.__build_timestamp__, str)
        self.assertIsInstance(build_info.__dirty_worktree__, bool)


if __name__ == "__main__":
    unittest.main()
