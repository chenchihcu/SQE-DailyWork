# E8: 分割 theme.py (1645→~200 lines)

## 目標

將 `src/ui/theme.py` 中龐大的常數定義與 QSS 模板提取到獨立模組，
使核心 `theme.py` 僅保留應用層主題套用入口 (`apply_app_theme`)。

## 分割邊界

### 新建 `src/ui/theme_tokens.py` (~150 lines)

**職責：** 單一真相來源 (Single Source of Truth) 的設計 Token 定義

**包含內容：**
- `PREFERRED_CJK_FONT_FAMILIES` tuple (第 42-58 行)
- `CJK_FONT_FAMILY_CSS` (第 62-64 行)
- `TOKENS` dict (第 68-194 行) — 所有顏色、間距、圓角等設計 token
- `TYPOGRAPHY` dict (第 196-219 行) — 字級 scale 定義

**依賴：** 僅 `from ui.design_tokens import PALETTE as _P`

**對外匯出：** `PREFERRED_CJK_FONT_FAMILIES`, `CJK_FONT_FAMILY_CSS`, `TOKENS`, `TYPOGRAPHY`

### 新建 `src/ui/theme_qss.py` (~1400 lines)

**職責：** QSS 樣式表模板建構

**包含內容：**
- Imports: `from pathlib import Path`, `from textwrap import dedent`
- `asset_path(asset_name: str) -> Path` (第 259-260 行)
- `_asset_qss_url(asset_name: str) -> str` (第 263-264 行)
- `get_theme_qss() -> str` (第 267-1638 行) — **巨大的 QSS 模板函式**

**依賴：**
- `from ui.theme_tokens import TOKENS, TYPOGRAPHY`
- `from ui.layout_constants import (...)` — 所有版面常數 (BUTTON_PADDING_*, TAB_BAR_*, etc.)

**對外匯出：** `get_theme_qss`, `asset_path`

### 精簡 `src/ui/theme.py` (~150 lines)

**職責：** 應用層主題套用入口

**保留內容：**
- Imports (含 `from ui.theme_tokens import ...`, `from ui.theme_qss import ...`)
- `_supports_cjk_writing_system(font_db, family) -> bool` (第 222-229 行)
- `apply_preferred_cjk_font(app: QApplication | None = None) -> None` (第 232-257 行)
- `apply_app_theme(app: QApplication) -> None` (第 1641-1644 行)

**移除內容：**
- 所有常數定義 (`PREFERRED_CJK_FONT_FAMILIES`, `CJK_FONT_FAMILY_CSS`, `TOKENS`, `TYPOGRAPHY`)
- `asset_path`, `_asset_qss_url` (移至 `theme_qss.py`)
- `get_theme_qss()` (移至 `theme_qss.py`)

**修改：**
- `apply_app_theme` 改為呼叫 `from ui.theme_qss import get_theme_qss`

## 步驟

### Step 1: 建立 `src/ui/theme_tokens.py`

從原始檔提取第 42-219 行的常數定義，加上適當的 imports 和 docstring。

### Step 2: 建立 `src/ui/theme_qss.py`

從原始檔提取：
- Imports (`pathlib.Path`, `textwrap.dedent`)
- `asset_path`, `_asset_qss_url` 函式
- `get_theme_qss()` 完整函式 (第 267-1638 行)
- 在檔案開頭加入 `from ui.theme_tokens import TOKENS, TYPOGRAPHY`
- 在檔案開頭加入所有 `from ui.layout_constants import (...)` 匯入（原 theme.py 第 10-40 行）

### Step 3: 精簡 `src/ui/theme.py`

保留：
- 基礎 imports (`pathlib.Path`, `PySide6.QtGui.QFont, QFontDatabase`, `PySide6.QtWidgets.QApplication`)
- `from ui.theme_tokens import PREFERRED_CJK_FONT_FAMILIES`
- `from ui.theme_qss import get_theme_qss`
- `_supports_cjk_writing_system` (第 222-229 行)
- `apply_preferred_cjk_font` (第 232-257 行)
- `apply_app_theme` (第 1641-1644 行，需確保呼叫 `get_theme_qss()`)

