from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_repo_imports() -> None:
    repo_root_text = str(REPO_ROOT)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)


def _prepare_native_qt_platform(*, allow_offscreen: bool) -> dict[str, str | bool]:
    original = os.environ.get("QT_QPA_PLATFORM", "")
    forced_native = False

    if allow_offscreen:
        return {"original_qt_platform": original, "forced_native": forced_native}

    if os.name == "nt":
        if original.lower() == "offscreen" or not original:
            os.environ["QT_QPA_PLATFORM"] = "windows"
            forced_native = True
        return {"original_qt_platform": original, "forced_native": forced_native}

    if original.lower() == "offscreen":
        print(
            "Refusing visual probe with QT_QPA_PLATFORM=offscreen. "
            "Use --allow-offscreen only for non-visual structural checks.",
            file=sys.stderr,
        )
        sys.exit(2)

    return {"original_qt_platform": original, "forced_native": forced_native}


def _has_cjk_writing_system(font_db, family: str) -> bool:
    if not family:
        return False
    systems = font_db.writingSystems(family)
    return any(
        system in systems
        for system in (
            font_db.WritingSystem.TraditionalChinese,
            font_db.WritingSystem.SimplifiedChinese,
            font_db.WritingSystem.Japanese,
            font_db.WritingSystem.Korean,
        )
    )


def _default_output_path() -> Path:
    return Path(tempfile.gettempdir()) / "sqetool_qt_visual_probe.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture SQETOOL with a native Qt platform so CJK rendering can be "
            "used as visual evidence."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Screenshot output path. Defaults to the OS temp directory.",
    )
    parser.add_argument(
        "--allow-offscreen",
        action="store_true",
        help="Allow offscreen mode for structural probing; output is not visual evidence.",
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="Run platform and font checks without saving a screenshot.",
    )
    parser.add_argument(
        "--target",
        choices=("main", "form-density", "stats-stress"),
        default="main",
        help="Capture the main shell, dense forms, or statistics visual stress surfaces.",
    )
    return parser.parse_args()


def _target_output_path(output: Path, suffix: str) -> Path:
    if suffix == "main":
        return output
    return output.with_name(f"{output.stem}_{suffix}{output.suffix or '.png'}")


def _capture_widget(widget, output_path: Path, app: "QApplication") -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    widget.show()
    app.processEvents()
    widget.grab().save(str(output_path))
    widget.close()
    app.processEvents()
    return str(output_path)


def _capture_main_window(output: Path, app: "QApplication") -> list[str]:
    from database.connection import initialize_database
    from ui.main_window import MainWindow

    initialize_database()
    window = MainWindow()
    window.resize(1100, 740)
    return [_capture_widget(window, output, app)]


