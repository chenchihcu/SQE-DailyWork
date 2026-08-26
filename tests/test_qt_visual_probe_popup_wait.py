from __future__ import annotations

import unittest

from scripts.qt_visual_probe import _wait_for_popup_visible


class _FakeApplication:
    def __init__(self) -> None:
        self.process_count = 0

    def processEvents(self) -> None:
        self.process_count += 1


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


if __name__ == "__main__":
    unittest.main()
