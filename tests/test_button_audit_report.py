from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import button_audit_report as audit


class ButtonAuditReportTests(unittest.TestCase):
    def test_import_does_not_mutate_database_routing_environment(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        code = (
            "import os; "
            "os.environ.pop('SQE_TESTING', None); "
            "os.environ.pop('SQE_REQUIRE_DISPOSABLE_DB', None); "
            "import scripts.button_audit_report; "
            "print(os.environ.get('SQE_TESTING')); "
            "print(os.environ.get('SQE_REQUIRE_DISPOSABLE_DB'))"
        )

        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(["None", "None"], completed.stdout.splitlines())

    def test_page_registry_keys(self) -> None:
        self.assertEqual(len(audit.PAGE_KEYS), 9)
        self.assertIn("main_window", audit.PAGE_KEYS)
        self.assertIn("event_create_anomaly", audit.PAGE_KEYS)
        self.assertIn("supplier_form", audit.PAGE_KEYS)
        self.assertNotIn("event_create_visit", audit.PAGE_KEYS)

    def test_is_seh_returncode(self) -> None:
        self.assertTrue(audit.is_seh_returncode(-1073741819))
        self.assertTrue(audit.is_seh_returncode(3221226356))
        self.assertFalse(audit.is_seh_returncode(0))

    def test_build_report_markdown_includes_structural_section(self) -> None:
        markdown = audit.build_report_markdown(
            [
                {
                    "page_key": "event_create_anomaly",
                    "results": [],
                    "exit": "ok",
                    "structural_only": True,
                },
                {
                    "page_key": "supplier_form",
                    "results": [{"page": "SupplierFormDialog", "name": "ok", "status": "OK"}],
                    "exit": "ok",
                },
            ]
        )
        self.assertIn("結構驗證頁面", markdown)
        self.assertIn("`event_create_anomaly`", markdown)

    def test_structural_only_page_keys(self) -> None:
        self.assertEqual(frozenset({"event_create_anomaly"}), audit.STRUCTURAL_ONLY_PAGE_KEYS)

    def test_build_report_markdown_includes_seh_section(self) -> None:
        markdown = audit.build_report_markdown(
            [
                {"page_key": "main_window", "results": [], "exit": "seh"},
                {
                    "page_key": "supplier_form",
                    "results": [{"page": "SupplierFormDialog", "name": "ok", "status": "OK"}],
                    "exit": "ok",
                },
            ]
        )
        self.assertIn("隔離模式: subprocess-per-page", markdown)
        self.assertIn("## SEH 崩潰頁面", markdown)
        self.assertIn("`main_window`", markdown)

    def test_write_report_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "button_audit_report.md"
            audit.write_report(
                [
                    {
                        "page_key": "supplier_form",
                        "results": [],
                        "exit": "ok",
                    }
                ],
                report_path=target,
            )
            self.assertTrue(target.is_file())
            self.assertIn("隔離模式", target.read_text(encoding="utf-8"))

    def test_orchestrator_merges_subprocess_payloads(self) -> None:
        payloads = {
            "supplier_form": {
                "page_key": "supplier_form",
                "results": [{"page": "SupplierFormDialog", "name": "x", "status": "OK"}],
                "exit": "ok",
            },
            "product_form": {
                "page_key": "product_form",
                "results": [],
                "exit": "ok",
            },
        }

        def fake_runner(cmd, **kwargs):
            page_key = cmd[cmd.index("--page") + 1]
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payloads[page_key], ensure_ascii=False),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "button_audit_report.md"
            with mock.patch.object(audit, "_prepare_disposable_database", return_value="db"):
                with mock.patch.dict("os.environ", {"SQE_DB_PATH": "db"}, clear=False):
                    exit_code = audit.run_orchestrator(
                        page_keys=("supplier_form", "product_form"),
                        report_path=report_path,
                        subprocess_runner=fake_runner,
                    )
            self.assertEqual(exit_code, 0)
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("測試按鍵總數: 1", text)

    def test_orchestrator_marks_seh_as_failure(self) -> None:
        def fake_runner(cmd, **kwargs):
            return SimpleNamespace(returncode=-1073741819, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "button_audit_report.md"
            with mock.patch.object(audit, "_prepare_disposable_database", return_value="db"):
                with mock.patch.dict("os.environ", {"SQE_DB_PATH": "db"}, clear=False):
                    exit_code = audit.run_orchestrator(
                        page_keys=("main_window",),
                        report_path=report_path,
                        subprocess_runner=fake_runner,
                    )
            self.assertEqual(exit_code, 1)
            self.assertIn("SEH 崩潰頁面", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
