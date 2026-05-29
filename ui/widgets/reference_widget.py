"""靜態說明頁：專案結構與各畫面用途（繁體中文）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.layout_constants import REFERENCE_PAGE_MARGINS
from ui.theme import TOKENS, TYPOGRAPHY

_REF_INNER_MARGINS = (6, 6, 6, 6)
_REF_SPLIT_SPACING = 8
# 左欄「各畫面功能摘要」RichText 字級（px）
_REF_FEATURES_FONT_PX = 12


def _directory_html() -> str:
    """右欄：專案結構表（不含【】標題）。"""
    ff = TYPOGRAPHY["font_family"]
    c = TOKENS["text_primary"]
    muted = TOKENS["text_muted"]
    # Ensure tiny font is at least 11px
    tiny = max(TYPOGRAPHY["helper_text"] - 2, 11)

    row = (
        '<tr><td class="p">{path}</td>'
        '<td class="d">{desc}</td></tr>'
    )

    def r(path: str, desc: str) -> str:
        return row.format(path=path, desc=desc)

    rows: list[str] = [
        r("SQETOOL/", "專案根目錄"),
        r("main.py", "程式入口；建立 QApplication 與 MainWindow"),
        r("run_app.bat", "Windows 一鍵啟動腳本"),
        r("run_mig.py", "資料庫遷移／升級執行點"),
        r("requirements.txt", "Python 相依套件清單"),
        r("README.md", "產品定位、架構與執行說明（開發者文件）"),
        r("data/", "執行時資料目錄"),
        r("　├ sqe_v2.db", "v2 本機 SQLite 資料庫（主要使用）"),
        r("　└ …", "遷移備份、報告等可能出現於此目錄，依遷移流程而定"),
        r("database/", "資料存取層"),
        r("　├ connection.py", "開啟／設定資料庫連線"),
        r("　├ migration.py", "schema 遷移"),
        r("　├ repository.py", "CRUD、查詢與 schema 實作"),
        r("　├ product_stage.py", "產品階段常數與正規化"),
        r("　└ models/", "舊版套件佔位；v2 不使用 ORM 模型"),
        r("services/", "業務邏輯層"),
        r("　├ attachment_manager.py", "異常照片檔案與 captions.json 管理"),
        r("　├ event_pdf_exporter.py", "事件 PDF 匯出"),
        r("　├ event_service.py", "供應商、產品、事件、統計與 Excel API"),
        r("　└ report_service.py", "週報背景產生器"),
        r("ui/", "桌面介面（PySide6）"),
        r("　├ main_window.py", "主視窗：工作流分頁與跨頁刷新"),
        r("　├ theme.py", "全域 QSS／主題套色"),
        r("　├ layout_constants.py", "版面數值（邊距、表單寬度等）"),
        r("　├ popup_i18n.py", "訊息與例外在地化"),
        r("　├ status_colors.py", "狀態色系"),
        r("　├ event_display.py", "事件類型顯示文字"),
        r("　└ widgets/", "各主畫面子頁與元件"),
        r("　　 ├ home_widget.py", "首頁簡介、功能說明與專案目錄"),
        r("　　 ├ defect_list_widget.py", "事件管理列表與篩選"),
        r("　　 ├ defect_form_widget.py", "新增／編輯對話框"),
        r("　　 ├ stats_view_widget.py", "統計分析與圖表"),
        r("　　 ├ master_data_widget.py", "基礎清單：供應商／產品"),
        r("　　 ├ pagination_bar.py", "列表分頁列"),
        r("　　 └ reference_widget.py", "首頁說明內容 helper"),
        r("tests/", "自動化測試"),
        r("scripts/", "輔助腳本（驗證、資料工具等）"),
        r("build/、dist/", "建置／封裝輸出（若使用）"),
        r("scratch/", "本機除錯或臨時檔（可不入版控）"),
    ]

    table_body = "\n".join(rows)

    return f"""<html><head><meta charset="utf-8"/>
