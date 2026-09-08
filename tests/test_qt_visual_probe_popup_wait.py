from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QDate

from scripts.qt_visual_probe import (
    _clear_transient_main_window_status,
    _empty_states_fixture,
    _empty_states_fixture_provenance,
    _master_data_fixture,
    _master_data_fixture_provenance,
    _patched_empty_master_data,
    _patched_master_data_fixture,
    _stabilize_appearance_preferences_probe,
    _stabilize_event_create_probe,
    _stabilize_event_list_probe,
    _stabilize_main_probe,
    _stabilize_master_data_probe,
    _stabilize_month_range_probe,
    _wait_for_popup_visible,
)
from scripts.qt_visual_regress import (
    _copy_baseline_with_retry,
    _current_capture_contract,
)
from ui.appearance_preferences import AppearancePreferences


class _FakeApplication:
    def __init__(self) -> None:
        self.process_count = 0

    def processEvents(self) -> None:
        self.process_count += 1


class _FakeStatusBar:
    def __init__(self) -> None:
        self.clear_count = 0

    def clearMessage(self) -> None:
        self.clear_count += 1


class _FakeMainWindow:
    def __init__(self) -> None:
        self.status_bar = _FakeStatusBar()

    def statusBar(self) -> _FakeStatusBar:
        return self.status_bar


class _EventuallyVisiblePopup:
    def __init__(self, visible_on_call: int | None) -> None:
        self._visible_on_call = visible_on_call
        self.calls = 0

    def isVisible(self) -> bool:
        self.calls += 1
        return (
            self._visible_on_call is not None
            and self.calls >= self._visible_on_call
        )


class VisualProbePopupWaitTests(unittest.TestCase):
    def test_wait_accepts_popup_that_becomes_visible_after_event_cycles(self) -> None:
        app = _FakeApplication()
        popup = _EventuallyVisiblePopup(visible_on_call=3)

        self.assertTrue(
            _wait_for_popup_visible(popup, app, attempts=4, delay_ms=0)
        )
        self.assertGreaterEqual(app.process_count, 3)

    def test_wait_remains_fail_closed_after_bounded_attempts(self) -> None:
        app = _FakeApplication()
        popup = _EventuallyVisiblePopup(visible_on_call=None)

        self.assertFalse(
            _wait_for_popup_visible(popup, app, attempts=3, delay_ms=0)
        )
        self.assertEqual(app.process_count, 4)


class _DateRecorder:
    def __init__(self) -> None:
        self.value = QDate()

    def setDate(self, value: QDate) -> None:
        self.value = value


class _IndexRecorder:
    def __init__(self) -> None:
        self.value = -1

    def setCurrentIndex(self, value: int) -> None:
        self.value = value


class _ScrollRecorder:
    def __init__(self) -> None:
        self.value = -1

    def setValue(self, value: int) -> None:
        self.value = value


class _ScrollArea:
    def __init__(self) -> None:
        self.bar = _ScrollRecorder()

    def verticalScrollBar(self) -> _ScrollRecorder:
        return self.bar


class _FakeForm:
    def __init__(self) -> None:
        self.date_edit = _DateRecorder()
        self.due_date_edit = _DateRecorder()
        self.anomaly_source_combo = _IndexRecorder()
        self.form_scroll = _ScrollArea()
        self.visibility_updates = 0

    def _update_trace_row_visibility(self) -> None:
        self.visibility_updates += 1


class _PreferenceRecorder:
    def __init__(self) -> None:
        self.preferences = None
        self.preview = None

    def _set_preferences(self, preferences, *, preview: bool) -> None:
        self.preferences = preferences
        self.preview = preview


class _RangeSelectorsRecorder:
    def __init__(self) -> None:
        self.values = None

    def set_range(self, start_key: str, end_key: str) -> None:
        self.values = (start_key, end_key)


class _RangeWidgetRecorder:
    def __init__(self) -> None:
        self.range_selectors = _RangeSelectorsRecorder()
        self.refreshed_values = None

    def set_range(self, start_key: str, end_key: str) -> None:
        self.refreshed_values = (start_key, end_key)


class _FocusRecorder:
    def __init__(self) -> None:
        self.set_focus_count = 0

    def setFocus(self) -> None:
        self.set_focus_count += 1