def _capture_form_density(output: Path, app: "QApplication") -> list[str]:
    import sqlite3

    from database.connection import initialize_database
    from ncr.db.database import apply_schema
    from ncr.embed import DefectTrackerPage
    from ncr.ui.defect_form import QuickProductCreateDialog
    from ui.widgets.defect_form_widget import NewVisitDialog
    from ui.widgets.master_data_widget import ProductFormDialog, SupplierFormDialog

    initialize_database()
    screenshots: list[str] = []

    visit_dialog = NewVisitDialog()
    screenshots.append(
        _capture_widget(visit_dialog, _target_output_path(output, "visit-form"), app)
    )

    supplier_dialog = SupplierFormDialog()
    screenshots.append(
        _capture_widget(
            supplier_dialog,
            _target_output_path(output, "supplier-form"),
            app,
        )
    )

    product_dialog = ProductFormDialog(
        [{"id": "supplier-1", "supplier_name": "測試供應商"}]
    )
    screenshots.append(
        _capture_widget(
            product_dialog,
            _target_output_path(output, "product-form"),
            app,
        )
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        apply_schema(conn, with_version=True)
        warehouse_form = DefectTrackerPage(conn)
        warehouse_form.open_create_entry()
        warehouse_form.resize(1180, 720)
        screenshots.append(
            _capture_widget(
                warehouse_form,
                _target_output_path(output, "warehouse-form"),
                app,
            )
        )

        quick_product_dialog = QuickProductCreateDialog(conn, "ITEM-NEW")
        screenshots.append(
            _capture_widget(
                quick_product_dialog,
                _target_output_path(output, "quick-product-form"),
                app,
            )
        )
    finally:
        conn.close()

    return screenshots


def _capture_stats_stress(output: Path, app: "QApplication") -> list[str]:
    from unittest.mock import patch

    from PySide6.QtCore import QDate

    from ui.widgets.stats_view_widget import StatsViewWidget

    long_supplier = "超長供應商名稱-01-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    long_product = "倉庫產品名稱-00-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    summary = {
        "anomaly_count": 200,
        "visit_count": 20,
        "closed_anomaly_count": 40,
        "open_anomaly_count": 160,
        "overdue_open_anomaly_count": 15,
        "top_suppliers_by_anomaly": [
            {
                "supplier_name": (
                    long_supplier
                    if index == 1
                    else f"超長供應商名稱-{index:02d}-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                ),
                "anomaly_count": index + 1,
                "open_anomaly_count": index % 5,
                "overdue_open_anomaly_count": index % 3,
                "closed_anomaly_count": index % 4,
                "avg_resolution_time": 1.5 + index,
            }
            for index in range(30)
        ],
    }
    trend_data = [
        {
            "yyyymm": f"2026-{month:02d}",
            "total_count": month * 2,
            "closed_count": month,
            "overdue_count": month % 3,
            "backlog_count": month * 4,
        }
        for month in range(1, 13)
    ]
    resp_stats = [
        {
            "responsible_person": f"責任人員-{index:02d}-VeryLongName",
            "total_count": index + 2,
            "avg_resolution_time": index / 2 + 1,
        }
        for index in range(25)
    ]
    warehouse_products = [
        {
            "product_name": (
                long_product
                if index == 0
                else f"倉庫產品名稱-{index:02d}-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            ),
            "total_qty": index * 2 + 1,
        }
        for index in range(10)
    ]
    supplier_disposition_rows = [
        {
            "supplier_name": f"倉庫供應商-{index:02d}-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "disposition": disposition,
            "total_qty": index + 1,
        }
        for index in range(10)
        for disposition in ("報廢", "退貨", "重工")
    ]

    class _StatsProbeHost:
        def open_event_query_with_filters(self, **_kwargs):
            return None

        def open_warehouse_nonconforming_tracker(self):
            return None

    screenshots: list[str] = []
    with (
        patch("services.event_service.get_monthly_stats", return_value=summary),
        patch("services.event_service.get_anomaly_trend", return_value=trend_data),
        patch("services.event_service.get_responsible_person_stats", return_value=resp_stats),
        patch(
            "ui.widgets.stats_view_widget.ncr_stats_service.get_disposition_stats",
            return_value=[
                {"disposition": "報廢", "total_qty": 10},
                {"disposition": "退貨", "total_qty": 5},
                {"disposition": "重工", "total_qty": 8},
            ],
        ),
        patch(
            "ui.widgets.stats_view_widget.ncr_stats_service.get_trend_stats",
            return_value=[
                {"event_month": f"2026-{month:02d}", "total_qty": month * 3}
                for month in range(1, 13)
            ],
        ),
        patch(
            "ui.widgets.stats_view_widget.ncr_stats_service.get_top_products_stats",
            return_value=warehouse_products,
        ),
        patch(
            "ui.widgets.stats_view_widget.ncr_stats_service.get_supplier_disposition_stats",
            return_value=supplier_disposition_rows,
        ),
    ):
        widget = StatsViewWidget(main_window=_StatsProbeHost())
        widget.month_input.setDate(QDate(2026, 6, 1))
        widget.resize(1024, 680)
        widget.show()
        app.processEvents()
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            for index, suffix in enumerate(
                (
                    "stats-trend",
                    "stats-responsible",
                    "stats-supplier-risk",
                    "stats-warehouse",
                )
            ):
                widget.tabs.setCurrentIndex(index)
                app.processEvents()
                target = _target_output_path(output, suffix)
                widget.grab().save(str(target))
                screenshots.append(str(target))
        finally:
            widget.close()
            app.processEvents()

    return screenshots


def main() -> int:
    args = parse_args()
    _ensure_repo_imports()
    platform_info = _prepare_native_qt_platform(
        allow_offscreen=bool(args.allow_offscreen)
    )

    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from ui.theme import apply_app_theme

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_app_theme(app)

    selected_font = app.font().family()
    cjk_font_ok = _has_cjk_writing_system(QFontDatabase, selected_font)
    is_offscreen = app.platformName().lower() == "offscreen"
    visual_trustworthy = (not is_offscreen) and cjk_font_ok

    screenshot_path = None
    screenshots: list[str] = []
    if not args.no_screenshot:
        if args.target == "stats-stress":
            screenshots = _capture_stats_stress(args.output, app)
        elif args.target == "form-density":
            screenshots = _capture_form_density(args.output, app)
        else:
            screenshots = _capture_main_window(args.output, app)
        screenshot_path = screenshots[0] if screenshots else None

    result = {
        **platform_info,
        "target": args.target,
        "qt_platform_env": os.environ.get("QT_QPA_PLATFORM", ""),
        "qt_platform": app.platformName(),
        "selected_font": selected_font,
        "cjk_font_ok": cjk_font_ok,
        "visual_trustworthy": visual_trustworthy,
        "screenshot": screenshot_path,
    }
    if screenshots:
        result["screenshots"] = screenshots
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not visual_trustworthy and not args.allow_offscreen:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
