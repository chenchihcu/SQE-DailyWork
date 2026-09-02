"""Subprocess-isolated UI button audit for SQE DailyWork.

Orchestrator mode (default) spawns one worker subprocess per page to avoid
Windows offscreen Qt ACCESS_VIOLATION from long-lived widget chains.

Worker mode: ``python button_audit_report.py --page <key>``
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (SRC_ROOT, REPO_ROOT):
    candidate = str(path)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

SEH_RETURN_CODES = frozenset(
    {
        -1073741819,
        3221226356,
        3221225477,
    }
)

PAGE_KEYS: tuple[str, ...] = (
    "main_window",
    "event_create_anomaly",
    "event_list",
    "master_data",
    "supplier_form",
    "product_form",
    "appearance_prefs",
    "ncr_defect_form",
    "ncr_defect_list",
)

# Offscreen Qt heap corruption when clicking DefectFormWidget-backed anomaly create buttons.
STRUCTURAL_ONLY_PAGE_KEYS = frozenset({"event_create_anomaly"})


class _ProbeHost:
    def open_new_visit_dialog(self, *_a: Any, **_k: Any) -> None:
        pass

    def open_new_anomaly_dialog(self, *_a: Any, **_k: Any) -> None:
        pass

    def open_event_query_with_filters(self, *_a: Any, **_k: Any) -> None:
        pass

    def open_warehouse_nonconforming_tracker(self, *_a: Any, **_k: Any) -> None:
        pass


def _configure_audit_environment() -> None:
    """Set process flags only when the button audit is actually executed."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SQE_TESTING", "1")
    os.environ.setdefault("SQE_REQUIRE_DISPOSABLE_DB", "1")


def _prepare_disposable_database() -> str:
    _configure_audit_environment()
    from database.backup import backup_sqlite_database
    import atexit
    import tempfile

    source = (REPO_ROOT / "data" / "sqe_v2.db").resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="sqe-button-audit-")
    atexit.register(temp_dir.cleanup)
    destination = Path(temp_dir.name) / "sqe_v2.db"
    backup_sqlite_database(source, destination)
    os.environ["SQE_DB_PATH"] = str(destination)
    return str(destination)


def _close_msg_boxes(app: Any) -> None:
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, (QMessageBox, QDialog)):
            widget.reject()


