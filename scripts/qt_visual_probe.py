from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

# Stress strings reused across targets so every surface is checked with long CJK.
LONG_SUPPLIER = "超長供應商名稱-01-ABCDEFGHIJKLMNOPQRSTUVWXYZ股份有限公司"
LONG_PRODUCT = "倉庫產品名稱-00-ABCDEFGHIJKLMNOPQRSTUVWXYZ精密組件"

# Targets that render a resizable top-level surface (so --size / --min-width apply).
_RESIZABLE_TARGETS = {
    "main",
    "event-list",
    "master-data",
    "ncr-tracker",
    "empty-states",
    "stats-stress",
    "ncr-stats",
}
MIN_WIDTH_SIZE = (1024, 680)


def _ensure_repo_imports() -> None:
    for path in (SRC_ROOT, REPO_ROOT):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


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


def _resolve_cjk_family(font_db, families: tuple[str, ...]) -> str | None:
    """First family in `families` that is both installed and CJK-capable."""
    available = set(font_db.families())
    for family in families:
        if family in available and _has_cjk_writing_system(font_db, family):
            return family
    return None


def _default_output_path() -> Path:
    return Path(tempfile.gettempdir()) / "sqe_dailywork_qt_visual_probe.png"


# ── QSS "Unknown property" capture ──────────────────────────────────────────
# main.py installs a Qt message handler that logs unsupported-QSS warnings. The
# probe replicates it so silently-failing QSS (box-shadow / transition / etc.,
# unsupported by Qt) is surfaced instead of passing a clean-looking screenshot.
_QSS_WARNINGS: list[str] = []


def _install_qss_warning_collector() -> None:
    from PySide6.QtCore import qInstallMessageHandler

    def _handler(_msg_type, _context, message: str) -> None:
        if "Unknown property" in message:
            _QSS_WARNINGS.append(message)

    qInstallMessageHandler(_handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture SQE DailyWork with a native Qt platform so CJK rendering can be "
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
        choices=(
            "main",
            "form-density",
            "stats-stress",
            "ncr-stats",
            "event-list",
            "master-data",
            "ncr-tracker",
            "empty-states",
            "pdf-export",
        ),
        default="main",
        help="Which surface family to capture.",
    )
    parser.add_argument(
        "--scale",
        default="1.0",
        help=(
            "Comma-separated DPI scale factors (e.g. 1.0,1.25,1.5). More than one "
            "value re-execs one child process per scale because QT_SCALE_FACTOR must "
            "be set before QApplication is created."
        ),
    )
    parser.add_argument(
        "--size",
        default=None,
        help="Override resizable-surface size as WxH (e.g. 1024x680).",
    )
    parser.add_argument(
        "--min-width",
        action="store_true",
        help=f"Capture resizable surfaces at the {MIN_WIDTH_SIZE[0]}x{MIN_WIDTH_SIZE[1]} contract minimum.",
    )
    return parser.parse_args()


def _resolve_size(args: argparse.Namespace) -> tuple[int, int] | None:
    if args.size:
        width, _, height = args.size.lower().partition("x")
        return (int(width), int(height))
    if args.min_width:
        return MIN_WIDTH_SIZE
    return None


def _target_output_path(output: Path, suffix: str) -> Path:
    if suffix == "main":
        return output
    return output.with_name(f"{output.stem}_{suffix}{output.suffix or '.png'}")


def _scale_output(output: Path, scale: str) -> Path:
    if scale in ("", "1", "1.0"):
        return output
    return output.with_name(f"{output.stem}@{scale}x{output.suffix or '.png'}")


def _capture_widget(widget, output_path: Path, app: "QApplication") -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    widget.show()
    app.processEvents()
    widget.grab().save(str(output_path))
    widget.close()
    app.processEvents()
    return str(output_path)


class _ProbeHost:
    """Minimal stand-in for MainWindow callbacks used by embedded widgets."""

    def open_new_visit_dialog(self, *_a, **_k):
        return None

    def open_new_anomaly_dialog(self, *_a, **_k):
        return None

    def open_event_query_with_filters(self, *_a, **_k):
        return None

    def open_warehouse_nonconforming_tracker(self, *_a, **_k):
        return None


