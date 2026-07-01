# E7: 分割 event_pdf_exporter.py (1491→300 lines)

## 目標

將 `src/services/event_pdf_exporter.py` 中純 HTML 建構輔助函式提取到新的
`src/services/pdf_html_helpers.py`，使 `event_pdf_exporter.py` 僅保留領域層
匯出邏輯（anomaly/visit/tech-transfer），行數從 ~1491 降至 ~300。

## 分割邊界

### 搬移到 `pdf_html_helpers.py`（~1050 lines）

- **imports**: `base64`, `logging`, `re`, `datetime`, `html.escape`,
  `os.environ`, `pathlib.Path`, `PySide6.QtGui` (QFont, QFontDatabase, QTextDocument)
- **所有常數**: `_ILLEGAL_FILENAME_CHARS`, `_LOADED_FONT_FAMILY`, `_LOGO_DATA_URI`,
  顏色常數 (`_BRAND_PRIMARY` ~ `_CHIP_EMPTY_BG`), `_ATTACHMENT_MAX_*`,
  `_NUMBERED_PARAGRAPH`, `_STATUS_NOT_PROVIDED`
- **`_RawHtml`** class
- **檔名輔助**: `sanitize_filename_part`
- **PDF 寫入/字型**: `_write_html_pdf`, `_preferred_pdf_font_family`,
  `_font_candidate_paths`
- **HTML document templates**: `_html_document` (含完整 CSS),
  `_brief_html_document` (含完整 CSS)
- **HTML 片段建構**: `_document_meta_html`, `_logo_html`, `_logo_data_uri`,
  `_summary_panel`, `_status_badge`, `_section`, `_wide_row`, `_image_pixel_size`,
  `_attachment_display_size`, `_text_section`
- **值格式化**: `_cell`, `_plain_cell`, `_structured_multiline`,
  `_paragraph_line_class`, `_positive_number_or_dash`

### 保留在 `event_pdf_exporter.py`（~300 lines）

- **imports**: `base64`, `logging`, `re`, `datetime`, `html.escape`, `pathlib.Path`,
  `PySide6.QtGui` (QFont, QFontDatabase, QTextDocument),
  `from services import attachment_manager`,
  **`from services.pdf_html_helpers import (…)`**
- **logger**: `logging.getLogger(__name__)`
- **領域事件類型**: `_event_type`
- **領域報告輔助**: `_report_reference`, `default_event_pdf_filename`,
  `_linked_visit_date`
- **異常附件**: `_anomaly_attachment_block`（用 `_TEXT_SECONDARY`, `_BORDER`,
  `_TEXT_PRIMARY` 顏色常數 → 從 helper import）
- **訪廠領域**: `_linked_visit_inline`, `_visit_defect_notes_section`,
  `_visit_defect_note_block`
- **技轉領域**: `_tech_transfer_section`, `_tech_state_marked`,
  `_tech_status_badge`
- **主要匯出 API**（對外不變）:
  - `build_event_pdf_html`, `export_event_pdf`
  - `build_brief_event_pdf_html`, `export_brief_event_pdf`
  - `render_brief_event_to_image`

## 步驟

### Step 1: 建立 `src/services/pdf_html_helpers.py`

寫入新的 helper 檔案，內容按以下順序排列（定義在前、使用在後）：

```
1. Module docstring + __future__
2. imports: base64, logging, re, datetime, escape, environ, Path, QFont etc.
3. logger
4. 所有常數 (_ILLEGAL_FILENAME_CHARS ~ _STATUS_NOT_PROVIDED)
5. _RawHtml class
6. sanitize_filename_part
7. _write_html_pdf, _preferred_pdf_font_family, _font_candidate_paths
8. _html_document (完整 CSS + HTML template)
9. _brief_html_document (完整 CSS + HTML template)
10. _document_meta_html, _logo_html, _logo_data_uri
11. _summary_panel, _status_badge, _section, _wide_row
12. _image_pixel_size, _attachment_display_size
13. _text_section
14. _cell, _plain_cell, _structured_multiline, _paragraph_line_class
15. _positive_number_or_dash
```