移除：
- `from ui.design_tokens import PALETTE as _P` (不再需要)
- `from ui.layout_constants import (...)` (移至 `theme_qss.py`)
- 所有常數定義 (第 42-219 行)
- `asset_path`, `_asset_qss_url`, `get_theme_qss` 函式

### Step 4: AST 驗證

```powershell
python -c "import ast; ast.parse(open('src/ui/theme_tokens.py').read()); print('theme_tokens OK')"
python -c "import ast; ast.parse(open('src/ui/theme_qss.py').read()); print('theme_qss OK')"
python -c "import ast; ast.parse(open('src/ui/theme.py').read()); print('theme OK')"
```

### Step 5: Import smoke test

```powershell
python -c "from ui.theme_tokens import TOKENS, TYPOGRAPHY, PREFERRED_CJK_FONT_FAMILIES; print('theme_tokens import OK')"
python -c "from ui.theme_qss import get_theme_qss, asset_path; qss = get_theme_qss(); print(f'theme_qss import OK, QSS length: {len(qss)} chars')"
python -c "from ui.theme import apply_app_theme, apply_preferred_cjk_font; print('theme (slim) import OK')"
```

### Step 6: 驗證外部呼叫端不變

```powershell
# 確認外部檔案仍從 ui.theme 匯入
Select-String -Path src\ui\*.py -Pattern "from ui\.theme import"
Select-String -Path tests\*.py -Pattern "from ui\.theme import"
```

預期結果：所有外部呼叫端仍使用 `from ui.theme import apply_app_theme` 或 `from ui.theme import ...`，無需修改。

### Step 7: 執行現有測試

```powershell
python -m pytest tests/test_color_polish_ui_smoke.py -v
```

## 驗證標準

- [ ] AST parse 三檔皆零錯誤
- [ ] `theme_tokens` 可獨立匯入，`TOKENS` dict 包含所有原 key
- [ ] `theme_qss` 可獨立匯入，`get_theme_qss()` 返回有效 QSS 字串（長度約 13000+ chars）
- [ ] `theme` (精簡版) 可匯入 `apply_app_theme` 和 `apply_preferred_cjk_font`
- [ ] 外部呼叫端 import 路徑不變（仍用 `ui.theme`）
- [ ] 精簡後 `theme.py` ≤ 200 lines（原始 1645）
- [ ] UI smoke test 通過

## 相依性分析

### `theme_tokens.py` 依賴
- `ui.design_tokens.PALETTE` — 設計系統原始色票

### `theme_qss.py` 依賴
- `ui.theme_tokens.TOKENS`, `TYPOGRAPHY` — 從新模組匯入
- `ui.layout_constants.*` — 版面常數（原已存在，不變）

### `theme.py` (精簡後) 依賴
- `ui.theme_tokens.PREFERRED_CJK_FONT_FAMILIES` — 字型常數
- `ui.theme_qss.get_theme_qss` — QSS 產生器
- `PySide6.QtGui.QFont, QFontDatabase` — 字型設定
- `PySide6.QtWidgets.QApplication` — 應用物件

## 殘餘風險

- **QSS 模板中的 f-string 變數替換**：`get_theme_qss()` 使用 `{TOKENS["..."]}` 和 `{TYPOGRAPHY["..."]}` 以及 `{LAYOUT_CONSTANT}`。需確認 `theme_qss.py` 正確匯入這些名稱。
- **`asset_path` 的 `__file__` 路徑**：`asset_path` 使用 `Path(__file__).resolve().parent / "assets"`。移至 `theme_qss.py` 後，路徑仍正確指向 `src/ui/assets/`（因為 `theme_qss.py` 也在 `src/ui/`）。
- **迴圈依賴**：`theme_tokens` 不應 import `theme` 或 `theme_qss`；`theme_qss` import `theme_tokens`；`theme` import 前兩者。無迴圈依賴。

## 停損條件

如果 smoke test 失敗（例如 `cannot import name` 或 `KeyError`）：
1. 檢查 `theme_qss.py` 是否正確匯入 `TOKENS`, `TYPOGRAPHY` 和所有 `layout_constants`
2. 檢查 `get_theme_qss()` 的 f-string 中是否有未定義的變數
3. 確認 `asset_path` 的 `__file__` 路徑在 `theme_qss.py` 中仍指向正確的 `assets/` 目錄