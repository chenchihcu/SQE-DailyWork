from __future__ import annotations

import importlib
import unittest
import sys
from types import ModuleType
from unittest.mock import patch

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QScrollArea,
    QTabWidget,
)

import services.event._anomaly_service as _anomaly_service_mod
from services.anomaly_trace_contract import ANOMALY_SOURCE_VISIT_AUDIT


class AnomalyCategoryDropdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def setUp(self) -> None:
        self._pandas_patch = patch.dict(sys.modules, {"pandas": ModuleType("pandas")})
        self._pandas_patch.start()
        self.addCleanup(self._pandas_patch.stop)

        # Re-import the widget module fresh, but DO NOT pop ``services.event_service``.
        # The supplier/product combos resolve the service through a *call-time*
        # ``import services.event_service`` inside
        # ``common_widgets.SupplierProductFormMixin`` (_load_suppliers /
        # _on_supplier_changed), whereas the patches below target the module-level
        # ``event_service`` reference held by ``defect_form_widget``. Popping
        # ``services.event_service`` from ``sys.modules`` desyncs those two references
        # once earlier suite modules have pre-populated the import state: the mocks land
        # on one module object while the dialog resolves a different one, so supplier
        # loading hits the real service/DB and ``supplier_combo`` comes up empty
        # (``findData`` returns -1). Keep the canonical module in ``sys.modules`` and pin
        # the widget's reference to it so the patch target is exactly the object the
        # dialog resolves at call time. This keeps the suite order-independent.
        sys.modules.pop("ui.widgets.defect_form_shim", None)
        self.widget_module = importlib.import_module("ui.widgets.defect_form_shim")
        self.addCleanup(lambda: sys.modules.pop("ui.widgets.defect_form_shim", None))

        import services.event_service as canonical_event_service

        self.widget_module.event_service = canonical_event_service
        self.assertIs(
            self.widget_module.event_service,
            sys.modules["services.event_service"],
            "event_service patch target must be the module dialogs resolve at call time;"
            " do not pop services.event_service from sys.modules here.",
        )

        self.NewAnomalyDialog = self.widget_module.NewAnomalyDialog
        self.category_options = self.widget_module.get_anomaly_category_options()

        self._suppliers = [{"id": "sup-1", "supplier_name": "供應商A", "is_active": True}]

        self._patches = [
            patch.object(
                self.widget_module.event_service,
                "preview_anomaly_no",
                side_effect=lambda d: d.replace("-", "") + "001" if d else "20260702001",
            ),
            patch.object(
                _anomaly_service_mod,
                "preview_anomaly_no",
                side_effect=lambda d: d.replace("-", "") + "001" if d else "20260702001",
            ),
            patch.object(
                self.widget_module.event_service,
                "list_active_suppliers",
                return_value=self._suppliers,
            ),
            patch.object(
                self.widget_module.event_service,
                "list_suppliers",
                return_value=self._suppliers,
            ),
            patch.object(
                self.widget_module.event_service,
                "list_active_products_for_supplier",
                return_value=[],
            ),
            patch.object(
                self.widget_module.event_service,
                "get_latest_visit_for_supplier_on_date",
                return_value=None,
            ),
            patch.object(
                _anomaly_service_mod,
                "get_latest_visit_for_supplier_on_date",
                return_value=None,
            ),
            # Sub-module patches for methods called through _anomaly_service directly
            patch.object(_anomaly_service_mod, "get_anomaly_detail", return_value=None),
            patch.object(_anomaly_service_mod, "close_anomaly", return_value=None),
            patch.object(_anomaly_service_mod, "update_anomaly_closed_at", return_value=None),
            patch.object(_anomaly_service_mod, "update_anomaly", return_value=None),
            patch.object(_anomaly_service_mod, "create_anomaly_with_visit_link", return_value=None),
            patch.object(self.widget_module.QMessageBox, "information"),
            patch.object(self.widget_module.QMessageBox, "warning"),
            patch.object(self.widget_module.QMessageBox, "critical"),
            patch.object(
                self.widget_module.QMessageBox,
                "question",
                return_value=self.widget_module.QMessageBox.StandardButton.Yes,
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _select_supplier(self, dialog) -> None:
        idx = dialog.supplier_combo.findData("sup-1")
        self.assertGreaterEqual(idx, 0)
        dialog.supplier_combo.setCurrentIndex(idx)

    def _select_anomaly_source(self, dialog, source: str = ANOMALY_SOURCE_VISIT_AUDIT) -> None:
        idx = dialog.anomaly_source_combo.findText(source)
        self.assertGreaterEqual(idx, 0, msg=f"missing anomaly source option: {source}")
        dialog.anomaly_source_combo.setCurrentIndex(idx)

    def test_category_dropdown_is_strict_and_has_default_options(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)

        self.assertIsInstance(dialog.category_input, QComboBox)
        self.assertFalse(dialog.category_input.isEditable())
        options = [
            dialog.category_input.itemText(i) for i in range(dialog.category_input.count())
        ]
        self.assertEqual(self.category_options, options)

    def test_anomaly_form_is_single_scroll_page_without_tab_host(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)

        self.assertIsInstance(dialog.form_scroll, QScrollArea)
        self.assertTrue(dialog.form_scroll.widgetResizable())
        self.assertEqual([], dialog.findChildren(QTabWidget))
        section_titles = {
            label.text()
            for label in dialog.form_scroll.findChildren(QLabel)
            if label.property("role") == "sectionTitle"
        }
        self.assertEqual(
            {"📋 基本資訊", "🔍 問題描述", "📷 現場照片"},
            section_titles,
        )

    def test_quality_report_requirement_must_be_selected_before_submit(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)
        self.assertEqual(-1, dialog.quality_report_required_group.checkedId())

        self.widget_module.QMessageBox.warning.reset_mock()
        _anomaly_service_mod.create_anomaly_with_visit_link.reset_mock()
        dialog._on_submit()

        self.widget_module.QMessageBox.warning.assert_called_once()
        self.assertIn(
            "品質異常單要求",
            self.widget_module.QMessageBox.warning.call_args.args[2],
        )
        _anomaly_service_mod.create_anomaly_with_visit_link.assert_not_called()

    def test_quality_report_requirement_rehydrates_yes_no_and_legacy_unset(self) -> None:
        for stored_value, expected_id in ((True, 1), (False, 0), (None, -1)):
            with self.subTest(stored_value=stored_value):
                dialog = self.NewAnomalyDialog(
                    anomaly_id="anomaly-quality",
                    initial_data={
                        "anomaly_no": "20260702002",
                        "anomaly_date": "2026-07-02",
                        "supplier_id": "sup-1",
                        "supplier_name": "供應商A",
                        "quality_report_required": stored_value,
                    },
                )
                self.addCleanup(dialog.close)
                self.assertEqual(
                    expected_id, dialog.quality_report_required_group.checkedId()
                )

    def test_category_dropdown_uses_root_cause_pareto_taxonomy(self) -> None:
        self.assertEqual(
            [
                "",
                "製程參數失控",
                "規範文件缺漏",
                "檢驗把關失靈",
                "設計匹配不良",
                "設備能力不符",
                "包裝防護不足",
                "來料品質不良",
                "標準作業不落實",
                "供應商改善不力",
                "其他",
            ],
            self.category_options,
        )

    def test_edit_mode_keeps_custom_category_text(self) -> None:
        dialog = self.NewAnomalyDialog(
            anomaly_id="anomaly-1",
            initial_data={
                "anomaly_no": "2026年04月16日 -SN 001",
                "anomaly_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "category": "客製異常A",
            },
        )
        self.addCleanup(dialog.close)

        self.assertEqual("客製異常A", dialog.category_input.currentText())

    def test_edit_mode_loads_raw_category_not_resolved_root_cause(self) -> None:
        # 已結案事件 detail 的 category 是解析值(root_cause 優先);編輯模式必須
        # 載入 category_raw,否則存檔會把根因值無聲覆寫進 category 欄位。
        dialog = self.NewAnomalyDialog(
            anomaly_id="anomaly-raw",
            initial_data={
                "anomaly_no": "20260416001",
                "anomaly_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "status": "已結案",
                "category": "其他",
                "category_raw": "製程參數失控",
            },
        )
        self.addCleanup(dialog.close)

        self.assertEqual("製程參數失控", dialog.category_input.currentText())

    def test_read_only_mode_shows_resolved_category_for_closed_anomaly(self) -> None:
        # 唯讀預覽依新規則顯示原始異常類別，並並列原因分類（結案唯讀項目）
        dialog = self.NewAnomalyDialog(
            anomaly_id="anomaly-ro",
            initial_data={
                "anomaly_no": "20260416001",
                "anomaly_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "status": "已結案",
                "category": "其他",
                "category_raw": "製程參數失控",
                "root_cause_category": "其他",
            },
            read_only=True,
        )
        self.addCleanup(dialog.close)

        self.assertEqual("製程參數失控", dialog.category_input.currentText())

    def test_submit_payload_rejects_custom_category_text(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            dialog.problem_input.setPlainText("測試問題描述")
            dialog._populate_category_combo("客製分類-XYZ")
            self._select_anomaly_source(dialog)
            dialog.quality_report_no_radio.setChecked(True)
            _anomaly_service_mod.create_anomaly_with_visit_link.reset_mock()
            dialog._on_submit()
        _anomaly_service_mod.create_anomaly_with_visit_link.assert_not_called()

    def test_submit_payload_uses_valid_category_text(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        captured: dict = {}

        def _fake_create(payload: dict, _captured: dict = captured) -> dict:
            _captured.update(payload)
            return {"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"}

        with patch.object(
            self.widget_module.event_service,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            _anomaly_service_mod,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            dialog.problem_input.setPlainText("測試問題描述")
            idx = dialog.category_input.findText("外觀不良")
            if idx < 0:
                dialog._populate_category_combo("製程參數失控")
                idx = dialog.category_input.findText("製程參數失控")
            self.assertGreaterEqual(idx, 0)
            dialog.category_input.setCurrentIndex(idx)
            expected = dialog.category_input.currentText()
            self._select_anomaly_source(dialog)
            dialog.quality_report_no_radio.setChecked(True)
            dialog._on_submit()

        self.assertEqual(expected, captured.get("category"))

    def test_anomaly_dialog_product_stage_defaults_to_mass_production(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)
        self.assertEqual("量產", dialog.product_stage_combo.currentText())
        self.assertFalse(dialog.product_stage_combo.isEnabled())

    def test_submit_payload_uses_product_and_keeps_stage_read_only_for_anomaly(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]

        def _fake_create(payload: dict) -> dict:
            captured.update(payload)
            return {"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"}

        with patch.object(
            self.widget_module.event_service,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            _anomaly_service_mod,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            self.assertEqual("試產", dialog.product_stage_combo.currentText())
            self.assertFalse(dialog.product_stage_combo.isEnabled())
            dialog.problem_input.setPlainText("測試問題描述")
            self._select_anomaly_source(dialog)
            dialog.quality_report_yes_radio.setChecked(True)
            dialog._on_submit()

        self.assertEqual("prd-1", captured.get("product_id"))
        self.assertNotIn("product_stage", captured)

    def test_select_product_autofills_stage_for_anomaly_dialog(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            self.assertEqual("試產", dialog.product_stage_combo.currentText())
            self.assertTrue(dialog.save_button.isEnabled())

    def test_anomaly_dialog_blocks_submit_when_supplier_has_no_products(self) -> None:
        create_spy = patch.object(
            self.widget_module.event_service,
            "create_anomaly_with_visit_link",
            return_value={"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"},
        )
        with create_spy as fake_create:
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            self.assertFalse(dialog.save_button.isEnabled())
            dialog.problem_input.setPlainText("測試問題描述")
            dialog._on_submit()
        fake_create.assert_not_called()

    def test_close_anomaly_dialog_preselects_original_category(self) -> None:
        from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
        with patch.object(
            self.widget_module.event_service,
            "get_anomaly_detail",
            return_value={"category": "規範文件缺漏", "anomaly_date": "2026-04-16"},
        ), patch.object(
            _anomaly_service_mod,
            "get_anomaly_detail",
            return_value={"category": "規範文件缺漏", "anomaly_date": "2026-04-16"},
        ) as mock_get:
            dialog = CloseAnomalyDialog("anomaly-123", "Some problem description")
            self.addCleanup(dialog.close)
            mock_get.assert_called_once_with("anomaly-123")
            self.assertEqual("2026-04-16", dialog.closed_at_input.minimumDate().toString("yyyy-MM-dd"))

    def test_close_anomaly_dialog_submits_user_selected_closed_date(self) -> None:
        from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
        with (
            patch.object(
                self.widget_module.event_service,
                "get_anomaly_detail",
                return_value={"category": "規範文件缺漏", "anomaly_date": "2026-04-16"},
            ),
            patch.object(
                _anomaly_service_mod,
                "get_anomaly_detail",
                return_value={"category": "規範文件缺漏", "anomaly_date": "2026-04-16"},
            ),
            patch.object(self.widget_module.event_service, "close_anomaly"),
            patch.object(_anomaly_service_mod, "close_anomaly") as close_mock,
        ):
            dialog = CloseAnomalyDialog("anomaly-123", "Some problem description")
            self.addCleanup(dialog.close)
            dialog.improvement_input.set_formatted_text("改善完成")
            dialog.closed_at_input.setDate(QDate(2026, 5, 10))
            dialog._on_submit()

        close_mock.assert_called_once_with(
            "anomaly-123",
            "1. 改善完成",
            closed_at="2026-05-10",
        )

    def test_close_anomaly_dialog_adjustment_mode_updates_only_closed_date(self) -> None:
        from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
        with (
            patch.object(
                self.widget_module.event_service,
                "get_anomaly_detail",
                return_value={
                    "category": "尺寸異常",
                    "anomaly_date": "2026-04-16",
                    "status": "已結案",
                    "improvement_desc": "已改善",
                    "closed_by": "王小明",
                    "root_cause_category": "規範文件缺漏",
                    "closed_at": "2026-05-10",
                },
            ),
            patch.object(
                _anomaly_service_mod,
                "get_anomaly_detail",
                return_value={
                    "category": "尺寸異常",
                    "anomaly_date": "2026-04-16",
                    "status": "已結案",
                    "improvement_desc": "已改善",
                    "closed_by": "王小明",
                    "root_cause_category": "規範文件缺漏",
                    "closed_at": "2026-05-10",
                },
            ),
            patch.object(self.widget_module.event_service, "close_anomaly") as close_mock,
            patch.object(_anomaly_service_mod, "close_anomaly") as close_mock_2,
            patch.object(
                self.widget_module.event_service,
                "update_anomaly_closed_at",
            ) as update_closed_at,
            patch.object(
                _anomaly_service_mod,
                "update_anomaly_closed_at",
            ) as update_closed_at_2,
        ):
            dialog = CloseAnomalyDialog(
                "anomaly-123",
                "Some problem description",
                date_adjustment_only=True,
            )
            self.addCleanup(dialog.close)
            self.assertTrue(dialog.improvement_input.isReadOnly())
            self.assertEqual("2026-05-10", dialog.closed_at_input.date().toString("yyyy-MM-dd"))

            dialog.closed_at_input.setDate(QDate(2026, 5, 12))
            dialog._on_submit()

        close_mock_2.assert_not_called()
        update_closed_at_2.assert_called_once_with(
            "anomaly-123",
            closed_at="2026-05-12",
        )

    def test_closed_anomaly_edit_uses_saved_category_not_root_cause(self) -> None:
        dialog_closed = self.NewAnomalyDialog(
            anomaly_id="anomaly-456",
            initial_data={
                "anomaly_no": "20260702002",
                "anomaly_date": "2026-07-02",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "product_id": "prd-1",
                "product_name": "產品一號",
                "status": "已結案",
                "category": "尺寸異常",
                "root_cause_category": "規範文件缺漏",
            }
        )
        self.addCleanup(dialog_closed.close)
        self.assertEqual("尺寸異常", dialog_closed.category_input.currentText())

        captured: dict = {}

        def _fake_update(_anomaly_id: str, payload: dict) -> None:
            captured.update(payload)

        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "量產",
            }
        ]
        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ), patch.object(
            self.widget_module.event_service,
            "update_anomaly",
            side_effect=_fake_update,
        ), patch.object(
            _anomaly_service_mod,
            "update_anomaly",
            side_effect=_fake_update,
        ):
            dialog_closed.category_input.setCurrentText("來料品質不良")
            dialog_closed.problem_input.setPlainText("測試問題描述")
            dialog_closed.quality_report_no_radio.setChecked(True)
            dialog_closed._on_submit()

        self.assertEqual("來料品質不良", captured.get("category"))
        self.assertIs(False, captured.get("quality_report_required"))

        reopened = self.NewAnomalyDialog(
            anomaly_id="anomaly-456",
            initial_data={
                "anomaly_no": "20260702002",
                "anomaly_date": "2026-07-02",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "product_id": "prd-1",
                "product_name": "產品一號",
                "status": "已結案",
                "category": captured.get("category"),
                "root_cause_category": "規範文件缺漏",
            }
        )
        self.addCleanup(reopened.close)
        self.assertEqual("來料品質不良", reopened.category_input.currentText())

        dialog_open = self.NewAnomalyDialog(
            anomaly_id="anomaly-789",
            initial_data={
                "anomaly_no": "20260702003",
                "anomaly_date": "2026-07-02",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "product_id": "prd-1",
                "product_name": "產品一號",
                "status": "待處理",
                "category": "製程參數失控",
                "root_cause_category": "規範文件缺漏",
            }
        )
        self.addCleanup(dialog_open.close)
        self.assertEqual("製程參數失控", dialog_open.category_input.currentText())


if __name__ == "__main__":
    unittest.main()
