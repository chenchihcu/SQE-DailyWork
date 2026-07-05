from __future__ import annotations

import importlib
import unittest
import sys
from types import ModuleType
from unittest.mock import patch

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QTableWidgetItem

import services.event._anomaly_service as _anomaly_service_mod
import services.event._visit_service as _visit_service_mod


class AnomalyCategoryDropdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls._app is not None:
            cls._app.quit()

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
        self.NewVisitDialog = self.widget_module.NewVisitDialog
        self.category_options = self.widget_module.ANOMALY_CATEGORY_OPTIONS

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
            # Sub-module patches for methods called through _visit_service directly
            patch.object(_visit_service_mod, "get_visit_detail", return_value=None),
            patch.object(_visit_service_mod, "create_visit", return_value=None),
            patch.object(_visit_service_mod, "update_visit", return_value=None),
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

    def test_category_dropdown_is_editable_and_has_default_options(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)

        self.assertIsInstance(dialog.category_input, QComboBox)
        self.assertTrue(dialog.category_input.isEditable())
        options = [
            dialog.category_input.itemText(i) for i in range(dialog.category_input.count())
        ]
        self.assertEqual(self.category_options, options)

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
        self.assertTrue(hasattr(dialog, "root_cause_display"))
        self.assertEqual("其他", dialog.root_cause_display.text())

    def test_submit_payload_uses_dropdown_or_custom_category_text(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        for expected in ("外觀不良", "客製分類-XYZ"):
            captured: dict = {}

            def _fake_create(payload: dict, _captured: dict = captured) -> dict:
                _captured.update(payload)
                return {"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"}

            with self.subTest(category=expected):
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
                    dialog.category_input.setCurrentText(expected)
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

    def test_anomaly_dialog_prefills_blank_fields_from_same_day_visit(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        same_day_visit = {
            "id": "visit-1",
            "visit_date": "2026-04-16",
            "supplier_id": "sup-1",
            "product_id": "prd-1",
            "product_name": "產品一號",
            "product_stage": "試產",
            "work_order_no": "WO-200",
            "production_qty": 200,
        }

        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ), patch.object(
            self.widget_module.event_service,
            "get_latest_visit_for_supplier_on_date",
            return_value=same_day_visit,
        ), patch.object(
            _anomaly_service_mod,
            "get_latest_visit_for_supplier_on_date",
            return_value=same_day_visit,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            dialog.date_edit.setDate(QDate(2026, 4, 16))
            self._select_supplier(dialog)

        self.assertEqual("prd-1", dialog.product_combo.currentData())
        self.assertEqual("試產", dialog.product_stage_combo.currentText())
        self.assertEqual("WO-200", dialog.outsource_work_order_input.text())
        self.assertEqual("200", dialog.batch_qty_input.text())
        self.assertEqual(
            "已沿用 2026-04-16 訪廠資料：品名、工單、數量",
            dialog._same_day_visit_hint_label.text(),
        )
        self.assertFalse(dialog._same_day_visit_hint_label.isHidden())

    def test_anomaly_dialog_same_day_prefill_does_not_override_manual_values(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "量產",
            },
            {
                "id": "prd-2",
                "product_code": "P-002",
                "product_name": "產品二號",
                "product_stage": "試產",
            },
        ]

        def _same_day_visit(_supplier_id: str, visit_date: str) -> dict:
            return {
                "id": f"visit-{visit_date}",
                "visit_date": visit_date,
                "supplier_id": "sup-1",
                "product_id": "prd-1",
                "product_name": "產品一號",
                "product_stage": "量產",
                "work_order_no": f"WO-{visit_date}",
                "production_qty": 100,
            }

        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ), patch.object(
            self.widget_module.event_service,
            "get_latest_visit_for_supplier_on_date",
            side_effect=_same_day_visit,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            dialog.date_edit.setDate(QDate(2026, 4, 16))
            self._select_supplier(dialog)
            dialog.product_combo.setCurrentIndex(dialog.product_combo.findData("prd-2"))
            dialog.outsource_work_order_input.setText("WO-MANUAL")
            dialog.batch_qty_input.setText("333")

            dialog.date_edit.setDate(QDate(2026, 4, 17))

        self.assertEqual("prd-2", dialog.product_combo.currentData())
        self.assertEqual("試產", dialog.product_stage_combo.currentText())
        self.assertEqual("WO-MANUAL", dialog.outsource_work_order_input.text())
        self.assertEqual("333", dialog.batch_qty_input.text())

    def test_anomaly_edit_mode_does_not_trigger_same_day_prefill(self) -> None:
        with patch.object(
            self.widget_module.event_service,
            "get_latest_visit_for_supplier_on_date",
            return_value={
                "id": "visit-1",
                "visit_date": "2026-04-16",
                "supplier_id": "sup-1",
                "product_id": "prd-1",
                "work_order_no": "WO-200",
                "production_qty": 200,
            },
        ) as latest_visit:
            dialog = self.NewAnomalyDialog(
                anomaly_id="anomaly-1",
                initial_data={
                    "anomaly_no": "20260416001",
                    "anomaly_date": "2026-04-16",
                    "supplier_id": "sup-1",
                    "supplier_name": "供應商A",
                    "product_id": "",
                    "outsource_work_order": "",
                    "batch_qty": 0,
                },
            )
            self.addCleanup(dialog.close)

        latest_visit.assert_not_called()

    def test_visit_dialog_product_stage_defaults_and_submit_payload(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-2",
                "product_code": "V-001",
                "product_name": "訪廠產品",
                "product_stage": "試產",
            }
        ]

        def _fake_create_visit(payload: dict) -> str:
            captured.update(payload)
            return "visit-001"

        with patch.object(
            self.widget_module.event_service,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            _visit_service_mod,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewVisitDialog()
            self.addCleanup(dialog.close)
            self.assertEqual("量產", dialog.product_stage_combo.currentText())
            self.assertFalse(dialog.product_stage_combo.isEnabled())
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-2")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            self.assertEqual("試產", dialog.product_stage_combo.currentText())
            self.assertFalse(dialog.product_stage_combo.isEnabled())
            dialog._on_submit()

        self.assertEqual("prd-2", captured.get("product_id"))
        self.assertNotIn("product_stage", captured)
        self.assertEqual("prd-2", captured["product_sections"][0]["product_id"])
        self.assertEqual("試產", captured["product_sections"][0]["product_stage"])
        self.assertFalse(captured.get("tech_transfer", True))
        self.assertFalse(captured.get("tech_transfer_doc", True))
        self.assertFalse(captured.get("carrier_requirement", True))
        self.assertFalse(captured.get("dispensing_process", True))
        self.assertFalse(captured.get("functional_test", True))
        self.assertFalse(captured.get("packaging_requirement", True))

    def test_visit_dialog_focus_defect_note_opens_shared_defect_tab(self) -> None:
        dialog = self.NewVisitDialog(focus_defect_note=True)
        self.addCleanup(dialog.close)

        self.assertEqual("缺失紀錄", dialog.tabs.tabText(dialog.tabs.currentIndex()))
        self.assertEqual(1, dialog.visit_defect_table.rowCount())
        self.assertEqual(0, dialog.visit_defect_table.currentColumn())

    def test_visit_dialog_submits_visit_level_and_product_defect_notes(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            },
            {
                "id": "prd-2",
                "product_code": "P-002",
                "product_name": "產品二號",
                "product_stage": "量產",
            },
        ]

        def _fake_create_visit(payload: dict) -> str:
            captured.update(payload)
            return "visit-001"

        with patch.object(
            self.widget_module.event_service,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            _visit_service_mod,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewVisitDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            dialog.time_slot_input.setText("上午")
            dialog.work_order_input.setText("WO-A")
            dialog.primary_defect_table.add_empty_note()
            dialog.primary_defect_table.setItem(0, 0, QTableWidgetItem("材料未全檢"))
            dialog.primary_defect_table.setItem(0, 1, QTableWidgetItem("已建立 SOP"))
            dialog.visit_defect_table.add_empty_note()
            dialog.visit_defect_table.setItem(0, 0, QTableWidgetItem("共通現場問題"))

            extra = dialog._add_extra_product_section()
            extra.product_combo.setCurrentIndex(extra.product_combo.findData("prd-2"))
            extra.time_slot_input.setText("下午")
            extra.defect_table.add_empty_note()
            extra.defect_table.setItem(0, 0, QTableWidgetItem("規格書未收到"))
            extra.defect_table.setItem(0, 2, QTableWidgetItem("下次補看"))
            dialog._on_submit()

        self.assertEqual("共通現場問題", captured["defect_notes"][0]["defect_desc"])
        self.assertEqual(2, len(captured["product_sections"]))
        self.assertEqual("prd-1", captured["product_sections"][0]["product_id"])
        self.assertEqual("上午", captured["product_sections"][0]["time_slot"])
        self.assertEqual("材料未全檢", captured["product_sections"][0]["defect_notes"][0]["defect_desc"])
        self.assertEqual("prd-2", captured["product_sections"][1]["product_id"])
        self.assertEqual("下午", captured["product_sections"][1]["time_slot"])
        self.assertEqual("", captured["product_sections"][1]["defect_notes"][0]["improvement_desc"])

    def test_visit_dialog_item_yes_auto_checks_tech_transfer(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-2",
                "product_code": "V-001",
                "product_name": "訪廠產品",
                "product_stage": "試產",
            }
        ]

        def _fake_create_visit(payload: dict) -> str:
            captured.update(payload)
            return "visit-001"

        with patch.object(
            self.widget_module.event_service,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            _visit_service_mod,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewVisitDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-2")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            functional_group = dialog._tech_transfer_groups["functional_test"]
            yes_button = functional_group.button(1)
            self.assertIsNotNone(yes_button)
            assert yes_button is not None
            yes_button.setChecked(True)
            self.assertTrue(dialog.tech_transfer_check.isChecked())
            dialog._on_submit()

        self.assertTrue(captured.get("tech_transfer"))
        self.assertTrue(captured.get("functional_test"))

    def test_uncheck_tech_transfer_resets_all_items_to_no(self) -> None:
        dialog = self.NewVisitDialog()
        self.addCleanup(dialog.close)
        self._select_supplier(dialog)

        for field_key in ("tech_transfer_doc", "carrier_requirement"):
            group = dialog._tech_transfer_groups[field_key]
            yes_button = group.button(1)
            self.assertIsNotNone(yes_button)
            assert yes_button is not None
            yes_button.setChecked(True)

        self.assertTrue(dialog.tech_transfer_check.isChecked())
        dialog.tech_transfer_check.setChecked(False)
        self.assertFalse(dialog.tech_transfer_check.isChecked())
        for key, _label in self.widget_module.VISIT_TECH_TRANSFER_ITEMS:
            self.assertNotEqual(
                self.widget_module.TECH_TRANSFER_STATE_YES,
                dialog._get_tech_transfer_state(key),
            )

    def test_visit_dialog_edit_mode_applies_item_flags(self) -> None:
        dialog = self.NewVisitDialog(
            visit_id="visit-1",
            initial_data={
                "visit_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "tech_transfer": False,
                "functional_test": True,
                "carrier_requirement": False,
                "tech_transfer_doc": False,
                "dispensing_process": False,
                "packaging_requirement": False,
            },
        )
        self.addCleanup(dialog.close)

        self.assertTrue(dialog.tech_transfer_check.isChecked())
        self.assertEqual(
            self.widget_module.TECH_TRANSFER_STATE_YES,
            dialog._get_tech_transfer_state("functional_test"),
        )
        self.assertNotEqual(
            self.widget_module.TECH_TRANSFER_STATE_YES,
            dialog._get_tech_transfer_state("carrier_requirement"),
        )

    def test_visit_dialog_tech_transfer_cards_use_right_side_dot_indicator_style(self) -> None:
        dialog = self.NewVisitDialog()
        self.addCleanup(dialog.close)
        self._select_supplier(dialog)

        for field_key, _label in self.widget_module.VISIT_TECH_TRANSFER_ITEMS:
            card = dialog._tech_transfer_cards[field_key]
            self.assertEqual(Qt.LayoutDirection.RightToLeft, card.yes_radio.layoutDirection())
            self.assertEqual(Qt.LayoutDirection.RightToLeft, card.no_radio.layoutDirection())

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
            self.assertEqual("規範文件缺漏", dialog.root_cause_combo.currentText())
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
            dialog.improvement_input.setPlainText("改善完成")
            dialog.closer_input.setText("王小明")
            dialog.closed_at_input.setDate(QDate(2026, 5, 10))
            dialog._on_submit()

        close_mock.assert_called_once_with(
            "anomaly-123",
            "改善完成",
            closed_by="王小明",
            root_cause_category="規範文件缺漏",
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
            self.assertTrue(dialog.closer_input.isReadOnly())
            self.assertFalse(dialog.root_cause_combo.isEnabled())
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
        self.assertTrue(hasattr(dialog_closed, "root_cause_display"))
        self.assertEqual("規範文件缺漏", dialog_closed.root_cause_display.text())

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
            dialog_closed._on_submit()

        self.assertEqual("來料品質不良", captured.get("category"))

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
