# 資料庫連線洩漏調查與分析報告

## 1. 概述
本報告針對 SQE DailyWork 專案在執行單元測試或應用程式啟動時，產生的 `ResourceWarning: unclosed database connection` 進行深入調查。透過靜態程式碼分析，我們定位了主要的資料庫連線洩漏點，其根源在於：
1. **Context Manager 誤區**：`sqlite3.Connection` 的預設 `__exit__` 實作僅處理事務提交（Commit）或回滾（Rollback），**並不會自動關閉連線（close）**。因此，所有使用 `with get_connection() as conn:` 或 `with sqlite3.connect(...) as conn:` 的區塊，在結束時皆會殘留未關閉的連線。
2. **遷移程序連線殘留**：在資料庫初期化與遷移的邏輯中，數個直接呼叫 `sqlite3.connect` 建立的連線未於 `finally` 區塊中確實關閉。
3. **異常處理盲點**：在舊有 NCR 遷移模組中，連線的開啟與清理區塊分割，存在潛在的 `UnboundLocalError` 或連線殘留風險。

---

## 2. 洩漏點定位與根因分析

### 2.1 `src/database/connection.py` 中的 Context Manager 殘留
* **檔案路徑**：`src/database/connection.py` (第 26-32 行)
* **原始程式碼**：
  ```python
  def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
      """Create SQLite connection with row mapping and foreign key support."""
      target = db_path or DB_PATH
      conn = sqlite3.connect(target)
      conn.row_factory = sqlite3.Row
      conn.execute("PRAGMA foreign_keys=ON")
      return conn
  ```
* **根因分析**：
  專案在 `src/services/event_service.py` 與各個 UI 頁面元件中廣泛使用 `with get_connection() as conn:` 模式（約有 49 處）。由於 `sqlite3.Connection` 不會在退出 `with` 區塊時呼叫 `close()`，這些連線在退出區塊後依然保持開啟，直到 Python 進行垃圾回收（GC）時才被動釋放並觸發 `ResourceWarning`。

### 2.2 `src/database/migration.py` 中的 `migrate_legacy_data_if_needed` 洩漏
* **檔案路徑**：`src/database/migration.py` (第 94 與 124 行)
* **原始程式碼**：
  ```python
  def migrate_legacy_data_if_needed(v2_path: Path, legacy_path: Path) -> dict:
      ...
      with sqlite3.connect(v2_path) as v2_conn:
          ...
          with sqlite3.connect(legacy_path) as legacy_conn:
              ...
  ```
* **根因分析**：
  同上，此處直接使用 `with sqlite3.connect(...)` 建立的 `v2_conn` 與 `legacy_conn`。在函數執行完畢返回 `report` 時，兩個連線皆處於未關閉狀態。

### 2.3 `src/database/ncr_migration.py` 中的健全度風險
* **檔案路徑**：`src/database/ncr_migration.py` (第 135-142 行)
* **原始程式碼**：
  ```python
  try:
      src_conn = _connect_source(ncr_db_path)
  except sqlite3.Error as exc:
      report["errors"].append(f"Failed to open source defect.db read-only: {exc}")
      report["target_after"] = report["target_before"]
      return report

  try:
      # 遷移程序
  finally:
      src_conn.close()
  ```
* **根因分析**：
  雖然此處有在 `finally` 中呼叫 `src_conn.close()`，但如果 `_connect_source` 丟出非 `sqlite3.Error` 的異常（例如：`KeyboardInterrupt` 或其他預期外的 `OSError`），由於外層 `except sqlite3.Error` 無法捕捉，程式碼會直接傳播異常而跳過第二個 `try` 區塊，導致連線如果已被部分建立則無法被確實釋放。

---

## 3. 測試套件的連線清理狀態
我們對 `tests/` 和 `src/ncr/tests/` 底下的測試檔案進行了全面檢索，所有顯式使用 `sqlite3.connect` 建立測試用 in-memory 或實體檔案資料庫連線的測試類別，皆有在 `tearDown` 或是測試方法的 `finally` 中確實執行 `self.conn.close()` 或 `conn.close()`。
因此，測試套件本身的連線管理是安全的，無須修改測試套件程式碼，主要的 ResourceWarning 來源即是上述的 Service 層 context manager 以及 Migration 模組。

---

## 4. 具體修復方案

### 方案 A：在 `get_connection` 中引入自關閉連線類別（最推薦，影響最小）
為解決大量 `with get_connection() as conn:` 殘留連線的問題，無須逐一修改 49 處的業務邏輯代碼。我們可以在 `src/database/connection.py` 中宣告一個 `ClosingConnection` 繼承自 `sqlite3.Connection`，並重寫其 `__exit__` 方法。

#### 建議修改內容：
##### 檔案：[MODIFY] `src/database/connection.py`(file:///c:/Users/user/Documents/SQE%20DailyWork/src/database/connection.py)

