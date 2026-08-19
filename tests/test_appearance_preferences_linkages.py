"""Unit and integration tests for AppearancePreferences business linkages."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from database.backup import prune_backups
from services.appearance_preferences_service import (
    load_application_preferences,
    save_application_preferences,
)
from services.event import _anomaly_service as anomaly_service
from services.pdf_html_helpers import _html_document
from ui.appearance_preferences import AppearancePreferences

# Ensure QApplication exists for Qt widget tests
app = QApplication.instance() or QApplication([])


class TestAppearancePreferencesLinkages(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prune_backups_keeps_newest_and_removes_excess(self):
        backup_dir = Path(self.temp_dir) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        files = []
        for i in range(10):
            p = backup_dir / f"sqe_auto_backup_{i:02d}.db"
            p.write_text(f"content {i}")
            os.utime(p, (1000 + i * 10, 1000 + i * 10))
            files.append(p)

        self.assertEqual(len(list(backup_dir.glob("*.db"))), 10)

        # Prune to keep 3 newest
        removed = prune_backups(backup_dir, max_count=3, pattern="sqe_auto_backup_*.db")
        self.assertEqual(len(removed), 7)

        remaining = sorted(f.name for f in backup_dir.glob("*.db"))
        self.assertEqual(len(remaining), 3)
        self.assertEqual(
            remaining,
            ["sqe_auto_backup_07.db", "sqe_auto_backup_08.db", "sqe_auto_backup_09.db"],
        )

    def test_prune_backups_boundary_conditions(self):
        self.assertEqual(prune_backups(self.temp_dir, 0), [])
        self.assertEqual(prune_backups(Path(self.temp_dir) / "non_existent", 5), [])

    def test_pdf_html_document_respects_density_and_disclaimer(self):
        custom_prefs = AppearancePreferences(
            pdf_font_density="compact",
            report_organization_header="品質工程測試中心",
            export_include_disclaimer=True,
        )
        with patch(
            "services.pdf_html_helpers.load_application_preferences",
            return_value=custom_prefs,
        ):
            html = _html_document("測試標題", "<p>內容</p>", "Microsoft JhengHei UI")
            self.assertIn("font-size: 8.5pt", html)
            self.assertIn("品質工程測試中心", html)
            self.assertIn("內部專用品質文件，未經授權禁止外傳", html)

    def test_pdf_html_document_standard_density(self):
        custom_prefs = AppearancePreferences(
            pdf_font_density="standard",
            report_organization_header="標準部門",
            export_include_disclaimer=False,
        )
        with patch(
            "services.pdf_html_helpers.load_application_preferences",
            return_value=custom_prefs,
        ):
            html = _html_document("測試標題", "<p>內容</p>", "Microsoft JhengHei UI")
            self.assertIn("font-size: 10pt", html)
            self.assertIn("標準部門", html)
            self.assertNotIn("內部專用品質文件，未經授權禁止外傳", html)

    def test_close_anomaly_dialog_prefills_default_closer(self):
        from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog

        custom_prefs = AppearancePreferences(default_closer_name="王大明 / SQE_LEAD")
        with patch(
            "ui.widgets.close_anomaly_dialog.load_application_preferences",
            return_value=custom_prefs,
        ), patch(
            "services.event._anomaly_service.get_anomaly_detail",
            return_value={"id": "test_id", "status": "待處理", "problem_desc": "不良描述"},
        ):
            dlg = CloseAnomalyDialog("test_id", "不良描述")
            self.assertEqual(dlg.closed_by_input.text(), "王大明 / SQE_LEAD")


    def test_close_anomaly_service_passes_closed_by(self):
        with patch("database.connection.get_connection") as mock_conn, patch(
            "database.repository.close_anomaly"
        ) as mock_repo_close, patch(
            "database.repository.get_anomaly_detail",
            return_value={"id": "A1", "status": "已結案"},
        ), patch(
            "services.event._anomaly_service._write_snapshot_with_warning",
            return_value=[],
        ):
            res = anomaly_service.close_anomaly(
                "A1", "改善措施完畢", closed_by="張工程師", closed_at="2026-08-16"
            )
            self.assertEqual(res["anomaly_id"], "A1")
            mock_repo_close.assert_called_once()
            _, kwargs = mock_repo_close.call_args
            self.assertEqual(kwargs.get("closed_by"), "張工程師")
            self.assertEqual(kwargs.get("closed_at"), "2026-08-16")

    def test_confirm_and_delete_skips_modal_when_disabled(self):
        from ui.widgets.event_actions import _confirm_and_delete

        custom_prefs = AppearancePreferences(confirm_on_delete=False)
        deleted = []
        refreshed = []

        with patch(
            "services.appearance_preferences_service.load_application_preferences",
            return_value=custom_prefs,
        ), patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            _confirm_and_delete(
                None,
                "異常",
                "20260816001",
                lambda: deleted.append(1),
                lambda: refreshed.append(1),
            )
            self.assertEqual(len(deleted), 1)
            self.assertEqual(len(refreshed), 1)
            mock_info.assert_called_once()

    def test_defect_list_apply_sort_modes(self):
        from ui.widgets.defect_list_widget import EventListWidget

        widget = EventListWidget.__new__(EventListWidget)
        widget._all_rows = [
            {"ref_no": "20260810001", "event_date": "2026-08-10", "status": "已結案"},
            {"ref_no": "20260816001", "event_date": "2026-08-16", "status": "待處理"},
            {"ref_no": "20260812001", "event_date": "2026-08-12", "status": "待處理"},
        ]


        # 1. Date desc
        with patch(
            "services.appearance_preferences_service.load_application_preferences",
            return_value=AppearancePreferences(default_list_sort_field="date_desc"),
        ):
            widget._sort_mode = None
            widget._apply_sort()
            dates = [r["event_date"] for r in widget._all_rows]
            self.assertEqual(dates, ["2026-08-16", "2026-08-12", "2026-08-10"])

        # 2. Status first (open first)
        with patch(
            "services.appearance_preferences_service.load_application_preferences",
            return_value=AppearancePreferences(default_list_sort_field="status_first"),
        ):
            widget._sort_mode = None
            widget._apply_sort()
            statuses = [r["status"] for r in widget._all_rows]
            self.assertEqual(statuses[:2], ["待處理", "待處理"])
            self.assertEqual(statuses[2], "已結案")


if __name__ == "__main__":
    unittest.main()

