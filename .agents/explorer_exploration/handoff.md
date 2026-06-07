# Handoff Report — 2026-06-07T05:11:16Z

## 1. 觀察結果 (Observation)
透過對 `src/` 與 `tests/` 的全面靜態程式碼檢索，我們觀察到以下關鍵代碼片段與連線建立模式：

1. **`src/database/migration.py` 的檔案遷移連線**（第 94 與 124 行）：
   ```python
   with sqlite3.connect(v2_path) as v2_conn:
       ...
       with sqlite3.connect(legacy_path) as legacy_conn:
   ```
   此處直接使用 Python 標準庫 `sqlite3` 的 context manager 模式開啟連線。

2. **`src/database/connection.py` 的連線工廠**（第 26-32 行）：
   ```python
   def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
       """Create SQLite connection with row mapping and foreign key support."""
       target = db_path or DB_PATH
       conn = sqlite3.connect(target)
       conn.row_factory = sqlite3.Row
       conn.execute("PRAGMA foreign_keys=ON")
       return conn
   ```
   此處建立並返回標準的 `sqlite3.Connection` 對象。

3. **Service 層與 UI 層的廣泛呼叫**：
   在 `src/services/event_service.py` 及多個 UI widget（如 `HomeWidget`, `StatsViewWidget`）中，有高達 49 處呼叫：
   ```python
   with get_connection() as conn:
   ```
   這代表每次執行業務邏輯或刷新畫面時，都會經歷一次連線建立。

4. **`src/database/ncr_migration.py` 的異常清理機制**（第 135-142 行）：
   ```python
   try:
       src_conn = _connect_source(ncr_db_path)
   except sqlite3.Error as exc:
       ...
       return report
   try:
       ...
   finally:
       src_conn.close()
   ```
   此處的 `src_conn` 建立與 `finally` 清理區塊分立，若在兩者之間拋出非 `sqlite3.Error` 之異常，可能導致 `UnboundLocalError` 或資源洩漏。

5. **測試套件程式碼 (`tests/` 內 12 個測試檔案)**：
   包含 `test_anomaly_no_recode.py` 等，皆在 `setUp` 中建立連線，並在 `tearDown` 或 `finally` 區塊中顯式呼叫了 `self.conn.close()` 或 `conn.close()`，測試清理邏輯齊全。

6. **自動化驗證執行權限受限**：
   在執行 `python -m pytest -Wd -v` 時，終端機回報需要使用者授權逾時：
   > `Encountered error in step execution: Permission prompt for action 'command' on target 'python -m pytest -Wd -v' timed out waiting for user response.`

---

## 2. 推導邏輯 (Logic Chain)
基於上述觀察，推導過程如下：

1. **前提**：Python 的 `sqlite3.Connection` 的 context manager 協議（`__exit__` 方法）在結束時**只會執行事務的 commit/rollback**，並不會呼叫 `.close()` 關閉資料庫實體連線。
2. **推論一（Service 與 UI 層洩漏）**：由【觀察結果 2】與【觀察結果 3】，由於 `get_connection()` 返回的是標準 `sqlite3.Connection`，因此這 49 處 `with get_connection() as conn:` 退出後連線皆處於未關閉狀態，並在 GC 發生時觸發 `ResourceWarning: unclosed database connection`。
3. **推論二（Migration 模組洩漏）**：由【觀察結果 1】，`migrate_legacy_data_if_needed` 在運行時同樣使用了 `with sqlite3.connect`，導致兩個資料庫檔案連線在遷移結束後未關閉，同樣會引發資源警告。
4. **推論三（修復方案之最優選）**：若逐一修改業務邏輯中的 49 處 context manager 改為手動 close 或 wrap，會導致大量檔案變更，違反 Minimal Blast Radius 原則。因此，最優解決方案是在 `get_connection` 的 `sqlite3.connect` 中傳入自訂的 `factory=ClosingConnection` 類別，在 context manager 退出時自動關閉連線。

---

## 3. 注意事項 (Caveats)
* 本次調查因使用者環境權限提示逾時，未能在本輪次完成 `pytest` 指令的實機輸出捕捉，但所有分析均已透過對原始碼細緻的靜態分析完成。
* 修改 `get_connection` 返回自定義連線類別 `ClosingConnection` 後，若在單元測試或 UI 實體中存在「複用已被 exit 的連線對象」之行為，可能會因為連線已關閉而報錯。然而，經檢索【觀察結果 3】，所有的連線調用均是獨立的 `with get_connection() as conn:`，並未發現傳遞已被 exit 連線的行為，故該改動風險極低，但實作時仍應予以注意。

---

## 4. 結論 (Conclusion)
為解決 `ResourceWarning` 警告，建議實作者採取以下變更：
* **變更一**：在 `src/database/connection.py` 宣告 `ClosingConnection(sqlite3.Connection)` 並重寫 `__exit__` 以確實執行 `self.close()`，同時在 `get_connection` 內套用此 class factory。
* **變更二**：重構 `src/database/migration.py` 的 `migrate_legacy_data_if_needed` 函數，將雙層 `with sqlite3.connect` 改為顯式的 `try...finally`，確保連線確實被 close。
* **變更三**：優化 `src/database/ncr_migration.py` 中的 `migrate_ncr_data_once` 異常安全性，確保 `src_conn` 的生命週期在單一 try-finally 下安全管理。

詳細的程式碼 Diff 與修復指南，已寫入本目錄下的分析報告 [analysis.md](file:///c:/Users/user/Documents/SQE%20DailyWork/.agents/explorer_exploration/analysis.md)。

---

## 5. 獨立驗證方法 (Verification Method)
實作人員在套用修改後，可使用以下步驟獨立驗證：
1. **執行專案測試套件並開啟警告過濾**：
   ```powershell
   python -Wd -m pytest
   ```
   確認所有 278 個測試皆通過且無 `ResourceWarning` 輸出。
2. **執行管線驗證腳本**：
   ```powershell
   .\scripts\verify.ps1
   ```
   確認管線無報錯。
3. **無效化條件 (Invalidation conditions)**：若在單元測試過程中出現 `sqlite3.ProgrammingError: Cannot operate on a closed database.`，表示有部分代碼在 Exit Context 後重用了該 Connection 對象，須對該處進行排除。
