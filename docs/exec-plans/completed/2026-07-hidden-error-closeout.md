# 2026-07 隱藏錯誤量產收斂計畫

Plan status: completed — ready with exception

## Contract

- Done: 已確認的 P1 與使用者可感知 P2 有根因修正與回歸測試；正式資料庫只讀，所有初始化、migration、視覺與匯出驗證使用拋棄式快照。
- Output: 程式、測試、文件、harness、原生 Qt 證據，以及 `Outputs/audit/` 下唯一不可自動判定資料列的 `VERIFY` CSV。
- Non-goals: 不改統計公式、不合併供應商事件與倉庫 NCR、不執行正式庫 migration、不自動修正正式資料、不 commit/push/deploy。
- Scope: SQLite 備份與路徑隔離、交易/migration、異常與匯入契約、Excel/圖表語意、Qt 視覺與 probe、文件與 repo membership。

## Phase 0 baseline

- Branch/commit: `main` / `b30ee68ed19e9c5ef572fd62b920264f8e2083ac`。
- Source DB: `data/sqe_v2.db`，唯讀 `integrity_check=ok`，14 tables、246 rows。
- Disposable snapshot: `scratch/hidden-error-closeout/phase0-safety-snapshot.db`，由 SQLite online backup 建立。
- Snapshot parity: table counts equal、`integrity_check=ok`；來源檔 size/mtime/SHA-256 在備份前後不變。
- Worktree gate before implementation: clean。

## Finding register

| ID | Severity | Category | Evidence / root cause | Required gate | Status |
| --- | --- | --- | --- | --- | --- |
| A1 | P1 | A | WAL DB 以 raw copy 備份會遺漏已提交 WAL 頁 | WAL restore probe | resolved |
| A2 | P1 | A | verify/tests/probe 可在預設路徑執行 `initialize_database()` | live-path fail-fast + temp DB | resolved |
| A3 | P1 | A | 異常 mutation 在月快取與 Markdown 前先 commit，失敗會顯示整體失敗並誘發重試 | failure injection | resolved |
| A4 | P1 | A | legacy migration 逐筆吞錯後仍寫完成 metadata | rollback/reconciliation probe | resolved |
| A5 | P1 | A | 正式 theme 擴張 `QDateEdit`，異常表單水平溢出 96px | themed layout test | resolved |
| A6 | P1 | A/C | probe 輸出與 baseline manifest 漂移；缺 baseline 被跳過成功 | manifest/baseline gate | resolved |
| A7 | P2 | A | 產品匯入忽略 stage 差異，查重鍵未包含 supplier | import conflict tests | resolved |
| A8 | P2 | A | 異常單號與 anomaly/visit supplier invariant 未在 repository 全路徑執行 | repository tests | resolved |
| A9 | P2 | A | 反向日期區間產生偽資料 | range validation tests | resolved |
| A10 | P2 | A | 圖表輸出錯誤被吞，UI 仍顯示完全成功 | partial-export tests | resolved |
| A11 | P2 | A | Excel 混用建立 cohort 與 `closed_at` 活動口徑 | workbook parity tests | resolved |
| A12 | P2 | A | Qt message handler 的 enum 比較把 Debug/Info 也寫入 | log filter test | resolved |
| A13 | P2 | A/C | Phase 0 與結案的正式庫業務列一致，但 raw hash 不同；差異只在兩筆衍生月快取 `updated_at` 且結案值較早，來源無法由現有證據唯一判定 | read-only row parity + current hash stability | accepted residual; no live write |
| C1 | P2 | C | README/UI contract/inline comments、active plan、source baseline 漂移 | harness live checks | resolved |
| C2 | P2 | C | 生成 Excel 與 `.playwright-mcp` 狀態檔仍受追蹤 | tracked membership gate | resolved |
| D1 | P3 | D | NCR defect list 重複匯入欄位持久化 helper | definite Ruff | resolved |
| E1 | P3 | E | 無量測支持的效能問題 | none | no supported finding |

## Gates

1. Safety: online backup 能保存未 checkpoint WAL；正式庫前後 hash/mtime/counts 不變。
2. Transaction/migration: cache failure rollback；snapshot failure 只產生 warning；migration error 無半套資料與完成 metadata。
3. Contract: anomaly number、supplier invariant、stage conflict、reverse range、cross-month closure、partial chart export 全綠。
4. Visual: container scan 有明確決策；正式 theme 水平 scrollbar maximum=0；所有 manifest targets 在 Windows Qt 100/125/150% 通過。
5. Harness/docs: live tracked membership、do-not-track、active plan 與 target/baseline mapping 可重現並攔截漂移。
6. Closeout: compileall、definite Ruff、完整 unittest、offscreen structural smoke、native visual belt、visual regress、harness、正式庫唯讀 parity 通過；無未處理 P0/P1。

## Rollback

- 正式資料不在本任務中寫入或 migration；若任何 gate 偵測來源 DB 變更，立即停止並使用 Phase 0 驗證快照比對，未經使用者核准不還原正式庫。
- 程式變更可按 phase 的檔案 diff 回復；不使用 destructive Git 指令。
- UI helper/theme 若造成回歸，回復該 helper/尺寸策略，保留資料層修正。

## Final state

- `scripts/verify.ps1 -Profile Focused`：pass；完整 unittest 434 tests pass（901.780s），offscreen structural smoke pass。
- Native visual belt：Windows Qt 100% / 125% / 150%，28/28 pass；九個 required targets 的 pixel regress 全數 pass；harness pass。
- Definite-error Ruff、compileall、`git diff --check`：pass；結構化品質掃描只回報已知 broad-exception 邊界，新增路徑均為 rollback/re-raise 或明確 post-commit warning，無未處理 P0/P1。
- 正式庫結案唯讀檢查：`integrity_check=ok`、14 tables、246 rows；所有業務資料列與 Phase 0 快照一致。raw hash 的 A13 差異保留為不寫入的證據例外。
- 唯一 supplier/product 歸屬不一致資料已輸出 `Outputs/audit/supplier_product_ownership_VERIFY_20260714.csv`，未自動修改。
- 最終狀態：`ready with exception`；使用者完成該列歸屬分類前不升為完全 `ready`。
