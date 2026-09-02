from __future__ import annotations

import unittest
from unittest.mock import patch

from ui.runtime_mode import is_automated_runtime, missing_supplier_create_gate


def _main_window_importable() -> bool:
    try:
        from ui.main_window import MainWindow  # noqa: F401
    except ImportError:
        return False
    return True


class AutomatedRuntimeFlagTests(unittest.TestCase):
    def test_offscreen_platform_is_automated(self) -> None:
        self.assertTrue(is_automated_runtime({"QT_QPA_PLATFORM": "offscreen"}))

    def test_sqe_testing_is_automated(self) -> None:
        self.assertTrue(is_automated_runtime({"SQE_TESTING": "1"}))

    def test_disposable_db_is_automated(self) -> None:
        self.assertTrue(is_automated_runtime({"SQE_REQUIRE_DISPOSABLE_DB": "1"}))

    def test_probe_is_automated(self) -> None:
        self.assertTrue(is_automated_runtime({"SQE_PROBE": "1"}))

    def test_empty_env_is_interactive(self) -> None:
        self.assertFalse(is_automated_runtime({}))

    def test_windows_qpa_alone_is_interactive(self) -> None:
        self.assertFalse(is_automated_runtime({"QT_QPA_PLATFORM": "windows"}))

    def test_sqe_testing_zero_is_not_automated(self) -> None:
        self.assertFalse(is_automated_runtime({"SQE_TESTING": "0"}))


class MissingSupplierCreateGateTests(unittest.TestCase):
    def test_proceeds_without_warning_when_suppliers_exist(self) -> None:
        self.assertEqual(
            (True, False),
            missing_supplier_create_gate(True, automated=False),
        )
        self.assertEqual(
            (True, False),
            missing_supplier_create_gate(True, automated=True),
        )

    def test_skips_warning_when_automated_and_no_suppliers(self) -> None:
        self.assertEqual(
            (False, False),
            missing_supplier_create_gate(False, automated=True),
        )

    def test_warns_when_interactive_and_no_suppliers(self) -> None:
        self.assertEqual(
            (False, True),
            missing_supplier_create_gate(False, automated=False),
        )

    def test_default_automated_flag_follows_runtime(self) -> None:
        with patch("ui.runtime_mode.is_automated_runtime", return_value=True):
            self.assertEqual((False, False), missing_supplier_create_gate(False))
        with patch("ui.runtime_mode.is_automated_runtime", return_value=False):
            self.assertEqual((False, True), missing_supplier_create_gate(False))


@unittest.skipUnless(_main_window_importable(), "PySide6 MainWindow import required")
class EnsureActiveSuppliersModalTests(unittest.TestCase):
    def _host(self):
        class _Host:
            def open_master_raw_supplier(self) -> None:
                self.opened_master = True

        host = _Host()
        host.opened_master = False
        return host

    def test_skips_warning_when_automated_and_no_suppliers(self) -> None:
        host = self._host()
        from ui.main_window import MainWindow

        with (
            patch(
                "ui.main_window._product_service.has_active_suppliers",
                return_value=False,
            ),
            patch("ui.runtime_mode.is_automated_runtime", return_value=True),
            patch("ui.main_window.QMessageBox.warning") as warning,
        ):
            result = MainWindow._ensure_has_active_suppliers(host)
        self.assertFalse(result)
        warning.assert_not_called()
        self.assertTrue(host.opened_master)

    def test_warns_when_interactive_and_no_suppliers(self) -> None:
        host = self._host()
        from ui.main_window import MainWindow

        with (
            patch(
                "ui.main_window._product_service.has_active_suppliers",
                return_value=False,
            ),
            patch("ui.runtime_mode.is_automated_runtime", return_value=False),
            patch("ui.main_window.QMessageBox.warning") as warning,
        ):
            result = MainWindow._ensure_has_active_suppliers(host)
        self.assertFalse(result)
        warning.assert_called_once()
        self.assertEqual("需先建立供應商", warning.call_args[0][1])
        self.assertTrue(host.opened_master)

    def test_true_when_suppliers_exist(self) -> None:
        host = self._host()
        from ui.main_window import MainWindow

        with (
            patch(
                "ui.main_window._product_service.has_active_suppliers",
                return_value=True,
            ),
            patch("ui.main_window.QMessageBox.warning") as warning,
        ):
            result = MainWindow._ensure_has_active_suppliers(host)
        self.assertTrue(result)
        warning.assert_not_called()
        self.assertFalse(host.opened_master)


if __name__ == "__main__":
    unittest.main()