def _cleanup_top_level_widgets(app: Any) -> None:
    from PySide6.QtWidgets import QApplication

    for widget in list(QApplication.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    app.processEvents()


def _create_ncr_connection() -> Any:
    from ncr.db.database import apply_schema
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_schema(conn, with_version=True)
    return conn


def create_page(page_key: str) -> Any:
    host = _ProbeHost()
    if page_key == "main_window":
        from ui.main_window import MainWindow

        return MainWindow()
    if page_key == "event_create_anomaly":
        from ui.widgets.event_create_page import EventCreatePage

        return EventCreatePage(host, "anomaly", lazy_load=False)
    if page_key == "event_list":
        from ui.widgets.defect_list_widget import EventListWidget

        return EventListWidget(host, mode="query", fixed_scope=None, lazy_load=False)
    if page_key == "master_data":
        from ui.widgets.master_data_widget import MasterDataSupplierPage
        from database.supplier_category import SUPPLIER_CATEGORY_RAW_MATERIAL

        return MasterDataSupplierPage(
            host,
            SUPPLIER_CATEGORY_RAW_MATERIAL,
            page_label="原物料供應商",
            lazy_load=False,
        )
    if page_key == "supplier_form":
        from ui.widgets.supplier_form_dialog import SupplierFormDialog

        return SupplierFormDialog()
    if page_key == "product_form":
        from ui.widgets.product_form_dialog import ProductFormDialog

        return ProductFormDialog([{"id": "supplier-1", "supplier_name": "測試供應商"}])
    if page_key == "appearance_prefs":
        from ui.widgets.appearance_preferences_dialog import AppearancePreferencesPage

        return AppearancePreferencesPage()
    if page_key == "ncr_defect_form":
        from ncr.ui.defect_form import DefectFormWidget

        return DefectFormWidget(_create_ncr_connection())
    if page_key == "ncr_defect_list":
        from ncr.ui.defect_list import DefectListWidget

        return DefectListWidget(_create_ncr_connection(), workflow="trace")
    raise KeyError(f"Unknown page key: {page_key}")


def audit_page_buttons(page: Any, app: Any) -> list[dict[str, Any]]:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QAbstractButton, QWidget

    results: list[dict[str, Any]] = []
    if not isinstance(page, QWidget):
        return results

    page.show()
    app.processEvents()
    buttons = page.findChildren(QAbstractButton)
    btn_info: list[tuple[Any, str]] = []
    for btn in buttons:
        try:
            name = btn.objectName() or btn.text() or str(btn)
            btn_info.append((btn, name))
        except RuntimeError:
            pass

    page_name = page.__class__.__name__
    for btn, name in btn_info:
        try:
            if not btn.isEnabled() or not btn.isVisible():
                continue
            QTimer.singleShot(100, lambda: _close_msg_boxes(app))
            btn.click()
            app.processEvents()
            results.append(
                {"page": page_name, "name": name, "status": "OK", "error": None}
            )
        except RuntimeError:
            pass
        except Exception as exc:
            err = traceback.format_exc()
            results.append(
                {
                    "page": page_name,
                    "name": name,
                    "status": "ERROR",
                    "error": str(exc),
                    "traceback": err,
                }
            )

    try:
        page.close()
    except RuntimeError:
        pass
    app.processEvents()
    return results


def is_seh_returncode(returncode: int | None) -> bool:
    if returncode is None:
        return False
    return int(returncode) in SEH_RETURN_CODES


def build_report_markdown(
    page_runs: list[dict[str, Any]],
    *,
    isolation_mode: str = "subprocess-per-page",
    orchestrator_failed: bool = False,
) -> str:
    all_results: list[dict[str, Any]] = []
    seh_pages: list[str] = []
    structural_pages: list[str] = []
    error_pages: list[str] = []
    for run in page_runs:
        page_key = str(run.get("page_key", ""))
        if run.get("exit") == "seh":
            seh_pages.append(page_key)
            continue
        if run.get("exit") == "error":
            error_pages.append(page_key)
            continue
        if run.get("structural_only"):
            structural_pages.append(page_key)
            continue
        all_results.extend(run.get("results") or [])

    errors = [row for row in all_results if row.get("status") == "ERROR"]
    lines = [
        "# UI 按鍵功能稽核報告",
        "",
    ]
    if orchestrator_failed or seh_pages or error_pages:
        lines.extend(
            [
                "> **orchestrator_status: FAILED** — 部分頁面 worker 失敗或 SEH；"
                "下方通過頁面結果仍保留供診斷。",
                "",
            ]
        )
    lines.extend(
        [
        "此報告記錄了在一次性測試資料庫環境中，模擬點擊所有主要介面與模組中所有按鍵的結果。",
        "",
        "## 總覽",
        f"- 隔離模式: {isolation_mode}",
        f"- 測試頁面數: {len(page_runs)}",
        f"- 測試按鍵總數: {len(all_results)}",
        f"- 異常數量: {len(errors)}",
        f"- SEH 崩潰頁面數: {len(seh_pages)}",
        f"- Worker 錯誤頁面數: {len(error_pages)}",
        f"- 結構驗證頁面數 (略過按鍵點擊): {len(structural_pages)}",
        "",
        ]
    )
    if structural_pages:
        lines.append("## 結構驗證頁面 (略過按鍵點擊)")
        lines.append("")
        for page_key in structural_pages:
            lines.append(f"- `{page_key}`")
        lines.append("")
    if seh_pages:
        lines.append("## SEH 崩潰頁面")
        lines.append("")
        for page_key in seh_pages:
            lines.append(f"- `{page_key}`")
        lines.append("")
    if error_pages:
        lines.append("## Worker 錯誤頁面")
        lines.append("")
        for page_key in error_pages:
            lines.append(f"- `{page_key}`")
        lines.append("")
    if errors:
        lines.append("## 異常按鍵列表")
        lines.append("")
        for row in errors:
            lines.append(f"### `[{row['page']}] {row['name']}`")
            lines.append(f"- **錯誤訊息**: `{row['error']}`")
            lines.append(f"- **堆疊追蹤**:\n```python\n{row['traceback']}\n```\n")
    elif not seh_pages and not error_pages:
        lines.append("## 恭喜，未發現異常按鍵！")
    return "\n".join(lines) + "\n"


def write_report(
    page_runs: list[dict[str, Any]],
    report_path: Path | None = None,
    *,
    orchestrator_failed: bool = False,
) -> Path:
    target = report_path or (REPO_ROOT / "scratch" / "button_audit_report.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        build_report_markdown(
            page_runs,
            orchestrator_failed=orchestrator_failed,
        ),
        encoding="utf-8",
    )
    return target