class VisualProbeDeterminismTests(unittest.TestCase):
    def test_appearance_capture_clears_transient_shell_status(self) -> None:
        window = _FakeMainWindow()

        _clear_transient_main_window_status(window)

        self.assertEqual(1, window.status_bar.clear_count)

    def test_main_probe_pins_visible_month(self) -> None:
        events = type("Events", (), {"month_input": _DateRecorder()})()
        window = type("Window", (), {"events_widget": events})()

        _stabilize_main_probe(window)

        self.assertEqual("2026-08-01", events.month_input.value.toString("yyyy-MM-dd"))

    def test_event_create_probe_pins_dates_source_and_scroll(self) -> None:
        form = _FakeForm()
        page = type("Page", (), {"form": form})()

        _stabilize_event_create_probe(page)

        self.assertEqual("2026-08-31", form.date_edit.value.toString("yyyy-MM-dd"))
        self.assertEqual("2026-09-07", form.due_date_edit.value.toString("yyyy-MM-dd"))
        self.assertEqual(0, form.anomaly_source_combo.value)
        self.assertEqual(1, form.visibility_updates)
        self.assertEqual(0, form.form_scroll.bar.value)

    def test_event_create_probe_uses_shell_scroll_in_page_mode(self) -> None:
        form = _FakeForm()
        form.form_scroll = None
        shell_scroll = _ScrollArea()
        shell = type("Shell", (), {"content_scroll": shell_scroll})()
        page = type("Page", (), {"form": form, "workflow_shell": shell})()

        _stabilize_event_create_probe(page)

        self.assertEqual(0, shell_scroll.bar.value)

    def test_appearance_probe_uses_canonical_defaults_without_preview(self) -> None:
        dialog = _PreferenceRecorder()

        _stabilize_appearance_preferences_probe(dialog)

        self.assertEqual(AppearancePreferences.default(), dialog.preferences)
        self.assertFalse(dialog.preview)

    def test_event_list_probe_pins_visible_month(self) -> None:
        widget = type("Widget", (), {"month_input": _DateRecorder()})()

        _stabilize_event_list_probe(widget)

        self.assertEqual("2026-08-01", widget.month_input.value.toString("yyyy-MM-dd"))

    def test_master_data_probe_clears_workstation_hover_state(self) -> None:
        focus = _FocusRecorder()
        widget = type("Widget", (), {"query_input": focus})()
        app = _FakeApplication()

        with (
            patch(
                "scripts.qt_visual_probe._position_probe_cursor_at_safe_corner"
            ) as move_cursor,
            patch("scripts.qt_visual_probe._settle_qt_paint") as settle_paint,
            patch("scripts.qt_visual_probe._clear_widget_hover_state") as clear_hover,
        ):
            _stabilize_master_data_probe(widget, app)

        self.assertEqual(1, focus.set_focus_count)
        move_cursor.assert_called_once_with(widget)
        settle_paint.assert_called_once_with(app, delay_ms=80, cycles=2)
        clear_hover.assert_called_once_with(widget)

    def test_month_range_probe_can_set_controls_without_refresh(self) -> None:
        widget = _RangeWidgetRecorder()

        _stabilize_month_range_probe(widget, refresh=False)

        self.assertEqual(("202603", "202608"), widget.range_selectors.values)
        self.assertIsNone(widget.refreshed_values)

    def test_month_range_probe_can_refresh_through_public_hook(self) -> None:
        widget = _RangeWidgetRecorder()

        _stabilize_month_range_probe(widget, refresh=True)

        self.assertEqual(("202603", "202608"), widget.refreshed_values)
        self.assertIsNone(widget.range_selectors.values)