def _stress_event_rows() -> list[dict]:
    scopes = ("ANOMALY", "VISIT", "ANOMALY", "VISIT")
    rows = []
    for index in range(24):
        rows.append(
            {
                "id": f"evt-{index}",
                "event_date": f"2026-{(index % 12) + 1:02d}-15",
                "event_type": scopes[index % len(scopes)],
                "supplier_name": LONG_SUPPLIER if index == 0 else f"供應商-{index:02d}-長名稱股份有限公司",
                "product_name": LONG_PRODUCT if index == 1 else f"產品-{index:02d}-精密組件",
                "product_code": f"ITEM-{index:04d}",
                "product_stage": "量產" if index % 2 else "試產",
                "work_order_no": f"WO-{index:05d}",
                "production_qty": index * 10,
                "content": f"異常內容描述-{index}-長文字內容測試省略與 tooltip 行為驗證",
                "defect_note_summary": f"缺失摘要-{index}",
                "pending_items": f"待辦-{index}",
                "status": "待處理" if index % 3 else "已結案",
                "event_scope": "anomaly_only",
            }
        )
    return rows


def _stress_supplier_rows() -> list[dict]:
    rows = []
    for index in range(20):
        rows.append(
            {
                "id": f"sup-{index}",
                "supplier_name": LONG_SUPPLIER if index == 0 else f"供應商-{index:02d}-長名稱股份有限公司",
                "contact_name": f"聯絡人-{index:02d}",
                "department": "品保部" if index % 2 else "採購部",
                "contact_email": f"contact{index:02d}@example.com",
                "phone": f"02-1234-{index:04d}",
                "is_active": index % 5 != 0,
            }
        )
    return rows


def _stress_product_rows() -> list[dict]:
    rows = []
    for index in range(20):
        rows.append(
            {
                "id": f"prod-{index}",
                "product_code": f"ITEM-{index:04d}",
                "product_name": LONG_PRODUCT if index == 0 else f"產品-{index:02d}-精密組件",
                "product_stage": "MP" if index % 2 else "PP",
                "supplier_name": f"供應商-{index:02d}-長名稱股份有限公司",
                "secondary_supplier_name": f"次要供應商-{index:02d}" if index % 3 else None,
                "is_active": index % 5 != 0,
            }
        )
    return rows


