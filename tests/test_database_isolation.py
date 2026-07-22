from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import connection


class DatabaseIsolationTests(unittest.TestCase):
    def test_disposable_guard_rejects_formal_database(self) -> None:
        with patch.dict(os.environ, {"SQE_REQUIRE_DISPOSABLE_DB": "1"}):
            with self.assertRaisesRegex(RuntimeError, "formal SQE database"):
                connection.get_connection(connection.DEFAULT_DB_PATH)

    def test_disposable_guard_allows_non_formal_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sqe_v2.db"
            with patch.dict(os.environ, {"SQE_REQUIRE_DISPOSABLE_DB": "1"}):
                with connection.get_connection(target) as conn:
                    self.assertEqual(1, conn.execute("SELECT 1").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