**修改前**：
```python
def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create SQLite connection with row mapping and foreign key support."""
    target = db_path or DB_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

**修改後**：
```python
class ClosingConnection(sqlite3.Connection):
    """A sqlite3.Connection subclass that guarantees close() is called upon exiting context."""
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create SQLite connection with row mapping and foreign key support."""
    target = db_path or DB_PATH
    conn = sqlite3.connect(target, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

---

### 方案 B：重構 `migrate_legacy_data_if_needed` 的連線管理
將 `src/database/migration.py` 中直接使用 `with sqlite3.connect` 的區塊，改為顯式的 `try...finally` 關閉控制。

#### 建議修改內容：
##### 檔案：[MODIFY] `src/database/migration.py`(file:///c:/Users/user/Documents/SQE%20DailyWork/src/database/migration.py)

**修改前**：
```python
def migrate_legacy_data_if_needed(v2_path: Path, legacy_path: Path) -> dict:
    report: dict[str, Any] = {
        "migrated": False,
        "backup_path": "",
        "counts_before": {},
        "counts_after": {},
        "legacy_counts": {},
        "errors": [],
    }
    with sqlite3.connect(v2_path) as v2_conn:
        v2_conn.row_factory = sqlite3.Row
        ...
        with sqlite3.connect(legacy_path) as legacy_conn:
            ...
```

**修改後**：
```python
def migrate_legacy_data_if_needed(v2_path: Path, legacy_path: Path) -> dict:
    report: dict[str, Any] = {
        "migrated": False,
        "backup_path": "",
        "counts_before": {},
        "counts_after": {},
        "legacy_counts": {},
        "errors": [],
    }
    v2_conn = sqlite3.connect(v2_path)
    try:
        v2_conn.row_factory = sqlite3.Row
        create_schema(v2_conn)
        report["counts_before"] = count_rows(v2_conn)
        if get_migration_meta(v2_conn, "legacy_migrated") == "1":
            return report

        if not legacy_path.exists():
            upsert_migration_meta(v2_conn, "legacy_migrated", "1")
            report["counts_after"] = count_rows(v2_conn)
            return report

        if (
            report["counts_before"]["suppliers"] > 0
            or report["counts_before"].get("products", 0) > 0
            or report["counts_before"]["anomalies"] > 0
            or report["counts_before"]["visits"] > 0
        ):
            upsert_migration_meta(v2_conn, "legacy_migrated", "1")
            report["counts_after"] = count_rows(v2_conn)
            return report

        timestamp = datetime.now().strftime("%Y%m%d")
        backup_path = legacy_path.parent / f"sqe_legacy_{timestamp}.db"
        if not backup_path.exists():
            shutil.copy2(legacy_path, backup_path)
        report["backup_path"] = str(backup_path)

        legacy_conn = sqlite3.connect(legacy_path)
        try:
            legacy_conn.row_factory = sqlite3.Row
            _migrate_suppliers(legacy_conn, v2_conn, report)
            _migrate_anomalies(legacy_conn, v2_conn, report)
            _migrate_visits(legacy_conn, v2_conn, report)
        finally:
            legacy_conn.close()

        rebuild_all_monthly_cache(v2_conn)
        upsert_migration_meta(v2_conn, "legacy_migrated", "1")
        report["counts_after"] = count_rows(v2_conn)
        report["migrated"] = True
    finally:
        v2_conn.close()
    return report
```

---

### 方案 C：優化 `migrate_ncr_data_once` 異常安全性
將 `src/database/ncr_migration.py` 的雙重 try 區塊整合，宣告初始變數確保連線被正確清理。

#### 建議修改內容：
##### 檔案：[MODIFY] `src/database/ncr_migration.py`(file:///c:/Users/user/Documents/SQE%20DailyWork/src/database/ncr_migration.py)

**修改前**：
```python
    try:
        src_conn = _connect_source(ncr_db_path)
    except sqlite3.Error as exc:
        report["errors"].append(f"Failed to open source defect.db read-only: {exc}")
        report["target_after"] = report["target_before"]
        return report

    try:
        src_suppliers = src_conn.execute(
        ...
    finally:
        src_conn.close()
```

**修改后**：
```python
    src_conn = None
    try:
        try:
            src_conn = _connect_source(ncr_db_path)
        except sqlite3.Error as exc:
            report["errors"].append(f"Failed to open source defect.db read-only: {exc}")
            report["target_after"] = report["target_before"]
            return report

        src_suppliers = src_conn.execute(
        ...
    finally:
        if src_conn is not None:
            src_conn.close()
```

---

## 5. 驗證與測試計畫
實作人員在套用上述修改後，應執行以下驗證步驟以確保所有功能皆運作正常且連線洩漏警告完全消失：

1. **執行全套單元測試並啟用警告過濾**：
   ```powershell
   python -Wd -m pytest
   ```
   * 預期結果：278 個測試案例應全部通過，且終端機中不應出現任何 `ResourceWarning: unclosed database connection`。

2. **執行專案驗證腳本**：
   ```powershell
   .\scripts\verify.ps1
   ```
   * 預期結果：驗證管線順利執行完畢且無報錯。

3. **啟動 GUI 冒煙測試**：
   * 預期結果：能正常啟動 SQE DailyWork 介面，在不同頁面間切換，並成功關閉視窗而不拋出未釋放資源異常。
