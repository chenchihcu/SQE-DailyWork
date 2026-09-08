# 003#發行阻斷修正

Plan status: completed

Completed: 2026-09-07

Spec status: APPROVED

## Problem statement

目前 release evidence 有三項可在不觸及正式資料庫與發行產物的前提下修正的阻斷：

- 建置所用 `.venv` 的 Pillow 為 12.2.0，低於已知 High advisory 的修補版本 12.3.0。
- `master-data` 視覺 probe patch 了 facade，實際 widget 則使用 event 子模組，導致正式資料進入原應固定的 fixture capture。
- root-level `-e` 暫存檔使 release membership 與 source baseline manifest 不一致。
- Full native regression 額外揭露 `empty-states` 的 Master Data capture 同樣只 patch facade，因而錯把正式資料當成空狀態 evidence。
- 修正 capture seam 後，畫面雖正確顯示 0 筆，卻揭露 Master Data 真的會將空集合呈現為沒有文字的空白表格，違反既有四態 UI 契約。
- Native Windows read-back 額外顯示 Master Data 首次載入會讓搜尋欄取得焦點；在目前主機的可及性 caret 寬度下，會在尚未操作的首屏顯示一個寬文字游標。
- Master Data populated-fixture probe 未固定原生游標位置；工作站游標可觸發 `QTableWidget::item:hover`，使同一 fixture 的 visual capture 不穩定。

## Goal

讓上述三項 blocker 在 source／harness 層面 fail-closed 並有回歸測試；重新取得可重複的 native Windows master-data visual evidence。這不是正式 cutover 或 artifact promotion。

## Facts

- 2026-09-05 重現：`Pillow 12.2.0`；`services.event_service` facade patch 成功，但 `MasterDataWidget` 實際 service call 未被替換。
- 2026-09-05 重現：native `master-data @ 1.0` pixel regression 失敗，raw supplier ratio `0.0140544218`、outsource ratio `0.1823521334`。
- `-e` 是 repo root 的 30-byte untracked text file；live membership 因此為 710，manifest 預期值為 709。
- 2026-09-05 修正後：同一 native Windows 環境的 fixture candidate 於 1.0 DPI 重複 capture，四張對應 PNG 的 pixel ratio 都是 `0.0`；三個 DPI 的 fixture provenance 均為 `master-data-stress-v1` / `0791f9bc…e34e`。
- 2026-09-05：既有 12 張已登錄 master-data PNG 與 candidate 的 pixel ratio 為 `0.0355` 至 `0.1972`，皆高於 `0.001`；畫面幾何一致。root `-e` 的精確刪除遭本機刪除 guard 拒絕，未刪除、未繞過。
- 2026-09-05：read-back 中的 shell 搜尋誤產生 root `12.3.0`（17 bytes，內容僅為 `7:Pillow>=12.3.0`，SHA-256 `AC770E…5394`）；精確刪除同樣遭 guard 拒絕。此為本次作業的 accidental temporary file，不是使用者來源檔。
- 2026-09-05：使用者已確認 `-e` 與 `12.3.0` 均已移除；live membership read-back 為 `711`。
- 2026-09-05：使用者明確核准以 `master-data-stress-v1` candidate promotion 目前已登錄的 12 張 Master Data baseline PNG，以及更新 `baseline_manifest.json` fixture provenance；不調高 tolerance、不刪除六張未登錄歷史 PNG。
- 2026-09-05：Full 的 `empty-states @1.0` 在 `empty-states_empty-master.png` 失敗，ratio 為 `0.0027677648207720586`（tolerance `0.001`）；視覺 read-back 證實 baseline 與 candidate 都呈現 live supplier rows，而非空狀態，僅因 live row category/contact 資料不同而出現 diff。
- 2026-09-05：RCA 已證實 `MasterDataWidget` 的 `refresh_data()` 呼叫 `ui.widgets.master_data_widget._supplier_service`／`_product_service`，不是 `_capture_empty_states()` 所 patch 的 `services.event_service` facade。
- 2026-09-05：修正 capture seam 的 native candidate 已由 Full 產生；Master Data 確實為 0 筆，但只見 headers、空白 table surface 和 pagination。`docs/SQE_Incident_Management_UI_Design_Framework_v0.1.md` §3.5／§7.7 要求空狀態不得留白，必須使用 `EmptyStateWidget` 提供明確文案與建議動作。
- 2026-09-06：native focus diagnostic 證實黑色方塊不是 CJK glyph 或滑鼠游標：QLineEdit 有 focus 且游標移到空白區時仍存在；`PM_TextCursorWidth = 10`、DPR `2.0`、cursor rect 為 `19×18`。這是系統／可及性寬文字游標，不能由應用程式覆寫。修正為首次顯示聚焦 keyboard-focusable page root；使用者明確按「篩選」或點擊輸入欄時仍保留原本的搜尋焦點與系統 caret 行為。
- 2026-09-06：修正後的 Full 於隔離資料庫通過編譯、497 項 Windows-safe unit tests（1118.921s）、42 項 NCR tests、13 項 pytest、offscreen structural smoke、native probe belt，以及 master-data 與先行 visual target 三 DPI regression；但 `empty-states@1.5x_empty-master.png` 以嚴格 tolerance `0.001` 失敗，ratio 為 `0.001025186397526823`。1.0／1.25 候選 ratio 分別為 `0.000720214843750`／`0.000786633613782`，仍在 tolerance 內，三者幾何皆一致。
- 2026-09-06：native read-back 與 diff 證實唯一超限區域是 baseline 的系統寬文字游標；修正後 candidate 不會在未操作的首屏自動聚焦搜尋欄。此為視覺正確性改善，但 Empty States manifest 與三張 `empty-master` PNG 尚未取得獨立 promotion 核准，維持凍結，沒有調高 tolerance。
- 2026-09-06：以 `qt_visual_probe.py --target empty-states --scale 1.5` 進行第二次 native Windows repeat capture，`visual_trustworthy=true`、font 為 `Microsoft JhengHei UI`，fixture provenance 為相同的 `empty-states-v1`。重複 candidate 與 Full candidate 的 QImage pixel ratio 為 `0.0`，SHA-256 均為 `147a2726d0ae792a2ab0146a75fb14356b213af1c1a89e70216b029a0ff2bcb7`；相對目前 1.5x baseline 的 ratio 仍為 `0.001025186397527`。差異為可重複的產品修正，不是單次渲染波動。
- 2026-09-07：使用者獨立核准保留 `empty-states-v1` provenance，並升版恰好三張 `empty-master` PNG；明確排除六張 `empty-event-list`／`empty-ncr-placeholder` PNG，不調高 `0.001` tolerance、不觸及正式 DB。
- 2026-09-07：以固定三檔 allowlist 的 dry-run 驗證三張 candidate、manifest provenance 與排除清單後升版；回滾副本為 `scratch/empty-states-baseline-promotion-backup-093234872f384ac4a53889b01f4686b2`。三張 baseline SHA-256 均等於 fresh native candidate，manifest 與備份相同，Empty States native regression 在 1.0／1.25／1.5 DPI 均 PASS。
- 2026-09-07：Master Data regression 曾於三 DPI 失敗；失敗差異全部落在資料列 hover 區域（例如 1.0 raw supplier `x=1270–1627, y=710–765`），與 `QTableWidget::item:hover` 的背景樣式相符。probe 原本沒有固定 cursor 或清除 hover。
- 2026-09-07：修正 probe 後，兩次獨立 native 三 DPI capture 的 12 張 Master Data candidate `repeat_max_ratio=0`、幾何全同；現有 baseline 的每張差異皆低於 `0.001`，不需再寫入 Master Data baseline。正式 master-data regression 1.0／1.25／1.5 DPI 均 PASS。

