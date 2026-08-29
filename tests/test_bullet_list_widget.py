from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QTextEdit
from ui.widgets.bullet_list_widget import BulletListWidget, BulletListItemRow
from ui.widgets.defect_form_widgets import set_text_edit_visible_rows
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.new_visit_dialog import NewVisitDialog


class BulletListWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_bullet_list_widget_expansion_and_items(self) -> None:
        widget = BulletListWidget()
        self.assertEqual(len(widget._rows), 1)

        # 載入 7 筆條目（模擬使用者回報之場景）
        items = [
            "第一批進板取爽板開立鋼板",
            "修改功能: PIN開孔加長或加寬",
            "塑料影響部分已修改載具",
            "點膠作業標準書更新",
            "SMT鋼網開孔位置確認",
            "功能測試電訊阻抗量測異常",
            "包裝出貨前外觀二次檢驗",
        ]
        widget.set_items(items)
        self.assertEqual(len(widget._rows), 7)
        self.assertEqual(widget.get_items(), items)

        # 確保總高度並未被鎖死在 130px，且 sizeHint 能隨條目數自然生長
        hint_height = widget.sizeHint().height()
        self.assertGreater(hint_height, 180)

        # 確保每一列輸入框均有至少 28px 之最小高度保護
        for row in widget._rows:
            self.assertGreaterEqual(row.line_edit.minimumHeight(), 28)

    def test_bullet_list_widget_readonly_mode(self) -> None:
        widget = BulletListWidget()
        items = [f"條目 {i}" for i in range(1, 8)]
        widget.set_items(items)
        widget.setReadOnly(True)

        self.assertTrue(widget.isReadOnly())
        self.assertFalse(widget.btn_add.isVisible())

        for row in widget._rows:
            self.assertTrue(row.line_edit.isReadOnly())
            self.assertFalse(row.btn_delete.isVisible())

        # 測試在唯讀模式下重新載入文字，新建條目必須自動繼承唯讀狀態
        widget.set_formatted_text("1. 新條目A\n2. 新條目B\n3. 新條目C")
        self.assertEqual(len(widget._rows), 3)
        for row in widget._rows:
            self.assertTrue(row.line_edit.isReadOnly())
            self.assertFalse(row.btn_delete.isVisible())

    @patch("services.event_service.list_active_suppliers", return_value=[])
    def test_new_anomaly_dialog_multiline_items_not_squished(self, _mock_suppliers) -> None:
        sample_problem = (
            "1. 下批進板取爽板開立鋼板(待追蹤)\n"
            "2. 修改功能: PIN開孔加長或加寬(待追蹤)\n"
            "3. 塑料影響部分已修改載具(完成)\n"
            "4. 點膠作業標準書更新\n"
            "5. SMT鋼網開孔位置確認\n"
            "6. 功能測試電訊阻抗量測異常\n"
            "7. 包裝出貨前外觀二次檢驗"
        )
        initial_data = {
            "anomaly_no": "20260507001",
            "problem_desc": sample_problem,
            "pending_items": "1. 追蹤項目A\n2. 追蹤項目B",
        }

        dialog = NewAnomalyDialog(
            anomaly_id="test-anomaly-1",
            initial_data=initial_data,
            read_only=True,
        )

        # 驗證 problem_input 沒有被 setFixedHeight 鎖定在 130px
        self.assertEqual(dialog.problem_input.maximumHeight(), 16777215)
        self.assertEqual(len(dialog.problem_input._rows), 7)

        # 驗證 pending_items_input 同樣沒有被鎖死在 86px
        self.assertEqual(dialog.pending_items_input.maximumHeight(), 16777215)
        self.assertEqual(len(dialog.pending_items_input._rows), 2)

        # 驗證所有條目文字皆正確載入
        loaded_items = dialog.problem_input.get_items()
        self.assertEqual(len(loaded_items), 7)
        self.assertIn("下批進板取爽板開立鋼板(待追蹤)", loaded_items[0])

    def test_new_visit_dialog_summary_round_trip(self) -> None:
        legacy_summary = "上午討論鋼網開孔\n下午確認 SPI 參數"
        dialog = NewVisitDialog(
            visit_id="visit-test-1",
            initial_data={"summary": legacy_summary},
            read_only=True,
        )
        self.assertEqual(len(dialog.summary_input.get_items()), 2)
        self.assertEqual(
            dialog.summary_input.get_formatted_text(),
            "1. 上午討論鋼網開孔\n2. 下午確認 SPI 參數",
        )

    def test_set_text_edit_visible_rows_safety(self) -> None:
        # 對 QTextEdit 設定行高：正常運作
        text_edit = QTextEdit()
        set_text_edit_visible_rows(text_edit, 5)
        self.assertLess(text_edit.maximumHeight(), 16777215)

        # 對 BulletListWidget 呼叫：不應再錯誤施加固定高度
        bullet_list = BulletListWidget()
        set_text_edit_visible_rows(bullet_list, 5)
        self.assertEqual(bullet_list.maximumHeight(), 16777215)


if __name__ == "__main__":
    unittest.main()
