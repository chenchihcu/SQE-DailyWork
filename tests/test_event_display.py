from __future__ import annotations

import unittest

from ui.event_display import event_type_display


class EventDisplayTests(unittest.TestCase):
    def test_event_type_labels(self) -> None:
        self.assertEqual("異常", event_type_display("ANOMALY"))
        self.assertEqual("訪廠", event_type_display("VISIT"))
        self.assertEqual("-", event_type_display(""))
        self.assertEqual("異常", event_type_display("anomaly"))


if __name__ == "__main__":
    unittest.main()