def _capture_main_window(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    from database.connection import initialize_database
    from ui.main_window import MainWindow, EVENT_PAGE_INDEX

    initialize_database()
    window = MainWindow()
    window.resize(*(size or (1100, 740)))
    # Land on the event-management page (the daily primary surface) rather than 首頁.
    try:
        window._switch_primary_page(EVENT_PAGE_INDEX)
    except Exception as exc:
        print(f"warning: could not switch visual probe page: {exc}", file=sys.stderr)
    return [_capture_widget(window, output, app)]


def _capture_event_list(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    from unittest.mock import patch

    from database.connection import initialize_database
    from ui.widgets.defect_list_widget import EventListWidget

    initialize_database()
    screenshots: list[str] = []
    with patch("services.event_service.list_events", return_value=_stress_event_rows()):
        widget = EventListWidget(_ProbeHost(), mode="query", fixed_scope=None, lazy_load=False)
        widget.resize(*(size or (1180, 720)))
        widget.show()
        app.processEvents()
        output.parent.mkdir(parents=True, exist_ok=True)
        scope_tab_bar = getattr(widget, "event_scope_tab_bar", None)
        tab_count = scope_tab_bar.count() if scope_tab_bar is not None else 1
        for index in range(max(tab_count, 1)):
            if scope_tab_bar is not None:
                scope_tab_bar.setCurrentIndex(index)
                app.processEvents()
            target = _target_output_path(output, f"event-list-scope{index}")
            widget.grab().save(str(target))
            screenshots.append(str(target))
        widget.close()
        app.processEvents()
    return screenshots


def _capture_master_data(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    from unittest.mock import patch

    from database.connection import initialize_database
    from ui.widgets.master_data_widget import MasterDataWidget

    initialize_database()
    screenshots: list[str] = []
    with (
        patch("services.event_service.list_suppliers", return_value=_stress_supplier_rows()),
        patch("services.event_service.list_products", return_value=_stress_product_rows()),
    ):
        widget = MasterDataWidget(_ProbeHost(), lazy_load=False)
        widget.resize(*(size or (1180, 720)))
        widget.show()
        app.processEvents()
        output.parent.mkdir(parents=True, exist_ok=True)
        for index, suffix in enumerate(("master-supplier", "master-product")):
            widget.tabs.setCurrentIndex(index)
            app.processEvents()
            target = _target_output_path(output, suffix)
            widget.grab().save(str(target))
            screenshots.append(str(target))
        widget.close()
        app.processEvents()
    return screenshots


def _capture_ncr_tracker(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    import sqlite3

    from ncr.db.database import apply_schema
    from ncr.embed import NcrWorkflowPage
    from ncr.ui.defect_form import DefectFormWidget
    from ncr.ui.defect_list import DefectListWidget

    screenshots: list[str] = []
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        apply_schema(conn, with_version=True)
        pages = [
            (NcrWorkflowPage(DefectFormWidget(conn), "NcrCreatePage"), "ncr-create"),
            (
                NcrWorkflowPage(
                    DefectListWidget(conn, workflow="tracking"),
                    "NcrPendingPage",
                ),
                "ncr-pending",
            ),
            (
                NcrWorkflowPage(
                    DefectListWidget(conn, workflow="trace"),
                    "NcrHistoryPage",
                ),
                "ncr-history",
            ),
        ]
        output.parent.mkdir(parents=True, exist_ok=True)
        for page, suffix in pages:
            page.resize(*(size or (1180, 720)))
            page.show()
            app.processEvents()
            target = _target_output_path(output, suffix)
            page.grab().save(str(target))
            screenshots.append(str(target))
            page.close()
            app.processEvents()
    finally:
        conn.close()
    return screenshots


def _capture_empty_states(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    from unittest.mock import patch

    from database.connection import initialize_database
    from ui.widgets.defect_list_widget import EventListWidget
    from ui.widgets.master_data_widget import MasterDataWidget

    initialize_database()
    screenshots: list[str] = []
    with (
        patch("services.event_service.list_events", return_value=[]),
        patch("services.event_service.list_suppliers", return_value=[]),
        patch("services.event_service.list_products", return_value=[]),
    ):
        event_widget = EventListWidget(_ProbeHost(), mode="query", fixed_scope=None, lazy_load=False)
        event_widget.resize(*(size or (1180, 720)))
        screenshots.append(
            _capture_widget(event_widget, _target_output_path(output, "empty-event-list"), app)
        )

        master_widget = MasterDataWidget(_ProbeHost(), lazy_load=False)
        master_widget.resize(*(size or (1180, 720)))
        screenshots.append(
            _capture_widget(master_widget, _target_output_path(output, "empty-master"), app)
        )

    # NCR-unavailable placeholder (DB load failure path) rendered standalone.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    placeholder = QLabel("倉庫不合格品模組暫時無法載入。\n\n（範例：資料庫初始化失敗）")
    placeholder.setObjectName("NcrUnavailablePlaceholder")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder.setWordWrap(True)
    placeholder.resize(*(size or (1180, 720)))
    screenshots.append(
        _capture_widget(placeholder, _target_output_path(output, "empty-ncr-placeholder"), app)
    )
    return screenshots


def _capture_form_density(output: Path, app: "QApplication") -> list[str]:
    import sqlite3

    from database.connection import initialize_database
    from ncr.db.database import apply_schema
    from ncr.embed import NcrWorkflowPage
    from ncr.ui.defect_form import DefectFormWidget, QuickProductCreateDialog
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
        warehouse_form = NcrWorkflowPage(DefectFormWidget(conn), "NcrCreatePage")
        warehouse_form.resize(1180, 720)
        screenshots.append(
            _capture_widget(
                warehouse_form,
                _target_output_path(output, "warehouse-form"),
                app,
            )
        )

        # production 中此對話框的 parent 為已套用 NCR stylesheet 的頁面，
        # role="primary" 才會呈現 Electric Blue；探針給予同樣 styled parent 以反映實際渲染。
        from PySide6.QtWidgets import QWidget
        from ncr.ui.ui_style import app_stylesheet as _ncr_app_stylesheet

        _ncr_style_host = QWidget()
        _ncr_style_host.setStyleSheet(_ncr_app_stylesheet())
        quick_product_dialog = QuickProductCreateDialog(conn, "ITEM-NEW", _ncr_style_host)
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


def _capture_stats_stress(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    from unittest.mock import patch

    from PySide6.QtWidgets import QScrollArea

    from ui.widgets.stats_view_widget import StatsViewWidget

    long_supplier = "超長供應商名稱-01-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
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
            "closed_count": index % 4,
            "open_count": (index % 5) + 1,
            "avg_resolution_time": index / 2 + 1,
            "min_open_date": "2026-01-15",
            "max_open_date": "2026-12-15",
        }
        for index in range(25)
    ]
    category_pareto = [
        {"rank": 1, "category": "超長異常類別名稱-01-ABCDEFGHIJKLMNOPQRSTUVWXYZ", "count": 42, "percent": 42.0, "cumulative_percent": 42.0},
        {"rank": 2, "category": "來料品質不良", "count": 25, "percent": 25.0, "cumulative_percent": 67.0},
        {"rank": 3, "category": "尺寸/規格不符", "count": 16, "percent": 16.0, "cumulative_percent": 83.0},
        {"rank": 4, "category": "外觀不良", "count": 10, "percent": 10.0, "cumulative_percent": 93.0},
        {"rank": 5, "category": "未分類", "count": 7, "percent": 7.0, "cumulative_percent": 100.0},
    ]
    class _StatsProbeHost:
        def open_event_query_with_filters(self, **_kwargs):
            return None

        def open_warehouse_nonconforming_tracker(self):
            return None

    screenshots: list[str] = []
    with (
        patch("services.event_service.get_monthly_stats", return_value=summary),
        patch("services.event_service.get_anomaly_trend_by_range", return_value=trend_data),
        patch("services.event_service.get_visit_trend_by_range", return_value=[]),
        patch("services.event_service.get_responsible_person_stats_by_range", return_value=resp_stats),
        patch("services.event_service.get_anomaly_category_pareto_by_range", return_value=category_pareto),
    ):
        widget = StatsViewWidget(main_window=_StatsProbeHost())
        # 操作真實可見的起迄下拉（AGENTS §3：探針不得驅動隱藏代理）；
        # 區間與 mock trend_data 的 12 個月一致，面板標題與圖內標題才會相符
        widget.set_range("202601", "202612")
        widget.resize(*(size or (1024, 680)))
        widget.show()
        app.processEvents()
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            scroll = widget.findChild(QScrollArea, "StatsTrendScrollArea")
            capture_points = (
                ("stats-overview", 0),
                ("stats-pareto", "pareto"),
                ("stats-risk", "bottom"),
            )
            for suffix, position in capture_points:
                if scroll is not None:
                    bar = scroll.verticalScrollBar()
                    if position == "bottom":
                        target_value = bar.maximum()
                    elif position == "pareto":
                        target_value = bar.maximum() // 2
                    else:
                        target_value = int(position)
                    bar.setValue(target_value)
                app.processEvents()
                target = _target_output_path(output, suffix)
                widget.grab().save(str(target))
                screenshots.append(str(target))
        finally:
            widget.close()
            app.processEvents()

    return screenshots


def _capture_ncr_stats(output: Path, app: "QApplication", size: tuple[int, int] | None) -> list[str]:
    """NcrStatsWidget 2x2 視覺拓撲中 (mock 資料)，用於確認二欄二列網格修正效果。"""
    from unittest.mock import patch

    _MOCK_SUPPLIERS = [
        {"supplier_name": f"供應商-{i:02d}", "case_count": 10 - i, "total_qty": (10 - i) * 3}
        for i in range(5)
    ]
    _MOCK_PRODUCTS = [
        {"product_name": f"產品-{i:02d}", "case_count": 8 - i, "total_qty": (8 - i) * 2}
        for i in range(5)
    ]
    _MOCK_SCRAP_REWORK = [
        {"disposition": "報廢", "case_count": 8, "total_qty": 24},
        {"disposition": "重工", "case_count": 15, "total_qty": 45},
    ]
    _MOCK_RETURN_SLIPS = [
        {"return_slip_type": "廠內退料", "case_count": 20, "total_qty": 60},
        {"return_slip_type": "託外退料", "case_count": 12, "total_qty": 36},
    ]

    from ui.widgets.ncr_stats_widget import NcrStatsWidget

    screenshots: list[str] = []
    with (
        patch(
            "ncr.services.stats_service.get_top_suppliers_stats_by_range",
            return_value=_MOCK_SUPPLIERS,
        ),
        patch(
            "ncr.services.stats_service.get_top_products_stats_by_range",
            return_value=_MOCK_PRODUCTS,
        ),
        patch(
            "ncr.services.stats_service.get_scrap_rework_ratio_by_range",
            return_value=_MOCK_SCRAP_REWORK,
        ),
        patch(
            "ncr.services.stats_service.get_return_slip_ratio_by_range",
            return_value=_MOCK_RETURN_SLIPS,
        ),
    ):
        widget = NcrStatsWidget(lazy_load=False)
        widget.resize(*(size or (1024, 700)))
        widget.show()
        app.processEvents()
        output.parent.mkdir(parents=True, exist_ok=True)
        target = _target_output_path(output, "ncr-stats")
        widget.grab().save(str(target))
        screenshots.append(str(target))
        widget.close()
        app.processEvents()

    return screenshots


def _capture_pdf_export(output: Path) -> dict:
    """Render a sample event PDF and report the PDF font chain (separate from Qt)."""
    from PySide6.QtGui import QFontDatabase

    from services import event_pdf_exporter

    font_family = event_pdf_exporter._preferred_pdf_font_family()
    pdf_cjk_font_ok = _has_cjk_writing_system(QFontDatabase, font_family)

    pdf_path = output.with_name(f"{output.stem}_event.pdf")
    sample_ok = False
    sample_msg = ""
    row = {
        "id": "evt-sample",
        "event_type": "ANOMALY",
        "event_date": "2026-06-22",
        "supplier_name": LONG_SUPPLIER,
        "product_name": LONG_PRODUCT,
        "product_code": "ITEM-0001",
        "status": "待處理",
        "content": "異常內容：長中文字 CJK 渲染與字型嵌入驗證。",
    }
    detail = {"event": row, "anomaly": row, "defect_notes": [], "product_sections": []}
    try:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        sample_ok, sample_msg = event_pdf_exporter.export_event_pdf(pdf_path, row, detail)
    except Exception as exc:  # best-effort sample; font report is the key signal
        sample_msg = f"sample PDF skipped: {exc}"

    return {
        "pdf_font_family": font_family,
        "pdf_cjk_font_ok": pdf_cjk_font_ok,
        "pdf_sample_written": bool(sample_ok),
        "pdf_sample_path": str(pdf_path) if sample_ok else None,
        "pdf_sample_message": sample_msg,
    }


def _run_multi_scale(args: argparse.Namespace, scales: list[str]) -> int:
    """One child process per scale (QT_SCALE_FACTOR must precede QApplication)."""
    worst = 0
    results = []
    for scale in scales:
        child = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--target",
            args.target,
            "--output",
            str(args.output),
            "--scale",
            scale,
        ]
        if args.allow_offscreen:
            child.append("--allow-offscreen")
        if args.no_screenshot:
            child.append("--no-screenshot")
        if args.min_width:
            child.append("--min-width")
        if args.size:
            child += ["--size", args.size]
        completed = subprocess.run(child, capture_output=True, text=True, check=False)
        sys.stdout.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        results.append({"scale": scale, "exit_code": completed.returncode})
        worst = max(worst, completed.returncode)
    print(json.dumps({"multi_scale": results}, ensure_ascii=False, indent=2))
    return worst


def main() -> int:
    args = parse_args()

    scales = [s.strip() for s in str(args.scale).split(",") if s.strip()]
    if len(scales) > 1:
        return _run_multi_scale(args, scales)
    scale = scales[0] if scales else "1.0"

    # QT_SCALE_FACTOR must be set before QApplication is constructed.
    if scale not in ("", "1", "1.0"):
        os.environ["QT_SCALE_FACTOR"] = scale

    _ensure_repo_imports()
    platform_info = _prepare_native_qt_platform(
        allow_offscreen=bool(args.allow_offscreen)
    )
    _install_qss_warning_collector()

    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from ui.theme import apply_app_theme

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_app_theme(app)

    selected_font = app.font().family()
    cjk_font_ok = _has_cjk_writing_system(QFontDatabase, selected_font)

    # NCR module ships its own font stack; validate it independently so a divergent
    # second list cannot pass behind the main-theme trust flag.
    ncr_family = None
    try:
        from ncr.ui.ui_style import PREFERRED_CJK_FONT_FAMILIES as NCR_FAMILIES

        ncr_family = _resolve_cjk_family(QFontDatabase, tuple(NCR_FAMILIES))
    except Exception:
        ncr_family = None
    ncr_cjk_font_ok = ncr_family is not None

    is_offscreen = app.platformName().lower() == "offscreen"
    visual_trustworthy = (not is_offscreen) and cjk_font_ok

    output = _scale_output(args.output, scale)
    size = _resolve_size(args)

    screenshot_path = None
    screenshots: list[str] = []
    pdf_info: dict = {}
    if not args.no_screenshot:
        if args.target == "stats-stress":
            screenshots = _capture_stats_stress(output, app, size)
        elif args.target == "form-density":
            screenshots = _capture_form_density(output, app)
        elif args.target == "ncr-stats":
            screenshots = _capture_ncr_stats(output, app, size)
        elif args.target == "event-list":
            screenshots = _capture_event_list(output, app, size)
        elif args.target == "master-data":
            screenshots = _capture_master_data(output, app, size)
        elif args.target == "ncr-tracker":
            screenshots = _capture_ncr_tracker(output, app, size)
        elif args.target == "empty-states":
            screenshots = _capture_empty_states(output, app, size)
        elif args.target == "pdf-export":
            pdf_info = _capture_pdf_export(output)
        else:
            screenshots = _capture_main_window(output, app, size)
        screenshot_path = screenshots[0] if screenshots else None

    try:
        device_pixel_ratio = app.primaryScreen().devicePixelRatio()
    except Exception:
        device_pixel_ratio = float(app.devicePixelRatio())

    result = {
        **platform_info,
        "target": args.target,
        "scale": scale,
        "device_pixel_ratio": device_pixel_ratio,
        "size": list(size) if size else None,
        "qt_platform_env": os.environ.get("QT_QPA_PLATFORM", ""),
        "qt_platform": app.platformName(),
        "selected_font": selected_font,
        "cjk_font_ok": cjk_font_ok,
        "ncr_font_family": ncr_family,
        "ncr_cjk_font_ok": ncr_cjk_font_ok,
        "qss_unknown_property_warnings": len(_QSS_WARNINGS),
        "visual_trustworthy": visual_trustworthy,
        "screenshot": screenshot_path,
    }
    if screenshots:
        result["screenshots"] = screenshots
    if _QSS_WARNINGS:
        result["qss_warning_samples"] = _QSS_WARNINGS[:5]
    if pdf_info:
        result.update(pdf_info)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not visual_trustworthy and not args.allow_offscreen:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