<style type="text/css">
body {{ margin: 0; font-family: {ff}; font-size: {tiny}px; color: {c}; }}
table.files {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
td.p {{
  width: 40%;
  vertical-align: top;
  padding: 1px 6px 1px 0;
  font-family: Consolas, "Courier New", monospace;
  font-size: {tiny}px;
  color: {muted};
}}
td.d {{
  width: 60%;
  vertical-align: top;
  padding: 1px 0;
  font-size: {tiny}px;
  color: {c};
}}
</style></head><body>
<table class="files" cellspacing="0" cellpadding="0">
{table_body}
</table>
</body></html>"""


def _features_html(*, relaxed: bool = False) -> str:
    """左欄：功能導覽條列（不含【】標題；不含「參考」條目）。"""
    ff = TYPOGRAPHY["font_family"]
    c = TOKENS["text_primary"]
    paragraph_margin = "6px 0 3px 0" if relaxed else "4px 0 1px 0"
    list_margin = "0 0 8px 0" if relaxed else "0 0 3px 0"
    line_height = "1.46" if relaxed else "1.28"

    return f"""<html><head><meta charset="utf-8"/>
<style type="text/css">
body {{ margin: 0; font-family: {ff}; font-size: {_REF_FEATURES_FONT_PX}px; color: {c}; }}
p {{ margin: {paragraph_margin}; font-weight: 600; }}
p:first-child {{ margin-top: 0; }}
ul {{ margin: {list_margin}; padding-left: 1.1em; }}
li {{ margin: 0; padding: 0; line-height: {line_height}; }}
</style></head><body>
<p>首頁</p>
<ul>
<li>系統首頁：呈現產品定位與主要流程入口說明</li>
<li>功能導覽：整理事件管理、統計與基礎清單用途</li>
<li>專案結構：顯示目前桌面版程式結構與主要檔案用途</li>
</ul>
<p>事件管理</p>
<ul>
<li>工作流分頁拆分訪廠紀錄、訪廠發現異常、單獨異常與已結案</li>
<li>各事件頁可新增訪廠／異常，並以供應商名稱、月份與狀態查詢</li>
<li>點擊表格列可開啟操作選單：編輯、刪除或檢視明細</li>
<li>統計分析可帶入月份與範圍，跳回事件管理追溯明細</li>
</ul>
<p>統計分析</p>
<ul>
<li>選擇月份檢視 KPI 與「供應商異常件數」堆疊長條圖</li>
<li>可匯出該月統計為 Excel</li>
</ul>
<p>基礎清單</p>
<ul>
<li>維護供應商與產品清單</li>
<li>供應商／產品兩分頁：新增、更新、停用、刪除與查詢</li>
</ul>
</body></html>"""


def _make_rich_label(html: str) -> QLabel:
    lab = QLabel()
    lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setText(html)
    lab.setWordWrap(True)
    lab.setAlignment(Qt.AlignmentFlag.AlignTop)
    lab.setOpenExternalLinks(False)
    lab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
    return lab


class ReferenceWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        outer = QFrame()
        outer.setProperty("role", "panel")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(*REFERENCE_PAGE_MARGINS)
        outer_layout.setSpacing(4)

        intro = QLabel("功能導覽與專案結構。")
        intro.setWordWrap(True)
        intro.setProperty("role", "helperText")
        outer_layout.addWidget(intro)

        row = QHBoxLayout()
        row.setSpacing(_REF_SPLIT_SPACING)

        left_frame = QFrame()
        left_frame.setProperty("role", "subpanel")
        left_lo = QVBoxLayout(left_frame)
        left_lo.setContentsMargins(*_REF_INNER_MARGINS)
        left_lo.setSpacing(0)
        left_lo.addWidget(_make_rich_label(_features_html()))

        right_frame = QFrame()
        right_frame.setProperty("role", "subpanel")
        right_lo = QVBoxLayout(right_frame)
        right_lo.setContentsMargins(*_REF_INNER_MARGINS)
        right_lo.setSpacing(0)
        right_lo.addWidget(_make_rich_label(_directory_html()))

        row.addWidget(left_frame, 45)
        row.addWidget(right_frame, 55)

        outer_layout.addLayout(row, 1)

        root.addWidget(outer, 1)