## Inferences

- 「修正 patch seam 後既有 master-data PNG 仍可直接沿用」的初始假設，已由 candidate pixel evidence 否定；必須以人工作圖審閱決定是否 promotion，不能直接覆寫 PNG。
- Pillow floor 必須由 verification 與 packaging 入口各自 fail-closed，避免有人以舊 `.venv` 建置。
- 既有 master-data baseline 是不同資料契約的證據，不能與 deterministic fixture 混用；若要替換 12 張已登錄 PNG，必須有獨立的人工作圖審閱與明確 promotion 核准。
- Native visual probe 必須中和工作站游標的 hover 狀態；否則實際產品畫面未變，也能讓 populated-table baseline 產生不可重複的差異。

## Unknowns

- 現存或歷史 zip artifact 的可用 rollback chain 不在本次 scope；不得用這份修正假稱 release-ready。
- Authenticode signing、正式 DB backup/cutover、人工 supplier/product ownership 分類需另行授權。
- baseline promotion 已獲使用者核准，但必須先產生精確 pre-promotion backup，並以 native 三 DPI regression、fixture provenance 與 diff review 驗收；不得以 tolerance 變更掩蓋差異。
- Empty States 已取得獨立、精確的 promotion 核准並完成升版；這不延伸或改寫 Master Data 的授權範圍。

## Scope

### Allowed changes