def run_worker(page_key: str, *, child_process: bool = False) -> dict[str, Any]:
    if page_key not in PAGE_KEYS:
        raise KeyError(f"Unknown page key: {page_key}")

    _configure_audit_environment()
    if not child_process and not os.environ.get("SQE_DB_PATH"):
        _prepare_disposable_database()

    from database.connection import initialize_database
    from PySide6.QtWidgets import QApplication

    initialize_database()
    app = QApplication.instance() or QApplication(sys.argv)
    page = create_page(page_key)
    if page_key in STRUCTURAL_ONLY_PAGE_KEYS:
        from PySide6.QtWidgets import QWidget

        if isinstance(page, QWidget):
            page.show()
            app.processEvents()
            try:
                page.close()
            except RuntimeError:
                pass
            app.processEvents()
        _cleanup_top_level_widgets(app)
        return {
            "page_key": page_key,
            "results": [],
            "exit": "ok",
            "structural_only": True,
        }
    results = audit_page_buttons(page, app)
    _cleanup_top_level_widgets(app)
    return {
        "page_key": page_key,
        "results": results,
        "exit": "ok",
    }


def run_orchestrator(
    *,
    python_executable: str | None = None,
    report_path: Path | None = None,
    page_keys: tuple[str, ...] | None = None,
    subprocess_runner: Callable[..., Any] | None = None,
) -> int:
    _prepare_disposable_database()
    db_path = os.environ.get("SQE_DB_PATH", "")
    runner = subprocess_runner or subprocess.run
    script = str(Path(__file__).resolve())
    python = python_executable or sys.executable
    keys = page_keys or PAGE_KEYS
    page_runs: list[dict[str, Any]] = []
    failed = False

    for page_key in keys:
        env = os.environ.copy()
        env["SQE_DB_PATH"] = db_path
        env["SQE_BUTTON_AUDIT_CHILD"] = "1"
        env.setdefault("PYTHONIOENCODING", "utf-8")
        completed = runner(
            [python, script, "--page", page_key, "--child"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
        returncode = getattr(completed, "returncode", None)
        if is_seh_returncode(returncode):
            page_runs.append({"page_key": page_key, "results": [], "exit": "seh"})
            failed = True
            continue
        if returncode != 0:
            stderr = getattr(completed, "stderr", "") or ""
            page_runs.append(
                {
                    "page_key": page_key,
                    "results": [],
                    "exit": "error",
                    "error": stderr.strip() or f"worker exit {returncode}",
                }
            )
            failed = True
            continue
        stdout = (getattr(completed, "stdout", "") or "").strip()
        if not stdout:
            page_runs.append(
                {
                    "page_key": page_key,
                    "results": [],
                    "exit": "error",
                    "error": "empty worker stdout",
                }
            )
            failed = True
            continue
        payload = json.loads(stdout)
        page_runs.append(payload)
        if payload.get("exit") != "ok":
            failed = True
        if any(row.get("status") == "ERROR" for row in payload.get("results") or []):
            failed = True

    write_report(page_runs, report_path=report_path, orchestrator_failed=failed)
    return 1 if failed else 0


def _ensure_utf8_stdout() -> None:
    """Avoid cp950 UnicodeEncodeError when worker JSON includes UI glyphs."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def _emit_json_line(payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False)
    sys.stdout.buffer.write(line.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UI button audit (subprocess-isolated).")
    parser.add_argument("--page", choices=PAGE_KEYS, help="Audit a single page (worker mode).")
    parser.add_argument(
        "--child",
        action="store_true",
        help="Worker invoked by orchestrator; reuse parent SQE_DB_PATH.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional report path (orchestrator mode).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdout()
    args = _parse_args(argv)
    if args.page:
        payload = run_worker(args.page, child_process=args.child)
        _emit_json_line(payload)
        has_errors = any(row.get("status") == "ERROR" for row in payload.get("results") or [])
        return 1 if has_errors else 0
    return run_orchestrator(report_path=args.report)


if __name__ == "__main__":
    raise SystemExit(main())
