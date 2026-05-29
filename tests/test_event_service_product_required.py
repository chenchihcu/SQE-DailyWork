from __future__ import annotations

import unittest
from unittest.mock import patch

from services import event_service


class EventServiceProductRequiredTests(unittest.TestCase):
    def test_create_anomaly_requires_product_id(self) -> None:
        with patch.object(event_service, "get_connection", side_effect=AssertionError):
            with self.assertRaises(ValueError) as ctx:
                event_service.create_anomaly(
                    {
                        "supplier_id": "sup-1",
                        "problem_desc": "missing product",
                    }
                )
        self.assertEqual("Product is required", str(ctx.exception))

    def test_create_anomaly_with_visit_link_requires_product_id(self) -> None:
        with patch.object(event_service, "get_connection", side_effect=AssertionError):
            with self.assertRaises(ValueError) as ctx:
                event_service.create_anomaly_with_visit_link(
                    {
                        "supplier_id": "sup-1",
                        "problem_desc": "missing product",
                    }
                )
        self.assertEqual("Product is required", str(ctx.exception))

    def test_update_anomaly_requires_product_id(self) -> None:
        with patch.object(event_service, "get_connection", side_effect=AssertionError):
            with self.assertRaises(ValueError) as ctx:
                event_service.update_anomaly(
                    "anomaly-1",
                    {
                        "supplier_id": "sup-1",
                        "problem_desc": "missing product",
                    },
                )
        self.assertEqual("Product is required", str(ctx.exception))

    def test_create_visit_requires_product_id(self) -> None:
        with patch.object(event_service, "get_connection", side_effect=AssertionError):
            with self.assertRaises(ValueError) as ctx:
                event_service.create_visit(
                    {
                        "supplier_id": "sup-1",
                        "summary": "missing product",
                    }
                )
        self.assertEqual("Product is required", str(ctx.exception))

    def test_update_visit_requires_product_id(self) -> None:
        with patch.object(event_service, "get_connection", side_effect=AssertionError):
            with self.assertRaises(ValueError) as ctx:
                event_service.update_visit(
                    "visit-1",
                    {
                        "supplier_id": "sup-1",
                        "summary": "missing product",
                    },
                )
        self.assertEqual("Product is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
