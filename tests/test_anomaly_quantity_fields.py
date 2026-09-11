from __future__ import annotations

import unittest

from database.repo_helpers import (
    compute_defect_rate,
    defect_rate_denominator,
    enrich_anomaly_quantity_fields,
    format_defect_rate_display,
)


class AnomalyQuantityFieldTests(unittest.TestCase):
    def test_compute_defect_rate_returns_none_when_batch_zero(self) -> None:
        self.assertIsNone(compute_defect_rate(0, 5))

    def test_compute_defect_rate_returns_fraction(self) -> None:
        self.assertAlmostEqual(0.03, compute_defect_rate(200, 6))

    def test_compute_defect_rate_prefers_inspected_denominator(self) -> None:
        self.assertAlmostEqual(0.05, compute_defect_rate(200, 5, qty_inspected=100))

    def test_defect_rate_denominator_prefers_inspected(self) -> None:
        self.assertEqual((100, "檢驗數"), defect_rate_denominator(200, 100))
        self.assertEqual((200, "批量數"), defect_rate_denominator(200, 0))

    def test_format_defect_rate_display(self) -> None:
        self.assertEqual("—", format_defect_rate_display(0, 3))
        self.assertEqual("3.00%", format_defect_rate_display(200, 6))
        self.assertEqual("5.00%", format_defect_rate_display(200, 5, qty_inspected=100))

    def test_enrich_anomaly_quantity_fields(self) -> None:
        detail = enrich_anomaly_quantity_fields({"batch_qty": 100, "qty_ng": 1})
        self.assertEqual("1.00%", detail["defect_rate_display"])
        self.assertAlmostEqual(0.01, detail["defect_rate"])
        self.assertEqual(100, detail["defect_rate_denominator"])
        self.assertEqual("批量數", detail["defect_rate_denominator_label"])

    def test_enrich_anomaly_quantity_fields_uses_inspected_denominator(self) -> None:
        detail = enrich_anomaly_quantity_fields(
            {"batch_qty": 200, "qty_inspected": 50, "qty_ng": 2}
        )
        self.assertEqual("4.00%", detail["defect_rate_display"])
        self.assertEqual(50, detail["defect_rate_denominator"])
        self.assertEqual("檢驗數", detail["defect_rate_denominator_label"])


if __name__ == "__main__":
    unittest.main()