所有函式簽名、顏色值、CSS 內容與原始檔完全一致。

### Step 2: 精簡 `src/services/event_pdf_exporter.py`

保留的 imports:
```python
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont, QFontDatabase, QTextDocument

from services import attachment_manager
from services.pdf_html_helpers import (
    _RawHtml,
    sanitize_filename_part,
    _write_html_pdf,
    _preferred_pdf_font_family,
    _html_document,
    _brief_html_document,
    _summary_panel,
    _section,
    _status_badge,
    _wide_row,
    _text_section,
    _cell,
    _plain_cell,
    _structured_multiline,
    _positive_number_or_dash,
    _attachment_display_size,
    _BORDER,
    _TEXT_PRIMARY,
    _TEXT_SECONDARY,
)
```

保留的領域函式（順序不變，但移除所有已被提取的輔助函式）:
```
_event_type
default_event_pdf_filename
build_event_pdf_html
export_event_pdf
_report_reference
_anomaly_attachment_block
_linked_visit_inline
_visit_defect_notes_section
_visit_defect_note_block
_linked_visit_date
_tech_transfer_section
_tech_state_marked
_tech_status_badge
build_brief_event_pdf_html
export_brief_event_pdf
render_brief_event_to_image
```

### Step 3: AST 驗證

```powershell
python -c "import ast; ast.parse(open('src/services/pdf_html_helpers.py').read()); print('pdf_html_helpers OK')"
python -c "import ast; ast.parse(open('src/services/event_pdf_exporter.py').read()); print('event_pdf_exporter OK')"
```

### Step 4: Import smoke test

```powershell
python -c "from services.pdf_html_helpers import _html_document, _brief_html_document, _section, _cell, _preferred_pdf_font_family, sanitize_filename_part; print('pdf_html_helpers import OK')"
python -c "from services.event_pdf_exporter import build_event_pdf_html, export_event_pdf, build_brief_event_pdf_html, export_brief_event_pdf, render_brief_event_to_image; print('event_pdf_exporter import OK')"
```

### Step 5: 驗證對外 API 不變

```powershell
# 確認外部檔案仍從 event_pdf_exporter 匯入
Select-String -Path src\services\event_service.py -Pattern "from services\.event_pdf_exporter"
Select-String -Path scripts\qt_visual_probe.py -Pattern "from services\.event_pdf_exporter"
Select-String -Path src\ncr\tests\test_core.py -Pattern "from services\.event_pdf_exporter"
```

## 驗證標準

- [x] AST parse 零錯誤
- [x] `from services.pdf_html_helpers import …` 成功（所有匯出名稱正確）
- [x] `from services.event_pdf_exporter import build_event_pdf_html` 成功
  （五個 public API 皆可匯入）
- [x] 所有外部 import 路徑仍是 `services.event_pdf_exporter`（無需修改呼叫端）
- [x] 精簡後 `event_pdf_exporter.py` ≤ 400 lines（原始 1491）

## 殘餘風險

- `_anomaly_attachment_block` 使用 `_BORDER`, `_TEXT_PRIMARY`, `_TEXT_SECONDARY`
  顏色常數——已確認從 helper 匯入，無風險。
- `_tech_state_marked` / `_tech_status_badge` 使用 `_RawHtml`——已確認從 helper 匯入。
- `_visit_defect_notes_section` 使用 `_positive_number_or_dash`, `_plain_cell`——
  已確認從 helper 匯入。
- `render_brief_event_to_image` 使用 `QTextDocument`, `QFont`, `QFontDatabase`——
  `QFontDatabase` 在 original 中是 import，現已在 helper 中；但 `QFont`, `QTextDocument`
  在 domain code 的 `render_brief_event_to_image` 內是 local import，無影響。

## 停損條件

如果 import smoke test 失敗（例如 `cannot import name`），表示某個輔助函式
在 helper 中定義但未正確被 domain 檔 import。此時：
1. 查看錯誤訊息中缺少的名稱
2. 確認該名稱在 `pdf_html_helpers.py` 中有定義
3. 將該名稱加入 `event_pdf_exporter.py` 的 import list
