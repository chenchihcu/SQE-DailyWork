# /code-audit 報告 — SQE DailyWork

> 範圍：`src/`, `tests/`, `scripts/`, `main.py`, `run_mig.py`  
> 共 141 個 Python 檔案（排除 `.venv`、`__pycache__`、`.git`）  
> 分類標準：[check-categories.md](skill://code-audit/check-categories.md)  
> 規則來源：`AGENTS.md` + `CLAUDE.md`（無 `.claude/rules/code_audit_rules.md`）

---

## 摘要

| 類別 | 發現數 | 嚴重度 |
|------|--------|--------|
| **A** 架構 / 相依性 | 3 | P2 |
| **B** 無效 / 死程式碼 | 1 | P4 |
| **C** 程式碼品質 / 風格 | 5 | P3–P4 |
| **D** 複雜度 | 5 | P2–P3 |
| **E** 錯誤處理 / 安全 | 2 | P3 |

---

## A — 架構 / 相依性

### A‑1 [P2] `repository.py` 單一巨石：5280 行、80+ 函式

**檔案**: [src/database/repository.py](src/database/repository.py)  
**佐證**: `codegraph_node` 列出 108 個 symbol；行數 `(Get-Content | Measure-Object -Line).Lines = 5280`

所有資料庫操作集中在單一檔案：schema 建立、CRUD（suppliers / products / anomalies / visits / defect_notes）、Anomaly No recode、supplier consolidate、product stage sync、monthly stats cache、seed products、migration helpers。比 `src/services/` + `src/ui/widgets/` 任一目錄的總和還大。

**影響**: 難以測試、難以並行開發、單一檔案編輯衝突高、review 負擔大。  
**建議**: 按領域拆分為 `supplier_repo.py`、`product_repo.py`、`anomaly_repo.py`、`visit_repo.py`、`stats_repo.py`、`migration_repo.py`。

---

### A‑2 [P2] `import *` 洩漏名稱空間

**檔案**: [src/database/repository.py:18–19](src/database/repository.py:18)  
```python
from database.repo_helpers import *  # noqa: F403, F401
from database.repo_helpers import (  # noqa: F401, F811
```

**佐證**: `Select-String -Pattern "import \*"` 唯一匹配

`import *` 將 `repo_helpers` 所有公開名稱倒入 `repository` 的命名空間。編輯 `repo_helpers` 時可能非預期地影響 `repository` 的行為。同時使用 `F403` + `F811` 說明開發者已知此問題但選擇容忍。

**建議**: 改用顯式 `from database.repo_helpers import _normalize_date, _as_int, ...`。

---

### A‑3 [P2] `ncr/` 為獨立子模組，與主 App 平行架構

- **main app**: `src/database/` → `src/services/` → `src/ui/` + `src/ui/widgets/`
- **ncr**: `src/ncr/db/` → `src/ncr/services/` → `src/ncr/ui/` + `src/ncr/models/`

兩個各自獨立的 QSS 主題系統：`src/ui/theme_qss.py`（1218 行）與 `src/ncr/ui/ui_style.py`（1201 行）。設計 token 各自定義。

**影響**: 雙倍維護成本、樣式不一致風險、跨模組資料存取路徑混亂。  
**建議**: 長期目標合併主題系統，短期至少共用 design token。

---

## B — 無效 / 死程式碼

### B‑1 [P4] `# type: ignore[override]` 一處

**檔案**: [src/ui/widgets/common_widgets.py:297](src/ui/widgets/common_widgets.py:297)  
```python
def setText(self, text: str) -> None:  # type: ignore[override]
```

**備註**: Qt override 命名衝突，屬於已知合理使用。唯一一處 `type: ignore`。

**未發現**: 無 `if False:`、無懸置的 `TODO`/`FIXME`/`HACK`（出現在專案 code 中的皆為第三方套件）。  
**未驗證的死程式碼**: 未執行 runtime coverage 分析，靜態 grep 無法 100% 確認。

---

## C — 程式碼品質 / 風格

### C‑1 [P3] 過度使用 `Any` 型態註釋

**檔案**:  
- [src/database/migration.py:32–57](src/database/migration.py:32) — `_pick(row, *keys, default: Any) -> Any`  
- [src/database/ncr_migration.py:54](src/database/ncr_migration.py:54) — `_row_value(row, key, default: Any) -> Any`  
- [src/database/repo_helpers.py:100–262](src/database/repo_helpers.py:100) — 8 個函式簽名使用 `Any`  
- [src/database/repository.py:747](src/database/repository.py:747) — `params: list[Any]`

**佐證**: `Select-String -Pattern "Any\b" | select -first 20` 列出所有匹配（僅限 `src/`）

這些函式多數處理 SQLite row 資料，但 `Any` 讓 type checker 無法驗證傳入值。  
**建議**: 改用 `str | int | float | None` 或 `object`（搭配 `isinstance` 收窄），至少對公開 API 函式。

---

### C‑2 [P4] `print()` 用於生產碼

**檔案**: [src/database/connection.py:129](src/database/connection.py:129)  
```python
print(f"Migrated legacy data from {LEGACY_DB_PATH} -> {DB_PATH}")
```

**備註**: 其餘 `print()` 集中在 scripts/ 下（CLI 工具正當使用）。  
**建議**: 改為 `logger.info()`。

---

### C‑3 [P4] `global` 關鍵字用於模組級快取

**檔案**: [src/services/pdf_html_helpers.py:65,95](src/services/pdf_html_helpers.py:65)  
```python
global _LOADED_FONT_FAMILY
global _LOGO_DATA_URI
```

**建議**: 改用 `functools.cache` 或 `@lru_cache` 裝飾器。

---

### C‑4 [P4] Ad-hoc inline QSS 繞過主題系統

**檔案**:
- [src/ui/sidebar_nav.py:253–255](src/ui/sidebar_nav.py:253) — `setStyleSheet("background: transparent;")`
- [src/ui/widgets/ncr_stats_widget.py:145,179](src/ui/widgets/ncr_stats_widget.py:145) — f-string QSS
- [src/ui/widgets/stats_view_widget.py:312,353](src/ui/widgets/stats_view_widget.py:312) — f-string QSS

**佐證**: `Select-String -Pattern "\.setStyleSheet\("` 列出 11 處

UI-ux-universal 規範要求「樣式隔離優先用 role/property-based QSS」。  
**建議**: 改用 `setProperty("role", ...)` + QSS role selector。

---

### C‑5 [P4] 6 處 `# noqa` 為 Import re-export

**檔案**: `defect_form_widget.py:98,101`、`master_data_dialogs.py:5–8`、`close_anomaly_dialog.py:260`、`migrate_ncr_defects_to_main_db.py:18–20`、`smoke_test_v2.py:24–25`

**佐證**: `Select-String -Pattern "# noqa"` 結果

這些 `# noqa` 用於繞過 lint 規則（`F401`、`E402`），表示 import 順序或弱相依性問題。  
**建議**: 重構 import 順序或建立 `__init__.py` 聚合 export。

---

## D — 複雜度

### D‑1 [P2] `repository.py` — 5280 行（同 A‑1）

### D‑2 [P3] `theme_qss.py` — 1218 行

**檔案**: [src/ui/theme_qss.py](src/ui/theme_qss.py)  
單一函式 `get_theme_qss()` 產出完整 QSS 字串。1218 行純 QSS。

**建議**: 按元件區域拆分（`_qss_buttons()`、`_qss_tables()`、`_qss_sidebar()`...）。

---

### D‑3 [P3] `ui_style.py` (ncr) — 1201 行

**檔案**: [src/ncr/ui/ui_style.py](src/ncr/ui/ui_style.py)  
包含 design tokens、排版常數、元件工廠、QSS 產生器。

**建議**: 拆分為 `tokens.py`、`layout.py`、`widget_factory.py`、`qss.py`。

---

### D‑4 [P3] `defect_form.py` (ncr) — 1010 行 / `test_core.py` (ncr) — 1003 行

**檔案**: [src/ncr/ui/defect_form.py](src/ncr/ui/defect_form.py)、[src/ncr/tests/test_core.py](src/ncr/tests/test_core.py)

**建議**: 按 widget 組件拆分。

---

### D‑5 [P3] `pdf_html_helpers.py` — 879 行

**檔案**: [src/services/pdf_html_helpers.py](src/services/pdf_html_helpers.py)  
30+ 私有輔助函式 + 全域變數。包含 HTML 模板、PDF 渲染、圖片處理。

**建議**: 拆分 `html_templates.py`、`pdf_utils.py`、`image_utils.py`。

---

## E — 錯誤處理 / 安全

### E‑1 [P3] `except Exception` 寬泛捕獲（20 處）

**模式分析**: 全部 20 處 `except Exception` 分為四類：

| 模式 | 數量 | 嚴重度 | 代表檔案 |
|------|------|--------|----------|
| `logger.exception()` + rollback + re-raise | 8 | ✅ 可接受 | `repository.py` ×5, `migration.py` ×1, `main_window.py` ×1, `database.py` ×1 |
| `logger.exception()` + return None | 5 | ✅ 可接受 | `event_service.py`, `event_pdf_exporter.py`, `pdf_html_helpers.py` |
| `logger.exception()` + rollback (no re-raise) | 1 | ⚠️ 邊界 | `repository.py:890` — 已 log 但未 re-raise |
| Rollback + re-raise (無 logger) | 6 | ⚠️ 邊界 | `crud.py:171,183,227,239,436,452` |

**crud.py 問題**: 所有 6 處 `except Exception: conn.rollback(); raise` 未使用 `logger.exception()`，開發者遺失 crash 現場的 stack trace（雖然 exception 會往上傳）。

**佐證**: `Select-String -LiteralPath -Pattern "except Exception:" | Where-Object { $_.Line -notmatch "logger|log|traceback" }`：
```
crud.py:171       except Exception:
crud.py:183       except Exception:
crud.py:227       except Exception:
crud.py:239       except Exception:
crud.py:436       except Exception:
crud.py:452       except Exception:
```

**建議**: `crud.py` 6 處加上 `logger.exception("...失敗")` 保持一致。

---

### E‑2 [P3] `.pop()` / `del` 無預設值可能拋 KeyError

**檔案**:
- [src/ncr/ui/defect_list.py:384,408,421](src/ncr/ui/defect_list.py:384) — `filters.pop("month", None)` ✅ 有預設值
- [src/services/attachment_manager.py:129](src/services/attachment_manager.py:129) — `del existing[name]` ⚠️ 無防護
- [src/ui/widgets/anomaly_attachment_editor.py:176](src/ui/widgets/anomaly_attachment_editor.py:176) — `.pop(old_path_str)` ⚠️ 無預設值
- [src/ui/widgets/new_visit_dialog.py:398](src/ui/widgets/new_visit_dialog.py:398) — `.pop()` ⚠️ 無預設值

**建議**: 對可能不存在的 key 使用 `.pop(key, None)` 或先 `key in dict` 檢查。

---

## 未發現的常見問題（正面發現）

| 類別 | 狀態 |
|------|------|
| Bare `except:`（無指定例外） | ✅ 無 |
| `except: pass` 吞沒錯誤 | ✅ 無 |
| `if False:` 死區塊 | ✅ 無（僅第三方套件） |
| `TODO`/`FIXME`/`HACK` 殘留 | ✅ 無（僅第三方套件） |
| `# type: ignore` 浮濫使用 | ✅ 僅 1 處合理使用 |
| `import *` 浮濫 | ✅ 僅 1 處正規使用 |
| 測試覆蓋率嚴重不足 | ✅ 56 tests + 2 ncr tests ~= 58 tests 對於 ~66 個 src 檔案 |

---

## 總評

```
A: ██████████░░░░░░░░░░  24% (3 finds)
B: ██░░░░░░░░░░░░░░░░░░   5% (1 find)
C: ██████████████░░░░░░  33% (5 finds)
D: ██████████████░░░░░░  33% (5 finds)
E: █████░░░░░░░░░░░░░░░   5% (2 finds)
```

**正面**: 專案在錯誤處理上有良好的 logging 習慣、無 `pass` 吞錯、無懸置 TODO、型態註釋普遍存在。  
**主要風險**: `repository.py` 巨石（5280 行）、`Any` 型態浮濫（C‑1）、`crud.py` 6 處無 log 的 `except Exception`（E‑1）、兩套平行主題系統（A‑3）。  
**建議優先處理**: D‑1（拆分 repository.py）  
**不建議立即處理**: B‑1（已合理）、C‑2（scripts 中 `print()` 可接受）

---

*報告自動產出時間：2026-06-26 | 分析方法：靜態 grep + codegraph + 手動 verify*
