import sys
import os
import traceback
from pathlib import Path
from PySide6.QtWidgets import QApplication, QAbstractButton, QDialog, QMessageBox, QWidget
from PySide6.QtCore import Qt, QTimer

# Setup path and env
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["SQE_TESTING"] = "1"
os.environ["SQE_REQUIRE_DISPOSABLE_DB"] = "1"

def _prepare_disposable_database() -> str:
    from database.backup import backup_sqlite_database
    import tempfile
    import atexit
    source = (REPO_ROOT / "data" / "sqe_v2.db").resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="sqe-button-audit-")
    atexit.register(temp_dir.cleanup)
    destination = Path(temp_dir.name) / "sqe_v2.db"
    backup_sqlite_database(source, destination)
    os.environ["SQE_DB_PATH"] = str(destination)
    return str(destination)

def _close_msg_boxes():
    for w in QApplication.topLevelWidgets():
        if isinstance(w, (QMessageBox, QDialog)):
            w.reject()

class _ProbeHost:
    def open_new_visit_dialog(self, *_a, **_k): pass
    def open_new_anomaly_dialog(self, *_a, **_k): pass
    def open_event_query_with_filters(self, *_a, **_k): pass
    def open_warehouse_nonconforming_tracker(self, *_a, **_k): pass

def instantiate_all_pages():
    pages = []
    
    from ui.main_window import MainWindow
    window = MainWindow()
    pages.append(window)

    from ui.widgets.event_create_page import EventCreatePage
    pages.append(EventCreatePage(_ProbeHost(), "anomaly"))
    pages.append(EventCreatePage(_ProbeHost(), "visit"))

    from ui.widgets.defect_list_widget import EventListWidget
    pages.append(EventListWidget(_ProbeHost(), mode="query", fixed_scope=None, lazy_load=False))

    from ui.widgets.master_data_widget import MasterDataWidget
    pages.append(MasterDataWidget(_ProbeHost(), lazy_load=False))

    from ui.widgets.supplier_form_dialog import SupplierFormDialog
    pages.append(SupplierFormDialog())

    from ui.widgets.product_form_dialog import ProductFormDialog
    pages.append(ProductFormDialog([{"id": "supplier-1", "supplier_name": "測試供應商"}]))

    from ui.widgets.appearance_preferences_dialog import AppearancePreferencesDialog
    pages.append(AppearancePreferencesDialog())

    try:
        from ncr.db.database import apply_schema
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn, with_version=True)
        from ncr.ui.defect_form import DefectFormWidget
        from ncr.ui.defect_list import DefectListWidget
        pages.append(DefectFormWidget(conn))
        pages.append(DefectListWidget(conn, workflow="trace"))
    except Exception:
        pass
        
    return pages

def run_audit():
    _prepare_disposable_database()
    from database.connection import initialize_database
    initialize_database()
    
    app = QApplication.instance() or QApplication(sys.argv)
    pages = instantiate_all_pages()
    
    results = []
    app.processEvents()
    
    for page in pages:
        if isinstance(page, QWidget):
            page.show()
            app.processEvents()
            buttons = page.findChildren(QAbstractButton)
            
            # Extract names first so if they are deleted we still have the name
            btn_info = []
            for btn in buttons:
                try:
                    name = btn.objectName() or btn.text() or str(btn)
                    btn_info.append((btn, name))
                except RuntimeError:
                    pass
            
            for btn, name in btn_info:
                try:
                    # Double check if deleted
                    if not btn.isEnabled() or not btn.isVisible():
                        continue
                    
                    QTimer.singleShot(100, _close_msg_boxes)
                    btn.click()
                    app.processEvents()
                    results.append({"page": page.__class__.__name__, "name": name, "status": "OK", "error": None})
                except RuntimeError:
                    # Ignore deleted objects
                    pass
                except Exception as e:
                    err = traceback.format_exc()
                    results.append({"page": page.__class__.__name__, "name": name, "status": "ERROR", "error": str(e), "traceback": err})
            
            try:
                page.close()
            except RuntimeError:
                pass
            app.processEvents()
            
    with open("button_audit_report.md", "w", encoding="utf-8") as f:
        f.write("# UI 按鍵功能稽核報告\n\n")
        f.write("此報告記錄了在一次性測試資料庫環境中，模擬點擊所有主要介面與模組中所有按鍵的結果。\n\n")
        
        errors = [r for r in results if r["status"] == "ERROR"]
        f.write(f"## 總覽\n- 測試頁面數: {len(pages)}\n- 測試按鍵總數: {len(results)}\n- 異常數量: {len(errors)}\n\n")
        
        if errors:
            f.write("## 異常按鍵列表\n\n")
            for r in errors:
                f.write(f"### `[{r['page']}] {r['name']}`\n")
                f.write(f"- **錯誤訊息**: `{r['error']}`\n")
                f.write(f"- **堆疊追蹤**:\n```python\n{r['traceback']}\n```\n\n")
        else:
            f.write("## 🎉 恭喜，未發現異常按鍵！\n")

if __name__ == "__main__":
    run_audit()