- `requirements.txt`
- `scripts/assert_runtime_dependency_floor.py`
- `scripts/verify.ps1`
- `scripts/build_windows.ps1`
- `scripts/qt_visual_probe.py`
- `scripts/qt_visual_regress.py`
- `src/ui/widgets/master_data_widget.py`
- `src/ui/widgets/master_data_supplier_mixin.py`
- `src/ui/widgets/master_data_product_mixin.py`
- `tests/test_audit_formal_db_promotion_status.py`
- `tests/test_qt_visual_probe_popup_wait.py`
- `tests/test_master_data_query_behavior.py`
- `tests/visual_baseline/master-data/baseline_manifest.json`
- exactly these 12 registered files under `tests/visual_baseline/master-data/`: `master-data_master-raw-supplier.png`, `master-data_master-outsource-supplier.png`, `master-data_master-raw-material.png`, `master-data_master-semi-finished.png`, and their `@1.25x_` / `@1.5x_` counterparts
- `tests/visual_baseline/empty-states/baseline_manifest.json`
- exactly these three files under `tests/visual_baseline/empty-states/`: `empty-states_empty-master.png`, `empty-states@1.25x_empty-master.png`, `empty-states@1.5x_empty-master.png`
- `docs/harness/source-baseline-manifest.md`
- `docs/harness/closed-loop-log.md`
- `docs/ui-layout-theme-contract.md`
- this plan, then its move to `docs/exec-plans/completed/` when complete
- the exact root file `C:\Users\user\Documents\SQE DailyWork\-e` after pre-delete read-back
- the accidental exact root file `C:\Users\user\Documents\SQE DailyWork\12.3.0` after pre-delete read-back

### Forbidden changes

- `data/`, `data_backups/`, any migration/schema or formal SQLite write
- all visual baseline PNG replacement outside the 12 explicitly approved Master Data files and three independently approved Empty States `empty-master` files, any tolerance increase, or deletion of the six unregistered historical Master Data PNGs
- `dist/`, release summary promotion, portable distribution publication, signing, commit, push, or branch mutation
- 除已驗證的 Master Data 空狀態與初始焦點修正外的產品 workflow／UI 行為

## Acceptance criteria

- `requirements.txt` requires Pillow at least 12.3.0; the active `.venv` uses a version at or above that floor.
- A deterministic runtime-floor helper fails for a vulnerable or prerelease Pillow version and passes for stable 12.3.0 or newer; `verify.ps1` and `build_windows.ps1` invoke it before their substantive work.
- The master-data probe patches the exact module objects consumed by `MasterDataWidget`; a regression test proves the replacement.
- The empty-states Master Data capture patches the same widget-owned services and has a regression test proving that live supplier/product rows cannot leak into its empty-state evidence.
- The `empty-states` capture records a deterministic fixture provenance, and regression refuses to compare it against a baseline that lacks the same fixture contract.
- Supplier and product Master Data pages render the shared `EmptyStateWidget` rather than a blank table when the page has no rows or a local search returns no matches; copy distinguishes the two cases and points the user to the existing top-toolbar action.
- Master Data 首次顯示不隱式聚焦搜尋輸入欄，避免在使用者尚未要求輸入時顯示 system-level 寬文字游標；「篩選」動作仍可聚焦並選取搜尋輸入內容。
- Master-data probe emits deterministic fixture provenance; candidate manifests record the same provenance for 1.0, 1.25, and 1.5 scales, and a same-environment repeat capture is pixel-identical.
- Master-data populated-fixture capture neutralizes native cursor hover before screenshotting; a focused regression test protects the stabilization sequence.
- The mismatch between deterministic candidates and the 12 existing committed PNGs is reported as an explicit human baseline-promotion decision; no PNG is replaced or tolerance increased without that decision.
- A pre-promotion backup covers exactly the manifest plus approved 12 PNGs; after native promotion, the same 12 files and fixture provenance are read back and native Master Data regression passes at 1.0, 1.25, and 1.5 DPI.
- The corrected Empty States candidate is visually reviewed, independently authorized, and promoted only for the three listed `empty-master` files; provenance is retained, the six excluded PNGs remain untouched, and 1.0／1.25／1.5 native regressions pass without changing tolerance.
- The exact temporary files are absent, the resulting live membership is recorded as `711`, and `scripts/harness_check.ps1` passes. Neither temporary file may be hidden by a new ignore rule.
- After promotion, Focused, native master-data three-DPI regression, Full, Coverage, and Soak are rerun; any remaining gate failure is reported rather than hidden.

## Evidence requirements

- Pre-fix reproduction output for Pillow version, patch seam, and native regression.
- Post-fix unit/regression output, native JSON with `visual_trustworthy: true`, candidate provenance, same-environment repeat-capture parity, and (after any approved promotion) Full/Coverage/Soak transcript final markers.
- `git diff --check`, current git status, and formal DB read-only status inspection.

## Rollback plan

For the promoted Master Data artifacts, restore only the pre-promotion backup of the manifest plus the exact 12 approved PNGs; for Empty States, restore only `scratch/empty-states-baseline-promotion-backup-093234872f384ac4a53889b01f4686b2`'s manifest plus its exact three approved PNGs. Do not use a reverse visual transform or touch excluded PNGs. Revert source changes only if a focused or native regression fails. No formal DB or release artifact is changed.