class MasterDataFixtureContractTests(unittest.TestCase):
    def test_empty_patch_replaces_the_widget_owned_service_functions(self) -> None:
        from ui.widgets import master_data_widget

        original_supplier = master_data_widget._supplier_service.list_suppliers
        original_product = master_data_widget._product_service.list_products

        with _patched_empty_master_data(_empty_states_fixture()):
            self.assertEqual(
                [],
                master_data_widget._supplier_service.list_suppliers(
                    include_inactive=True,
                    category="原物料供應商",
                ),
            )
            self.assertEqual(
                [],
                master_data_widget._product_service.list_products(
                    include_inactive=True,
                    item_categories=("原物料",),
                ),
            )

        self.assertIs(
            original_supplier,
            master_data_widget._supplier_service.list_suppliers,
        )
        self.assertIs(
            original_product,
            master_data_widget._product_service.list_products,
        )

    def test_fixture_patch_replaces_the_widget_owned_service_functions(self) -> None:
        from database.product_item_category import (
            ITEM_CATEGORY_RAW_MATERIAL,
            MASTER_SEMI_FINISHED_CATEGORIES,
        )
        from database.supplier_category import (
            SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
            SUPPLIER_CATEGORY_RAW_MATERIAL,
        )
        from ui.widgets import master_data_widget

        fixture = _master_data_fixture()
        original_supplier = master_data_widget._supplier_service.list_suppliers
        original_product = master_data_widget._product_service.list_products

        with _patched_master_data_fixture(fixture):
            raw_suppliers = master_data_widget._supplier_service.list_suppliers(
                category=SUPPLIER_CATEGORY_RAW_MATERIAL
            )
            outsource_suppliers = master_data_widget._supplier_service.list_suppliers(
                category=SUPPLIER_CATEGORY_OUTSOURCE_FACTORY
            )
            raw_products = master_data_widget._product_service.list_products(
                item_categories=(ITEM_CATEGORY_RAW_MATERIAL,)
            )
            semi_finished_products = (
                master_data_widget._product_service.list_products(
                    item_categories=MASTER_SEMI_FINISHED_CATEGORIES
                )
            )

            self.assertEqual(12, len(raw_suppliers))
            self.assertEqual(8, len(outsource_suppliers))
            self.assertEqual(10, len(raw_products))
            self.assertEqual(10, len(semi_finished_products))

        self.assertIs(
            original_supplier,
            master_data_widget._supplier_service.list_suppliers,
        )
        self.assertIs(
            original_product,
            master_data_widget._product_service.list_products,
        )

    def test_fixture_provenance_is_deterministic_and_complete(self) -> None:
        first = _master_data_fixture_provenance(_master_data_fixture())
        second = _master_data_fixture_provenance(_master_data_fixture())

        self.assertEqual(first, second)
        self.assertEqual("master-data-stress-v1", first["id"])
        self.assertEqual(20, first["supplier_row_count"])
        self.assertEqual(20, first["product_row_count"])
        self.assertEqual(64, len(first["sha256"]))

    def test_empty_states_fixture_provenance_is_deterministic_and_complete(self) -> None:
        first = _empty_states_fixture_provenance(_empty_states_fixture())
        second = _empty_states_fixture_provenance(_empty_states_fixture())

        self.assertEqual(first, second)
        self.assertEqual("empty-states-v1", first["id"])
        self.assertEqual(0, first["event_row_count"])
        self.assertEqual(0, first["supplier_row_count"])
        self.assertEqual(0, first["product_row_count"])
        self.assertEqual(64, len(first["sha256"]))

    def test_master_data_capture_contract_requires_fixture_provenance(self) -> None:
        with self.assertRaises(SystemExit):
            _current_capture_contract({}, "master-data")

    def test_empty_states_capture_contract_requires_fixture_provenance(self) -> None:
        with self.assertRaises(SystemExit):
            _current_capture_contract({}, "empty-states")

    def test_master_data_capture_contract_includes_fixture_provenance(self) -> None:
        provenance = _master_data_fixture_provenance(_master_data_fixture())
        contract = _current_capture_contract(
            {
                "qt_platform": "windows",
                "selected_font": "Microsoft JhengHei UI",
                "scale": "1.0",
                "device_pixel_ratio": 2.0,
                "fixture_provenance": provenance,
            },
            "master-data",
        )

        self.assertEqual(provenance, contract["fixture_provenance"])
        self.assertEqual("windows", contract["env"]["qt_platform"])

    def test_empty_states_capture_contract_includes_fixture_provenance(self) -> None:
        provenance = _empty_states_fixture_provenance(_empty_states_fixture())
        contract = _current_capture_contract(
            {
                "qt_platform": "windows",
                "selected_font": "Microsoft JhengHei UI",
                "scale": "1.0",
                "device_pixel_ratio": 2.0,
                "fixture_provenance": provenance,
            },
            "empty-states",
        )

        self.assertEqual(provenance, contract["fixture_provenance"])
        self.assertEqual("windows", contract["env"]["qt_platform"])


class VisualBaselineCopyRetryTests(unittest.TestCase):
    @staticmethod
    def _windows_error(winerror: int) -> OSError:
        error = OSError(f"winerror {winerror}")
        error.winerror = winerror
        return error

    def test_retries_transient_windows_memory_map_failure(self) -> None:
        transient = self._windows_error(1224)
        with (
            patch(
                "scripts.qt_visual_regress.shutil.copy2",
                side_effect=[transient, None],
            ) as copy2,
            patch("scripts.qt_visual_regress.time.sleep") as sleep,
        ):
            _copy_baseline_with_retry("source", "destination")

        self.assertEqual(2, copy2.call_count)
        sleep.assert_called_once_with(0.25)

    def test_non_transient_copy_failure_remains_fail_closed(self) -> None:
        permanent = self._windows_error(5)
        with (
            patch(
                "scripts.qt_visual_regress.shutil.copy2",
                side_effect=permanent,
            ) as copy2,
            patch("scripts.qt_visual_regress.time.sleep") as sleep,
        ):
            with self.assertRaises(OSError):
                _copy_baseline_with_retry("source", "destination")

        self.assertEqual(1, copy2.call_count)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
