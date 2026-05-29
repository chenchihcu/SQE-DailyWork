from __future__ import annotations

import unittest

from ui.popup_i18n import localize_exception, localize_popup_message


class PopupI18nTests(unittest.TestCase):
    def test_fixed_message_translation(self) -> None:
        self.assertEqual(localize_popup_message("Supplier is required"), "供應商為必填")
        self.assertEqual(localize_popup_message("Visit not found"), "找不到訪廠紀錄")

    def test_dynamic_referenced_message_translation(self) -> None:
        self.assertEqual(
            localize_popup_message("Supplier is referenced by products, anomalies"),
            "供應商資料已被品名、異常資料引用",
        )
        self.assertEqual(
            localize_popup_message("Product is referenced by visits"),
            "品名資料已被訪廠紀錄引用",
        )

    def test_export_message_translation(self) -> None:
        self.assertEqual(
            localize_popup_message("Exported to C:\\temp\\report.xlsx"),
            "已匯出至：C:\\temp\\report.xlsx",
        )
        self.assertEqual(
            localize_popup_message("Export failed: Supplier not found"),
            "匯出失敗：找不到供應商資料",
        )

    def test_prefixed_detail_translation(self) -> None:
        self.assertEqual(
            localize_popup_message("建立供應商失敗：Supplier name is required"),
            "建立供應商失敗：供應商名稱為必填",
        )

    def test_unknown_message_fallback(self) -> None:
        self.assertEqual(localize_popup_message("Third-party error message"), "Third-party error message")

    def test_localize_exception(self) -> None:
        exc = ValueError("Product does not belong to selected supplier")
        self.assertEqual(localize_exception(exc), "產品不屬於所選供應商")


if __name__ == "__main__":
    unittest.main()
