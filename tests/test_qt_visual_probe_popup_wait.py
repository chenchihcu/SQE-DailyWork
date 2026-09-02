from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QDate

from scripts.qt_visual_probe import (
    _clear_transient_main_window_status,
    _stabilize_appearance_preferences_probe,
    _stabilize_event_create_probe,
    _stabilize_event_list_probe,
    _stabilize_main_probe,
    _stabilize_month_range_probe,
    _wait_for_popup_visible,
)
from scripts.qt_visual_regress import _copy_baseline_with_retry
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
