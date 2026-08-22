from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import app_paths


class AppPathsTests(unittest.TestCase):
    def test_source_runtime_root_matches_repo_layout(self) -> None:
        root = app_paths.runtime_root()
        self.assertTrue((root / "src" / "app_paths.py").exists())
        self.assertEqual(root / "data", app_paths.formal_data_dir())
        self.assertEqual(root / "data" / "sqe_v2.db", app_paths.formal_db_path())

    def test_outputs_and_anomaly_folder_under_runtime_root(self) -> None:
        root = app_paths.runtime_root()
        self.assertEqual(root / "Outputs", app_paths.outputs_dir())
        self.assertEqual(
            root / "Outputs" / "ncr number file",
            app_paths.anomaly_folder_root(),
        )

    @patch.dict("os.environ", {"SQE_DB_PATH": "scratch/custom/sqe_v2.db"}, clear=False)
    def test_resolve_db_path_honors_env_override(self) -> None:
        resolved = app_paths.resolve_db_path()
        self.assertTrue(
            str(resolved).replace("\\", "/").endswith("scratch/custom/sqe_v2.db")
        )
        self.assertNotEqual(resolved, app_paths.formal_db_path())
        self.assertEqual(
            app_paths.data_dir().resolve(),
            (Path.cwd() / "scratch" / "custom").resolve(),
        )

    @patch.object(sys, "frozen", True, create=True)
    @patch.object(sys, "executable", "C:/Apps/SQE/SQE_DailyWork.exe")
    def test_frozen_runtime_root_uses_executable_parent(self) -> None:
        self.assertTrue(app_paths.is_frozen())
        self.assertEqual(Path("C:/Apps/SQE"), app_paths.runtime_root())
        self.assertEqual(Path("C:/Apps/SQE/data/sqe_v2.db"), app_paths.formal_db_path())
        self.assertEqual(Path("C:/Apps/SQE/Outputs"), app_paths.outputs_dir())


if __name__ == "__main__":
    unittest.main()
