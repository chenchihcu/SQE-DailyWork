"""Commercial-style, reversible display preference, business defaults and system settings dialog."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.appearance_preferences_service import (
    load_application_preferences,
    save_application_preferences,
)
from ui.appearance_preferences import AppearancePreferences
from ui.layout_constants import PANEL_MARGINS, ROW_GAP
from ui.theme import apply_app_theme
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import apply_clickable_affordance
from ui.widgets.defect_form_widgets import ANOMALY_CATEGORY_OPTIONS


ANOMALY_SOURCE_OPTIONS = [
    "",
    "進料檢驗 (IQC)",
    "製程檢驗 (IPQC)",
    "出貨/客戶端 (OQA)",
    "廠內稽核",
    "訪廠發現",
]

VISIT_TYPE_OPTIONS = [
    "例行訪廠",
    "品質輔導",
    "年度稽核",
    "新產品導入輔導",
]

DEFECT_DISPOSITION_OPTIONS = [
    "",
    "特採",
    "退貨",
    "重工",
    "報廢",
    "待判定",
]

CATEGORY_TAB_NAMES = [
    "外觀主題",
    "視覺表格",
    "表單業務預設",
    "匯出與報告",
    "系統與備份",
]

CATEGORY_DISPLAY_TITLES = [
    "🎨 外觀與風格",
    "📊 表格與檢視",
    "📝 表單與業務",
    "📑 匯出與報表",
    "⚙️ 系統與維護",
]


class _PreferenceTabsAdapter:
    """Compatibility wrapper providing standard QTabWidget API over category list & stacked widget."""

    def __init__(self, dialog: "AppearancePreferencesDialog") -> None:
        self._dialog = dialog

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < self._dialog._stacked_widget.count():
            self._dialog._category_list.setCurrentRow(index)

    def currentIndex(self) -> int:
        return self._dialog._stacked_widget.currentIndex()

    def count(self) -> int:
        return self._dialog._stacked_widget.count()

    def tabText(self, index: int) -> str:
        if 0 <= index < len(CATEGORY_TAB_NAMES):
            return CATEGORY_TAB_NAMES[index]
        return ""


class AppearancePreferencesDialog(QDialog):
    """Preview, save, or discard global display, business and system default preferences."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppearancePreferencesDialog")
        self.setWindowTitle("系統與顯示設定")
        self.setModal(True)
        self._initial_preferences = load_application_preferences()
        self._build_ui()
        self.preference_tabs = _PreferenceTabsAdapter(self)
        self._set_preferences(self._initial_preferences, preview=False)
        fit_dialog_to_available_screen(
            self,
            preferred_width=980,
            preferred_height=660,
            minimum_width=840,
            minimum_height=520,
            maximum_width=1100,
        )

    def _create_scrollable_tab(self, content_widget: QWidget) -> QScrollArea:
        """Wrap a tab page in a borderless, transparent scroll area for responsive viewport protection."""
        scroll = QScrollArea()
        scroll.setObjectName("PreferenceTabScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        scroll.setWidget(content_widget)
        return scroll

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PANEL_MARGINS)
        root.setSpacing(ROW_GAP)

        title = QLabel("系統與顯示設定")
        title.setProperty("role", "sectionTitle")
        title.setToolTip("調整本機介面外觀、業務預設、匯出報告與系統偏好；不影響既有品質資料與資料庫架構。")
        title.setAccessibleDescription("調整本機介面外觀、業務預設、匯出報告與系統偏好；不影響既有品質資料與資料庫架構。")
        root.addWidget(title)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(12)

        # ── Left Navigation Category Sidebar ──
        self._category_list = QListWidget()
        self._category_list.setObjectName("PreferenceCategoryList")
        self._category_list.setFixedWidth(160)
        self._category_list.setFocusPolicy(Qt.TabFocus)
        self._category_list.setAccessibleName("偏好設定分類清單")
        self._category_list.setStyleSheet(
            """
            QListWidget#PreferenceCategoryList {
                border: 1px solid palette(midlight);
                border-radius: 6px;
                background: palette(window);
                outline: none;
                padding: 4px;
            }
            QListWidget#PreferenceCategoryList::item {
                height: 44px;
                padding: 6px 12px;
                border-radius: 5px;
                font-weight: 400;
                color: palette(text);
            }
            QListWidget#PreferenceCategoryList::item:hover {
                background: palette(midlight);
            }
            QListWidget#PreferenceCategoryList::item:selected {
                background: #1D4ED8;
                color: #FFFFFF;
                font-weight: bold;
            }
            """
        )

        for title_text in CATEGORY_DISPLAY_TITLES:
            item = QListWidgetItem(title_text)
            self._category_list.addItem(item)

        body_layout.addWidget(self._category_list)

        # ── Right Stacked Widget ──
        self._stacked_widget = QStackedWidget()
        self._stacked_widget.setObjectName("PreferenceStackedWidget")
        body_layout.addWidget(self._stacked_widget, 1)
        root.addLayout(body_layout, 1)

        self._category_list.currentRowChanged.connect(self._stacked_widget.setCurrentIndex)

        # ── Tab 0: 外觀主題 (Appearance & Theme) ──
        theme_page = QWidget()
        theme_grid = QGridLayout(theme_page)
        theme_grid.setContentsMargins(4, 4, 4, 4)
        theme_grid.setSpacing(12)

        # Tab 0 - Left: 版面密度與視窗啟動
        left_theme_col = QVBoxLayout()
        left_theme_col.setSpacing(ROW_GAP)

        density_group = QGroupBox("版面與控制項密度")
        density_layout = QVBoxLayout(density_group)
        density_layout.setSpacing(ROW_GAP)
        self._density_group = QButtonGroup(self)
        self._density_buttons = {}
        density_layout.addWidget(QLabel("全頁面控制項密度"))
        density_row = QHBoxLayout()
        for value, label, description in (
            ("compact", "緊湊", "緊湊版面：適合需要一次檢視更多列表與控制項的工作。"),
            ("standard", "標準", "標準版面：平衡一般工作區的可讀性與資訊密度。"),
            ("comfortable", "舒適", "舒適版面：增加控制項與資料表的垂直留白，降低視覺擁擠。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"介面密度：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._density_group.addButton(radio)
            self._density_buttons[value] = radio
            density_row.addWidget(radio)
        density_layout.addLayout(density_row)

        density_layout.addWidget(QLabel("側欄導覽列密度"))
        sidebar_row = QHBoxLayout()
        self._sidebar_density_group = QButtonGroup(self)
        self._sidebar_density_buttons = {}
        for value, label, description in (
            ("compact", "緊湊側欄", "縮短側欄列高以顯示更多工作入口。"),
            ("standard", "標準側欄", "使用既有清晰可讀的側欄列高。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"側欄密度：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._sidebar_density_group.addButton(radio)
            self._sidebar_density_buttons[value] = radio
            sidebar_row.addWidget(radio)
        density_layout.addLayout(sidebar_row)

        density_layout.addWidget(QLabel("側欄圖示顯示模式"))
        sidebar_icon_row = QHBoxLayout()
        self._sidebar_icon_group = QButtonGroup(self)
        self._sidebar_icon_buttons = {}
        for value, label, description in (
            ("both", "圖文並茂", "同時顯示工作頁面圖示與繁體中文標籤。"),
            ("text_only", "純文字", "僅顯示繁體中文導覽文字，簡約整齊。"),
            ("compact_icon", "簡約圖示", "側欄以緊湊圖示為主，兼顧空間與辨識度。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"側欄圖示模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._sidebar_icon_group.addButton(radio)
            self._sidebar_icon_buttons[value] = radio
            sidebar_icon_row.addWidget(radio)
        density_layout.addLayout(sidebar_icon_row)
        left_theme_col.addWidget(density_group)

        window_mode_group = QGroupBox("視窗啟動與狀態列")
        window_mode_layout = QVBoxLayout(window_mode_group)
        window_mode_layout.setSpacing(ROW_GAP)

        window_mode_layout.addWidget(QLabel("視窗啟動尺寸模式"))
        self._window_geometry_group = QButtonGroup(self)
        self._window_geometry_buttons = {}
        for value, label, description in (
            ("remember", "記憶上次視窗大小與位置", "啟動時自動還原前次關閉時的視窗尺寸與螢幕位置。"),
            ("standard", "固定標準視窗尺寸 (1200x800)", "每次啟動均以標準 1200x800 居中開啟。"),
            ("maximized", "預設全螢幕最大化啟動", "開啟應用程式時直接最大化視窗。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"視窗尺寸模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._window_geometry_group.addButton(radio)
            self._window_geometry_buttons[value] = radio
            window_mode_layout.addWidget(radio)

        window_mode_layout.addWidget(QLabel("主視窗狀態列詳細度"))
        self._status_bar_detail_group = QButtonGroup(self)
        self._status_bar_detail_buttons = {}
        status_bar_row = QHBoxLayout()
        for value, label, description in (
            ("standard", "標準", "顯示標準操作提示與資料庫狀態。"),
            ("compact", "簡潔", "僅在發生操作或重要提示時顯示訊息。"),
            ("detailed", "詳細", "即時顯示資料庫連線、待辦筆數與系統資源狀態。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"狀態列詳細度：{label}")
            radio.setToolTip(description)
            self._status_bar_detail_group.addButton(radio)
            self._status_bar_detail_buttons[value] = radio
            status_bar_row.addWidget(radio)
        window_mode_layout.addLayout(status_bar_row)
        left_theme_col.addWidget(window_mode_group)
        left_theme_col.addStretch(1)

        # Tab 0 - Right: 主題色彩、文字與中文字型
        right_theme_col = QVBoxLayout()
        right_theme_col.setSpacing(ROW_GAP)

        theme_style_group = QGroupBox("主題調性與強調色彩")
        theme_style_layout = QVBoxLayout(theme_style_group)
        theme_style_layout.setSpacing(ROW_GAP)

        theme_style_layout.addWidget(QLabel("介面調性模式"))
        self._theme_mode_group = QButtonGroup(self)
        self._theme_mode_buttons = {}
        theme_mode_row = QHBoxLayout()
        for value, label, description in (
            ("light", "專業亮色", "經典專業 Slate 明亮主題。"),
            ("dark_slate", "海軍暗灰", "沉穩深色灰藍主題，護眼低疲勞。"),
            ("system", "跟隨系統", "自動配合作業系統淺色/深色設定。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"主題模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._theme_mode_group.addButton(radio)
            self._theme_mode_buttons[value] = radio
            theme_mode_row.addWidget(radio)
        theme_style_layout.addLayout(theme_mode_row)

        theme_style_layout.addWidget(QLabel("主題強調色彩"))
        self._accent_color_group = QButtonGroup(self)
        self._accent_color_buttons = {}
        color_grid = QGridLayout()
        color_grid.setHorizontalSpacing(8)
        color_grid.setVerticalSpacing(6)
        colors = [
            ("electric_blue", "● 經典藍", "#1D4ED8", "預設 SQE Electric Blue 經典藍色主題。"),
            ("slate_navy", "● 海軍灰藍", "#1E293B", "沉穩灰藍調，適合長時間盯螢幕閱讀。"),
            ("emerald", "● 翡翠綠", "#047857", "清新墨綠調，高辨識度品質管理風格。"),
            ("amber", "● 溫和琥珀", "#B45309", "暖色系琥珀調，舒適視覺焦點。"),
            ("violet", "● 雅致紫羅蘭", "#7C3AED", "科技感深紫色調，鮮明高辨識。"),
            ("rose", "● 活力玫瑰", "#E11D48", "活力紅粉調，醒目重點提示。"),
        ]
        for idx, (value, label, hex_code, description) in enumerate(colors):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"主題色彩：{label}")
            radio.setToolTip(f"{description} (色碼：{hex_code})")
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._accent_color_group.addButton(radio)
            self._accent_color_buttons[value] = radio
            color_grid.addWidget(radio, idx // 2, idx % 2)
        theme_style_layout.addLayout(color_grid)
        right_theme_col.addWidget(theme_style_group)

        typography_group = QGroupBox("字型與無障礙檢視")
        typography_layout = QVBoxLayout(typography_group)
        typography_layout.setSpacing(ROW_GAP)

        typography_layout.addWidget(QLabel("偏好中文字型"))
        self._cjk_font_group = QButtonGroup(self)
        self._cjk_font_buttons = {}
        cjk_font_row = QHBoxLayout()
        for value, label, description in (
            ("default", "微軟正黑體", "Windows 預設微軟正黑體 (Microsoft JhengHei UI)。"),
            ("noto_sans", "思源黑體", "思源黑體 / Noto Sans CJK TC 高清晰度渲染。"),
            ("system", "系統預設", "由作業系統字型鏈自動匹配。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"中文字型：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._cjk_font_group.addButton(radio)
            self._cjk_font_buttons[value] = radio
            cjk_font_row.addWidget(radio)
        typography_layout.addLayout(cjk_font_row)

        typography_layout.addWidget(QLabel("文字大小與比例"))
        self._text_scale_group = QButtonGroup(self)
        self._text_scale_buttons = {}
        text_row = QHBoxLayout()
        for value, label, description in (
            ("standard", "標準字級", "使用 SQE DailyWork 的既有繁中字級階層。"),
            ("large", "放大字級 (+10%)", "放大應用程式文字以提升長時間閱讀的舒適度。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"文字大小：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._text_scale_group.addButton(radio)
            self._text_scale_buttons[value] = radio
            text_row.addWidget(radio)
        typography_layout.addLayout(text_row)

        typography_layout.addWidget(QLabel("高對比模式"))
        self._contrast_mode_group = QButtonGroup(self)
        self._contrast_mode_buttons = {}
        contrast_row = QHBoxLayout()
        for value, label, description in (
            ("standard", "標準對比", "使用 SQE DailyWork 既有的專業主題。"),
            ("high", "高對比模式", "提升文字、邊框、焦點與選取狀態的辨識度。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"對比模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._contrast_mode_group.addButton(radio)
            self._contrast_mode_buttons[value] = radio
            contrast_row.addWidget(radio)
        typography_layout.addLayout(contrast_row)
        right_theme_col.addWidget(typography_group)
        right_theme_col.addStretch(1)

        theme_grid.addLayout(left_theme_col, 0, 0)
        theme_grid.addLayout(right_theme_col, 0, 1)
        self._stacked_widget.addWidget(self._create_scrollable_tab(theme_page))

        # ── Tab 1: 視覺表格與互動 (Visual & Tables) ──
        table_page = QWidget()
        table_grid = QGridLayout(table_page)
        table_grid.setContentsMargins(4, 4, 4, 4)
        table_grid.setSpacing(12)

        # Tab 1 - Left: 表格密度、分頁與排序
        left_table_col = QVBoxLayout()
        left_table_col.setSpacing(ROW_GAP)

        table_density_group = QGroupBox("資料表閱讀密度與分頁")
        table_density_layout = QVBoxLayout(table_density_group)
        table_density_layout.setSpacing(ROW_GAP)

        table_density_layout.addWidget(QLabel("資料表閱讀密度"))
        self._table_density_group = QButtonGroup(self)
        self._table_density_buttons = {}
        table_density_row = QHBoxLayout()
        for value, label, description in (
            ("compact", "緊湊", "緊湊密度：縮短列高與表頭，適合大量資料比對。"),
            ("standard", "標準", "標準密度：平衡表格可讀性與可視筆數。"),
            ("comfortable", "舒適", "舒適密度：增加列高與表頭高度，降低長時間閱讀負擔。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"資料表閱讀密度：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._table_density_group.addButton(radio)
            self._table_density_buttons[value] = radio
            table_density_row.addWidget(radio)
        table_density_layout.addLayout(table_density_row)

        table_density_layout.addWidget(QLabel("資料表預設單頁筆數"))
        self._page_limit_group = QButtonGroup(self)
        self._page_limit_buttons = {}
        page_limit_grid = QGridLayout()
        limits = [
            (25, "25 筆 / 頁", "每頁預設顯示 25 筆資料。"),
            (50, "50 筆 / 頁 (預設)", "每頁預設顯示 50 筆資料。"),
            (100, "100 筆 / 頁", "每頁預設顯示 100 筆資料。"),
            (0, "不分頁（全部）", "不進行表格分頁，直接載入全部搜尋結果。"),
        ]
        for idx, (value, label, description) in enumerate(limits):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"資料表單頁筆數：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._page_limit_group.addButton(radio)
            self._page_limit_buttons[value] = radio
            page_limit_grid.addWidget(radio, idx // 2, idx % 2)
        table_density_layout.addLayout(page_limit_grid)

        table_density_layout.addWidget(QLabel("日期欄位顯示格式"))
        self._date_format_group = QButtonGroup(self)
        self._date_format_buttons = {}
        date_format_row = QHBoxLayout()
        for value, label, description in (
            ("YYYY-MM-DD", "YYYY-MM-DD (連字號)", "例如：2026-08-16。"),
            ("YYYY/MM/DD", "YYYY/MM/DD (斜線)", "例如：2026/08/16。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"日期顯示格式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._date_format_group.addButton(radio)
            self._date_format_buttons[value] = radio
            date_format_row.addWidget(radio)
        table_density_layout.addLayout(date_format_row)

        self._table_show_row_numbers_checkbox = QCheckBox("資料表格首欄顯示序號行號")
        self._table_show_row_numbers_checkbox.setAccessibleName("資料表格顯示序號")
        self._table_show_row_numbers_checkbox.setToolTip("在品質異常與事件清單首欄顯示 1, 2, 3... 序號以方便對帳。")
        self._table_show_row_numbers_checkbox.setAccessibleDescription("在品質異常與事件清單首欄顯示 1, 2, 3... 序號以方便對帳。")
        table_density_layout.addWidget(self._table_show_row_numbers_checkbox)
        left_table_col.addWidget(table_density_group)

        table_sort_group = QGroupBox("清單排序與呈現方式")
        table_sort_layout = QVBoxLayout(table_sort_group)
        table_sort_layout.setSpacing(ROW_GAP)

        table_sort_layout.addWidget(QLabel("清單預設排序欄位與方向"))
        self._list_sort_group = QButtonGroup(self)
        self._list_sort_buttons = {}
        for value, label, description in (
            ("anomaly_no_desc", "依異常單號降冪排序 (預設)", "最新建立之異常單號優先顯示。"),
            ("date_desc", "依發生日期降冪排序", "最近發生之事件日期優先顯示。"),
            ("status_first", "待處理項目優先排序", "未結案項目置頂顯示。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"清單預設排序：{label}")
            radio.setToolTip(description)
            self._list_sort_group.addButton(radio)
            self._list_sort_buttons[value] = radio
            table_sort_layout.addWidget(radio)

        table_sort_layout.addWidget(QLabel("表格文字過長換行模式"))
        self._text_wrapping_group = QButtonGroup(self)
        self._text_wrapping_buttons = {}
        text_wrap_row = QHBoxLayout()
        for value, label, description in (
            ("elide", "單行省略 (...) (預設)", "文字過長時顯示省略號，保持表格高度整齊。"),
            ("wrap", "文字自動換行 (Wrap)", "自動擴展列高以完整顯示內容。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"表格換行模式：{label}")
            radio.setToolTip(description)
            self._text_wrapping_group.addButton(radio)
            self._text_wrapping_buttons[value] = radio
            text_wrap_row.addWidget(radio)
        table_sort_layout.addLayout(text_wrap_row)
        left_table_col.addWidget(table_sort_group)
        left_table_col.addStretch(1)

        # Tab 1 - Right: 互動、視覺輔助與統計分析
        right_table_col = QVBoxLayout()
        right_table_col.setSpacing(ROW_GAP)

        interaction_group = QGroupBox("資料表互動與搜尋觸發")
        interaction_layout = QVBoxLayout(interaction_group)
        interaction_layout.setSpacing(ROW_GAP)

        interaction_layout.addWidget(QLabel("資料表列表列雙擊預設行為"))
        self._double_click_group = QButtonGroup(self)
        self._double_click_buttons = {}
        for value, label, description in (
            ("menu", "彈出操作選單 (預設)", "雙擊列表項目時彈出功能選單（編輯/結案/刪除/預覽等）。"),
            ("preview", "檢視案件詳情", "雙擊異常項目時直接開啟案件管理頁；訪廠項目仍開啟預覽視窗。"),
            ("edit", "直接開啟編輯視窗", "雙擊列表項目時直接開啟編輯表單。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"雙擊預設行為：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._double_click_group.addButton(radio)
            self._double_click_buttons[value] = radio
            interaction_layout.addWidget(radio)

        interaction_layout.addWidget(QLabel("搜尋過濾觸發模式"))
        self._search_mode_group = QButtonGroup(self)
        self._search_mode_buttons = {}
        search_mode_row = QHBoxLayout()
        for value, label, description in (
            ("live", "即打即篩 (Live)", "輸入關鍵字時即時過濾資料表列表。"),
            ("manual", "Enter / 點擊搜尋", "輸入完成後按 Enter 鍵或點擊搜尋按鈕才執行過濾。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"搜尋觸發模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._search_mode_group.addButton(radio)
            self._search_mode_buttons[value] = radio
            search_mode_row.addWidget(radio)
        interaction_layout.addLayout(search_mode_row)

        self._quick_filter_case_checkbox = QCheckBox("搜尋關鍵字精確比對大小寫")
        self._quick_filter_case_checkbox.setAccessibleName("搜尋關鍵字區分大小寫")
        self._quick_filter_case_checkbox.setToolTip("搜尋料號或問題描述時區分英文字母大小寫。")
        self._quick_filter_case_checkbox.setAccessibleDescription("搜尋料號或問題描述時區分英文字母大小寫。")
        interaction_layout.addWidget(self._quick_filter_case_checkbox)
        right_table_col.addWidget(interaction_group)

        visual_helper_group = QGroupBox("視覺輔助與統計分析")
        visual_helper_layout = QVBoxLayout(visual_helper_group)
        visual_helper_layout.setSpacing(ROW_GAP)

        self._alt_row_checkbox = QCheckBox("顯示資料表交替行底色")
        self._alt_row_checkbox.setAccessibleName("顯示資料表交替行底色")
        self._alt_row_checkbox.setToolTip("使用雙色交替底色增強表格列視覺對位。")
        self._alt_row_checkbox.setAccessibleDescription("使用雙色交替底色增強表格列視覺對位。")
        self._alt_row_checkbox.toggled.connect(self._preview_from_controls)
        visual_helper_layout.addWidget(self._alt_row_checkbox)

        self._grid_lines_checkbox = QCheckBox("顯示資料表網格線")
        self._grid_lines_checkbox.setAccessibleName("顯示資料表網格線")
        self._grid_lines_checkbox.setToolTip("顯示表格欄位與資料列間的微細網格線。")
        self._grid_lines_checkbox.setAccessibleDescription("顯示表格欄位與資料列間的微細網格線。")
        self._grid_lines_checkbox.toggled.connect(self._preview_from_controls)
        visual_helper_layout.addWidget(self._grid_lines_checkbox)

        self._hover_highlight_checkbox = QCheckBox("啟用滑鼠懸停資料行高亮")
        self._hover_highlight_checkbox.setAccessibleName("啟用滑鼠懸停資料行高亮")
        self._hover_highlight_checkbox.setToolTip("滑鼠游標移過資料列時顯示平滑背景反白強調。")
        self._hover_highlight_checkbox.setAccessibleDescription("滑鼠游標移過資料列時顯示平滑背景反白強調。")
        visual_helper_layout.addWidget(self._hover_highlight_checkbox)

        self._highlight_overdue_checkbox = QCheckBox("逾期未結案項目醒目警示")
        self._highlight_overdue_checkbox.setAccessibleName("逾期未結案項目醒目警示")
        self._highlight_overdue_checkbox.setToolTip("以淺紅色背景醒目標示已逾期之未結案異常與待辦事件。")
        self._highlight_overdue_checkbox.setAccessibleDescription("以淺紅色背景醒目標示已逾期之未結案異常與待辦事件。")
        visual_helper_layout.addWidget(self._highlight_overdue_checkbox)

        self._auto_scroll_top_checkbox = QCheckBox("搜尋或換頁時自動捲動至頂部")
        self._auto_scroll_top_checkbox.setAccessibleName("搜尋或換頁自動捲動至頂部")
        self._auto_scroll_top_checkbox.setToolTip("在篩選或切換分頁後自動將表格垂直捲動桿重置回頂部。")
        self._auto_scroll_top_checkbox.setAccessibleDescription("在篩選或切換分頁後自動將表格垂直捲動桿重置回頂部。")
        visual_helper_layout.addWidget(self._auto_scroll_top_checkbox)

        self._animations_checkbox = QCheckBox("啟用微過場與動畫效果")
        self._animations_checkbox.setAccessibleName("啟用微過場與動畫效果")
        self._animations_checkbox.setToolTip("在控制項懸停與視窗切換時啟用微動畫提示。")
        self._animations_checkbox.setAccessibleDescription("在控制項懸停與視窗切換時啟用微動畫提示。")
        self._animations_checkbox.toggled.connect(self._preview_from_controls)
        visual_helper_layout.addWidget(self._animations_checkbox)

        visual_helper_layout.addWidget(QLabel("預設統計區間跨度"))
        self._stats_span_group = QButtonGroup(self)
        self._stats_span_buttons = {}
        stats_span_row = QHBoxLayout()
        for value, label, description in (
            (3, "近 3 個月", "進入統計頁面時預設載入最近 3 個月的數據與圖表。"),
            (6, "近 6 個月 (預設)", "進入統計頁面時預設載入最近 6 個月的數據與圖表。"),
            (12, "近 1 年", "進入統計頁面時預設載入最近 1 年的數據與圖表。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設統計區間：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._stats_span_group.addButton(radio)
            self._stats_span_buttons[value] = radio
            stats_span_row.addWidget(radio)
        visual_helper_layout.addLayout(stats_span_row)

        self._pareto_cutoff_checkbox = QCheckBox("顯示 Pareto 80/20 累計百分比警戒線")
        self._pareto_cutoff_checkbox.setAccessibleName("顯示 Pareto 80/20 警戒參考線")
        self._pareto_cutoff_checkbox.setToolTip("在品質異常 Pareto 分析圖表 80% 處繪製輔助警戒虛線。")
        self._pareto_cutoff_checkbox.setAccessibleDescription("在品質異常 Pareto 分析圖表 80% 處繪製輔助警戒虛線。")
        visual_helper_layout.addWidget(self._pareto_cutoff_checkbox)
        right_table_col.addWidget(visual_helper_group)
        right_table_col.addStretch(1)

        table_grid.addLayout(left_table_col, 0, 0)
        table_grid.addLayout(right_table_col, 0, 1)
        self._stacked_widget.addWidget(self._create_scrollable_tab(table_page))

        # ── Tab 2: 表單業務預設 (Form & Business Defaults) ──
        form_page = QWidget()
        form_grid = QGridLayout(form_page)
        form_grid.setContentsMargins(4, 4, 4, 4)
        form_grid.setSpacing(12)

        # Tab 2 - Left: 異常事件表單預設
        left_form_col = QVBoxLayout()
        left_form_col.setSpacing(ROW_GAP)

        anomaly_default_group = QGroupBox("異常事件表單業務預設")
        anomaly_default_layout = QVBoxLayout(anomaly_default_group)
        anomaly_default_layout.setSpacing(ROW_GAP)

        anomaly_default_layout.addWidget(QLabel("預設責任人員 / SQE 填報人"))
        self._responsible_person_input = QLineEdit()
        self._responsible_person_input.setPlaceholderText("例如：王大明 / SQE001（留空則不自動帶入）")
        self._responsible_person_input.setAccessibleName("預設責任人員")
        self._responsible_person_input.setToolTip("新建異常事件時自動填入責任人員欄位。")
        anomaly_default_layout.addWidget(self._responsible_person_input)

        anomaly_default_layout.addWidget(QLabel("預設結案驗證人"))
        self._closer_name_input = QLineEdit()
        self._closer_name_input.setPlaceholderText("例如：陳主管 / SQE_LEAD（留空則不預設）")
        self._closer_name_input.setAccessibleName("預設結案驗證人")
        self._closer_name_input.setToolTip("結案視窗開啟時預設填入的驗證工程師名稱。")
        anomaly_default_layout.addWidget(self._closer_name_input)

        anomaly_default_layout.addWidget(QLabel("預設異常類別"))
        self._anomaly_category_combo = QComboBox()
        self._anomaly_category_combo.addItems([""] + ANOMALY_CATEGORY_OPTIONS)
        self._anomaly_category_combo.setAccessibleName("預設異常類別")
        self._anomaly_category_combo.setToolTip("新建異常事件時預設選取的異常類別。")
        anomaly_default_layout.addWidget(self._anomaly_category_combo)

        anomaly_default_layout.addWidget(QLabel("預設異常來源"))
        self._anomaly_source_combo = QComboBox()
        self._anomaly_source_combo.addItems(ANOMALY_SOURCE_OPTIONS)
        self._anomaly_source_combo.setAccessibleName("預設異常來源")
        self._anomaly_source_combo.setToolTip("新建異常事件時預設選取的異常發現來源。")
        anomaly_default_layout.addWidget(self._anomaly_source_combo)

        anomaly_default_layout.addWidget(QLabel("預設嚴重度等級"))
        self._severity_level_group = QButtonGroup(self)
        self._severity_level_buttons = {}
        severity_row = QHBoxLayout()
        for value, label, description in (
            ("一般", "一般", "一般品質缺失或輕微異常。"),
            ("重大", "重大", "影響出貨或製程嚴重中斷之重大異常。"),
            ("極嚴重", "極嚴重", "安全或法規重大品質違規。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設嚴重度：{label}")
            radio.setToolTip(description)
            self._severity_level_group.addButton(radio)
            self._severity_level_buttons[value] = radio
            severity_row.addWidget(radio)
        anomaly_default_layout.addLayout(severity_row)

        self._sync_visit_checkbox = QCheckBox("新建異常時預設勾選「同步建立訪廠紀錄」")
        self._sync_visit_checkbox.setAccessibleName("新建異常預設同步建立訪廠紀錄")
        self._sync_visit_checkbox.setToolTip("開啟新增異常表單時，預設自動勾選同步產生同日訪廠紀錄。")
        self._sync_visit_checkbox.setAccessibleDescription("開啟新增異常表單時，預設自動勾選同步產生同日訪廠紀錄。")
        anomaly_default_layout.addWidget(self._sync_visit_checkbox)

        self._auto_anomaly_no_checkbox = QCheckBox("切換日期時自動重新預覽 11 碼單號")
        self._auto_anomaly_no_checkbox.setAccessibleName("切換日期自動重算單號")
        self._auto_anomaly_no_checkbox.setToolTip("修改發生日期時，自動依據新日期重新生成 YYYYMMDDNNN 單號預覽。")
        self._auto_anomaly_no_checkbox.setAccessibleDescription("修改發生日期時，自動依據新日期重新生成 YYYYMMDDNNN 單號預覽。")
        anomaly_default_layout.addWidget(self._auto_anomaly_no_checkbox)

        self._auto_uppercase_checkbox = QCheckBox("輸入產品料號與單號自動轉換為大寫")
        self._auto_uppercase_checkbox.setAccessibleName("料號單號自動轉大寫")
        self._auto_uppercase_checkbox.setToolTip("在表單輸入料號或代碼時自動將英文字母轉為標準大寫。")
        self._auto_uppercase_checkbox.setAccessibleDescription("在表單輸入料號或代碼時自動將英文字母轉為標準大寫。")
        anomaly_default_layout.addWidget(self._auto_uppercase_checkbox)

        self._require_defect_photos_checkbox = QCheckBox("建立重大異常時提醒檢附不良佐證照片")
        self._require_defect_photos_checkbox.setAccessibleName("建立重大異常提醒檢附照片")
        self._require_defect_photos_checkbox.setToolTip("建立重大或極嚴重異常時提醒上傳或檢附現場佐證照片。")
        self._require_defect_photos_checkbox.setAccessibleDescription("建立重大或極嚴重異常時提醒上傳或檢附現場佐證照片。")
        anomaly_default_layout.addWidget(self._require_defect_photos_checkbox)
        left_form_col.addWidget(anomaly_default_group)
        left_form_col.addStretch(1)

        # Tab 2 - Right: 訪廠與處置預設
        right_form_col = QVBoxLayout()
        right_form_col.setSpacing(ROW_GAP)

        visit_default_group = QGroupBox("訪廠與改善回覆預設")
        visit_default_layout = QVBoxLayout(visit_default_group)
        visit_default_layout.setSpacing(ROW_GAP)

        visit_default_layout.addWidget(QLabel("改善回覆預設期限天數"))
        self._due_days_group = QButtonGroup(self)
        self._due_days_buttons = {}
        due_days_row = QHBoxLayout()
        for value, label, description in (
            (7, "7 天 (預設)", "預設回覆期限為 7 天。"),
            (14, "14 天 (2 週)", "預設回覆期限為 14 天。"),
            (30, "30 天 (1 個月)", "預設回覆期限為 30 天。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"改善回覆預設期限：{label}")
            radio.setToolTip(description)
            self._due_days_group.addButton(radio)
            self._due_days_buttons[value] = radio
            due_days_row.addWidget(radio)
        visit_default_layout.addLayout(due_days_row)

        visit_default_layout.addWidget(QLabel("預設訪廠性質"))
        self._visit_type_combo = QComboBox()
        self._visit_type_combo.addItems(VISIT_TYPE_OPTIONS)
        self._visit_type_combo.setAccessibleName("預設訪廠性質")
        self._visit_type_combo.setToolTip("新建訪廠紀錄時預設選取的訪廠性質。")
        visit_default_layout.addWidget(self._visit_type_combo)

        visit_default_layout.addWidget(QLabel("預設訪廠時段"))
        self._visit_time_slot_group = QButtonGroup(self)
        self._visit_time_slot_buttons = {}
        time_slot_row = QHBoxLayout()
        for value, label, description in (
            ("上午", "上午", "新建訪廠時預設選取上午時段。"),
            ("下午", "下午 (預設)", "新建訪廠時預設選取下午時段。"),
            ("全天", "全天", "新建訪廠時預設選取全天時段。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設訪廠時段：{label}")
            radio.setToolTip(description)
            self._visit_time_slot_group.addButton(radio)
            self._visit_time_slot_buttons[value] = radio
            time_slot_row.addWidget(radio)
        visit_default_layout.addLayout(time_slot_row)
        right_form_col.addWidget(visit_default_group)

        defect_default_group = QGroupBox("倉庫不良品處置與抽樣預設")
        defect_default_layout = QVBoxLayout(defect_default_group)
        defect_default_layout.setSpacing(ROW_GAP)

        defect_default_layout.addWidget(QLabel("不良品預設處置方式"))
        self._defect_disposition_combo = QComboBox()
        self._defect_disposition_combo.addItems(DEFECT_DISPOSITION_OPTIONS)
        self._defect_disposition_combo.setAccessibleName("不良品預設處置方式")
        self._defect_disposition_combo.setToolTip("新建倉庫實體不良品紀錄時預設選取的處置判定方式。")
        defect_default_layout.addWidget(self._defect_disposition_combo)

        defect_default_layout.addWidget(QLabel("預設檢驗抽樣批量數"))
        self._defect_sample_size_group = QButtonGroup(self)
        self._defect_sample_size_buttons = {}
        sample_size_row = QHBoxLayout()
        for value, label, description in (
            (0, "不指定 (預設)", "新建檢驗或不良品表單時抽樣數留空。"),
            (50, "50 件", "預設帶入 50 件抽樣數。"),
            (100, "100 件", "預設帶入 100 件抽樣數。"),
            (200, "200 件", "預設帶入 200 件抽樣數。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設抽樣批量：{label}")
            radio.setToolTip(description)
            self._defect_sample_size_group.addButton(radio)
            self._defect_sample_size_buttons[value] = radio
            sample_size_row.addWidget(radio)
        defect_default_layout.addLayout(sample_size_row)
        right_form_col.addWidget(defect_default_group)
        right_form_col.addStretch(1)

        form_grid.addLayout(left_form_col, 0, 0)
        form_grid.addLayout(right_form_col, 0, 1)
        self._stacked_widget.addWidget(self._create_scrollable_tab(form_page))

        # ── Tab 3: 匯出與報告 (Export & Reports) ──
        export_page = QWidget()
        export_grid = QGridLayout(export_page)
        export_grid.setContentsMargins(4, 4, 4, 4)
        export_grid.setSpacing(12)

        # Tab 3 - Left: 匯出目錄與檔案行為
        left_export_col = QVBoxLayout()
        left_export_col.setSpacing(ROW_GAP)

        export_path_group = QGroupBox("匯出路徑與命名格式")
        export_path_layout = QVBoxLayout(export_path_group)
        export_path_layout.setSpacing(ROW_GAP)

        export_path_layout.addWidget(QLabel("預設匯出目錄"))
        path_row = QHBoxLayout()
        self._export_dir_input = QLineEdit()
        self._export_dir_input.setPlaceholderText("留空則由系統記憶或預設儲存位置")
        self._export_dir_input.setAccessibleName("預設匯出目錄")
        path_row.addWidget(self._export_dir_input, 1)

        self._browse_dir_button = QPushButton("瀏覽...")
        self._browse_dir_button.setProperty("variant", "secondary")
        self._browse_dir_button.setCursor(Qt.PointingHandCursor)
        self._browse_dir_button.setAccessibleName("瀏覽選擇預設匯出目錄")
        self._browse_dir_button.clicked.connect(self._on_browse_export_dir)
        path_row.addWidget(self._browse_dir_button)
        export_path_layout.addLayout(path_row)

        export_path_layout.addWidget(QLabel("匯出檔案命名格式"))
        self._export_naming_group = QButtonGroup(self)
        self._export_naming_buttons = {}
        for value, label, description in (
            ("standard", "標準格式 (報表名_日期.xlsx)", "例如：SQE_異常事件清單_20260816.xlsx。"),
            ("detailed", "詳細格式 (單位_報表名_日期.xlsx)", "例如：品質部_異常事件清單_20260816.xlsx。"),
            ("compact", "緊湊格式 (報表名_時間戳記.xlsx)", "例如：異常清單_20260816_143000.xlsx。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"匯出命名格式：{label}")
            radio.setToolTip(description)
            self._export_naming_group.addButton(radio)
            self._export_naming_buttons[value] = radio
            export_path_layout.addWidget(radio)

        export_path_layout.addWidget(QLabel("匯出完成後動作"))
        self._export_action_group = QButtonGroup(self)
        self._export_action_buttons = {}
        for value, label, description in (
            ("open_file", "自動開啟檔案 (預設)", "匯出完成後自動以預設應用程式開啟檔案。"),
            ("open_folder", "開啟所在資料夾", "匯出完成後在檔案總管中顯示該檔案所在資料夾。"),
            ("notify_only", "僅顯示完成通知", "匯出完成後僅於狀態列或彈窗提示，不自動開啟。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"匯出完成後動作：{label}")
            radio.setToolTip(description)
            self._export_action_group.addButton(radio)
            self._export_action_buttons[value] = radio
            export_path_layout.addWidget(radio)
        left_export_col.addWidget(export_path_group)
        left_export_col.addStretch(1)

        # Tab 3 - Right: 報告抬頭與 PDF/Excel 設定
        right_export_col = QVBoxLayout()
        right_export_col.setSpacing(ROW_GAP)

        report_style_group = QGroupBox("報告抬頭與格式選項")
        report_style_layout = QVBoxLayout(report_style_group)
        report_style_layout.setSpacing(ROW_GAP)

        report_style_layout.addWidget(QLabel("報告單位抬頭名稱"))
        self._report_header_input = QLineEdit()
        self._report_header_input.setPlaceholderText("例如：SQE 供應商品質工程部")
        self._report_header_input.setAccessibleName("報告單位抬頭名稱")
        self._report_header_input.setToolTip("用於 PDF 與 Excel 匯出報表首頁與頁首的公司/部門名稱。")
        report_style_layout.addWidget(self._report_header_input)

        report_style_layout.addWidget(QLabel("Excel 匯出樣式主題"))
        self._excel_theme_group = QButtonGroup(self)
        self._excel_theme_buttons = {}
        excel_theme_row = QHBoxLayout()
        for value, label, description in (
            ("classic_navy", "海軍經典藍", "經典商務海軍深藍風格表頭。"),
            ("slate_gray", "冷灰極簡", "現代冷灰低飽和度風格。"),
            ("forest_green", "墨綠工程", "穩重墨綠工程品質管理風格。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"Excel樣式主題：{label}")
            radio.setToolTip(description)
            self._excel_theme_group.addButton(radio)
            self._excel_theme_buttons[value] = radio
            excel_theme_row.addWidget(radio)
        report_style_layout.addLayout(excel_theme_row)

        report_style_layout.addWidget(QLabel("PDF 匯出頁面預設方向"))
        self._pdf_orientation_group = QButtonGroup(self)
        self._pdf_orientation_buttons = {}
        pdf_ori_row = QHBoxLayout()
        for value, label, description in (
            ("portrait", "直向 (Portrait)", "標準直向 A4 報表輸出。"),
            ("landscape", "橫向 (Landscape)", "寬版橫向輸出，適合大量欄位報表。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"PDF 頁面方向：{label}")
            radio.setToolTip(description)
            self._pdf_orientation_group.addButton(radio)
            self._pdf_orientation_buttons[value] = radio
            pdf_ori_row.addWidget(radio)
        report_style_layout.addLayout(pdf_ori_row)

        report_style_layout.addWidget(QLabel("PDF 報表版面緊湊度"))
        self._pdf_density_group = QButtonGroup(self)
        self._pdf_density_buttons = {}
        pdf_density_row = QHBoxLayout()
        for value, label, description in (
            ("standard", "標準版面", "適度留白，適合閱讀與正式提報。"),
            ("compact", "緊湊節省紙張", "縮小行距與字級，減少列印頁數。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"PDF版面緊湊度：{label}")
            radio.setToolTip(description)
            self._pdf_density_group.addButton(radio)
            self._pdf_density_buttons[value] = radio
            pdf_density_row.addWidget(radio)
        report_style_layout.addLayout(pdf_density_row)

        report_style_layout.addWidget(QLabel("PDF 匯出浮水印標示"))
        self._pdf_watermark_input = QLineEdit()
        self._pdf_watermark_input.setPlaceholderText("例如：內部品質文件 / SQE 專用（留空則無浮水印）")
        self._pdf_watermark_input.setAccessibleName("PDF 浮水印文字")
        self._pdf_watermark_input.setToolTip("在 PDF 匯出報表頁面背景繪製半透明浮水印字樣。")
        report_style_layout.addWidget(self._pdf_watermark_input)

        self._export_charts_checkbox = QCheckBox("Excel 匯出預設包含 Pareto 統計圖表")
        self._export_charts_checkbox.setAccessibleName("Excel 匯出包含統計圖表")
        self._export_charts_checkbox.setToolTip("在品質統計匯出 Excel 報表時自動嵌入 Pareto 分析圖表與圖片。")
        self._export_charts_checkbox.setAccessibleDescription("在品質統計匯出 Excel 報表時自動嵌入 Pareto 分析圖表與圖片。")
        report_style_layout.addWidget(self._export_charts_checkbox)

        self._excel_autofit_checkbox = QCheckBox("Excel 匯出自動調整欄寬最佳化")
        self._excel_autofit_checkbox.setAccessibleName("Excel 匯出自動調整欄寬")
        self._excel_autofit_checkbox.setToolTip("在匯出 Excel 時依據文字長度自動調整儲存格欄寬以防截斷。")
        self._excel_autofit_checkbox.setAccessibleDescription("在匯出 Excel 時依據文字長度自動調整儲存格欄寬以防截斷。")
        report_style_layout.addWidget(self._excel_autofit_checkbox)

        self._export_disclaimer_checkbox = QCheckBox("匯出報表包含品質工程保密聲明")
        self._export_disclaimer_checkbox.setAccessibleName("匯出包含保密聲明")
        self._export_disclaimer_checkbox.setToolTip("在報表頁尾自動附上內部品質管理專用與保密免責聲明。")
        self._export_disclaimer_checkbox.setAccessibleDescription("在報表頁尾自動附上內部品質管理專用與保密免責聲明。")
        report_style_layout.addWidget(self._export_disclaimer_checkbox)

        self._export_summary_sheet_checkbox = QCheckBox("Excel 匯出自動附加統計摘要工作表")
        self._export_summary_sheet_checkbox.setAccessibleName("Excel 匯出附加摘要工作表")
        self._export_summary_sheet_checkbox.setToolTip("在多筆異常或訪廠匯出時於第一頁附加統計總覽與圓餅圖摘要工作表。")
        self._export_summary_sheet_checkbox.setAccessibleDescription("在多筆異常或訪廠匯出時於第一頁附加統計總覽與圓餅圖摘要工作表。")
        report_style_layout.addWidget(self._export_summary_sheet_checkbox)

        self._pdf_header_logo_checkbox = QCheckBox("PDF 報表頁首顯示品質部徽章標記")
        self._pdf_header_logo_checkbox.setAccessibleName("PDF 頁首顯示品質標記")
        self._pdf_header_logo_checkbox.setToolTip("在 PDF 正式報表頁首右上方繪製品質工程 SQE 標誌。")
        self._pdf_header_logo_checkbox.setAccessibleDescription("在 PDF 正式報表頁首右上方繪製品質工程 SQE 標誌。")
        report_style_layout.addWidget(self._pdf_header_logo_checkbox)
        right_export_col.addWidget(report_style_group)
        right_export_col.addStretch(1)

        export_grid.addLayout(left_export_col, 0, 0)
        export_grid.addLayout(right_export_col, 0, 1)
        self._stacked_widget.addWidget(self._create_scrollable_tab(export_page))

        # ── Tab 4: 系統、通知與備份 (System, Notifications & Backup) ──
        system_page = QWidget()
        system_grid = QGridLayout(system_page)
        system_grid.setContentsMargins(4, 4, 4, 4)
        system_grid.setSpacing(12)

        # Tab 4 - Left: 啟動頁面、日誌與安全操作
        left_sys_col = QVBoxLayout()
        left_sys_col.setSpacing(ROW_GAP)

        startup_group = QGroupBox("啟動、日誌與操作防護")
        startup_layout = QVBoxLayout(startup_group)
        startup_layout.setSpacing(ROW_GAP)

        startup_layout.addWidget(QLabel("預設啟動頁面"))
        self._startup_page_group = QButtonGroup(self)
        self._startup_page_buttons = {}
        startup_grid = QGridLayout()
        pages = [
            ("home", "首頁儀表板", "開啟應用程式時預設顯示首頁與待辦面板。"),
            ("events", "訪廠與異常事件", "開啟應用程式時預設進入供應商訪廠與品質異常清單。"),
            ("defects", "倉庫不良品紀錄", "開啟應用程式時預設進入實體不良品倉庫清單。"),
            ("stats", "品質統計分析", "開啟應用程式時預設進入品質 Pareto 與統計圖表。"),
        ]
        for idx, (value, label, description) in enumerate(pages):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設啟動頁面：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._startup_page_group.addButton(radio)
            self._startup_page_buttons[value] = radio
            startup_grid.addWidget(radio, idx // 2, idx % 2)
        startup_layout.addLayout(startup_grid)

        startup_layout.addWidget(QLabel("系統日誌記錄等級"))
        self._log_level_group = QButtonGroup(self)
        self._log_level_buttons = {}
        log_level_row = QHBoxLayout()
        for value, label, description in (
            ("INFO", "標準 (INFO)", "記錄一般操作與關鍵業務事件。"),
            ("DEBUG", "除錯 (DEBUG)", "記錄詳細資料庫查詢與除錯追蹤日誌。"),
            ("WARNING", "僅警示 (WARN)", "僅記錄警告與嚴重異常錯誤。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"日誌等級：{label}")
            radio.setToolTip(description)
            self._log_level_group.addButton(radio)
            self._log_level_buttons[value] = radio
            log_level_row.addWidget(radio)
        startup_layout.addLayout(log_level_row)

        startup_layout.addWidget(QLabel("資料匯入衝突策略"))
        self._import_conflict_group = QButtonGroup(self)
        self._import_conflict_buttons = {}
        import_conflict_row = QHBoxLayout()
        for value, label, description in (
            ("prompt", "提示確認", "遇到重複料號或單號時跳出詢問。"),
            ("skip", "略過重複", "自動保留既有資料並略過衝突資料列。"),
            ("overwrite", "覆蓋更新", "以匯入檔案最新內容直接覆蓋。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"匯入衝突策略：{label}")
            radio.setToolTip(description)
            self._import_conflict_group.addButton(radio)
            self._import_conflict_buttons[value] = radio
            import_conflict_row.addWidget(radio)
        startup_layout.addLayout(import_conflict_row)

        self._confirm_delete_checkbox = QCheckBox("執行資料刪除操作時強制二次確認")
        self._confirm_delete_checkbox.setAccessibleName("資料刪除二次確認")
        self._confirm_delete_checkbox.setToolTip("刪除異常單、訪廠或不良品紀錄時跳出確認視窗。")
        self._confirm_delete_checkbox.setAccessibleDescription("刪除異常單、訪廠或不良品紀錄時跳出確認視窗。")
        startup_layout.addWidget(self._confirm_delete_checkbox)

        self._auto_check_unresolved_checkbox = QCheckBox("啟動時於狀態列自動提示待辦異常筆數")
        self._auto_check_unresolved_checkbox.setAccessibleName("啟動自動提示待辦筆數")
        self._auto_check_unresolved_checkbox.setToolTip("在系統啟動完成後自動檢查並在狀態列提示待處理之品質異常筆數。")
        self._auto_check_unresolved_checkbox.setAccessibleDescription("在系統啟動完成後自動檢查並在狀態列提示待處理之品質異常筆數。")
        startup_layout.addWidget(self._auto_check_unresolved_checkbox)

        self._auto_save_drafts_checkbox = QCheckBox("表單編輯中斷時自動暫存草稿")
        self._auto_save_drafts_checkbox.setAccessibleName("自動暫存表單草稿")
        self._auto_save_drafts_checkbox.setToolTip("未提交的表單內容於異常退出時保留為本機草稿。")
        self._auto_save_drafts_checkbox.setAccessibleDescription("未提交的表單內容於異常退出時保留為本機草稿。")
        startup_layout.addWidget(self._auto_save_drafts_checkbox)

        self._clean_temp_checkbox = QCheckBox("關閉程式時自動清理暫存預覽報表")
        self._clean_temp_checkbox.setAccessibleName("關閉程式清理暫存")
        self._clean_temp_checkbox.setToolTip("結束工作區時自動清除暫存目錄下生成的 PDF 與 Excel 預覽檔案。")
        self._clean_temp_checkbox.setAccessibleDescription("結束工作區時自動清除暫存目錄下生成的 PDF 與 Excel 預覽檔案。")
        startup_layout.addWidget(self._clean_temp_checkbox)

        self._session_restore_filters_checkbox = QCheckBox("啟動時自動還原前次搜尋過濾條件")
        self._session_restore_filters_checkbox.setAccessibleName("啟動自動還原過濾條件")
        self._session_restore_filters_checkbox.setToolTip("啟動應用程式時自動載入前次離開各清單頁面時所設定的搜尋關鍵字與範圍。")
        self._session_restore_filters_checkbox.setAccessibleDescription("啟動應用程式時自動載入前次離開各清單頁面時所設定的搜尋關鍵字與範圍。")
        startup_layout.addWidget(self._session_restore_filters_checkbox)
        left_sys_col.addWidget(startup_group)
        left_sys_col.addStretch(1)

        # Tab 4 - Right: 逾期預警與資料庫備份
        right_sys_col = QVBoxLayout()
        right_sys_col.setSpacing(ROW_GAP)

        overdue_group = QGroupBox("待辦事項逾期預警")
        overdue_layout = QVBoxLayout(overdue_group)
        overdue_layout.setSpacing(ROW_GAP)

        overdue_layout.addWidget(QLabel("首頁待辦逾期預警天數閾值"))
        self._overdue_days_group = QButtonGroup(self)
        self._overdue_days_buttons = {}
        overdue_grid = QGridLayout()
        overdue_options = [
            (3, "3 天內即將到期", "距改善截止日不足 3 天時於待辦清單中顯示警示。"),
            (7, "7 天內即將到期 (預設)", "距改善截止日不足 7 天時顯示警示。"),
            (14, "14 天內即將到期", "距改善截止日不足 14 天時顯示警示。"),
            (0, "關閉預警提示", "不進行即將到期之提前警示提示。"),
        ]
        for idx, (value, label, description) in enumerate(overdue_options):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"逾期預警天數：{label}")
            radio.setToolTip(description)
            self._overdue_days_group.addButton(radio)
            self._overdue_days_buttons[value] = radio
            overdue_grid.addWidget(radio, idx // 2, idx % 2)
        overdue_layout.addLayout(overdue_grid)
        right_sys_col.addWidget(overdue_group)

        backup_group = QGroupBox("資料庫自動備份與維護")
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.setSpacing(ROW_GAP)

        self._auto_backup_checkbox = QCheckBox("關閉程式時顯示資料自動備份提醒")
        self._auto_backup_checkbox.setAccessibleName("關閉程式時顯示資料自動備份提醒")
        self._auto_backup_checkbox.setToolTip("結束工作區時自動檢查並提示建立 SQLite 備份。")
        self._auto_backup_checkbox.setAccessibleDescription("結束工作區時自動檢查並提示建立 SQLite 備份。")
        self._auto_backup_checkbox.toggled.connect(self._preview_from_controls)
        backup_layout.addWidget(self._auto_backup_checkbox)

        backup_layout.addWidget(QLabel("自動備份保留份數上限"))
        self._retention_count_group = QButtonGroup(self)
        self._retention_count_buttons = {}
        retention_grid = QGridLayout()
        retentions = [
            (5, "5 份", "保留最近 5 份備份檔案。"),
            (10, "10 份 (預設)", "保留最近 10 份備份檔案。"),
            (20, "20 份", "保留最近 20 份備份檔案。"),
            (30, "30 份", "保留最近 30 份備份檔案。"),
        ]
        for idx, (value, label, description) in enumerate(retentions):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"備份保留份數：{label}")
            radio.setToolTip(description)
            self._retention_count_group.addButton(radio)
            self._retention_count_buttons[value] = radio
            retention_grid.addWidget(radio, idx // 2, idx % 2)
        backup_layout.addLayout(retention_grid)

        self._auto_compact_db_checkbox = QCheckBox("關閉程式時自動壓縮重組資料庫 (VACUUM)")
        self._auto_compact_db_checkbox.setAccessibleName("關閉程式壓縮資料庫")
        self._auto_compact_db_checkbox.setToolTip("在結束程式時對 SQLite 資料庫執行 VACUUM 最佳化，釋放未使用的磁碟空間。")
        self._auto_compact_db_checkbox.setAccessibleDescription("在結束程式時對 SQLite 資料庫執行 VACUUM 最佳化，釋放未使用的磁碟空間。")
        backup_layout.addWidget(self._auto_compact_db_checkbox)
        right_sys_col.addWidget(backup_group)
        right_sys_col.addStretch(1)

        system_grid.addLayout(left_sys_col, 0, 0)
        system_grid.addLayout(right_sys_col, 0, 1)
        self._stacked_widget.addWidget(self._create_scrollable_tab(system_page))

        # Default select the first category
        self._category_list.setCurrentRow(0)

        # ── Pinned Footer ──
        footer = QHBoxLayout()
        self.reset_button = QPushButton("還原預設")
        self.reset_button.setProperty("variant", "secondary")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setAccessibleName("還原介面與系統預設值")
        apply_clickable_affordance(self.reset_button, tooltip="預覽所有介面與系統偏好的預設值；尚未儲存")
        self.reset_button.clicked.connect(self._reset_defaults)
        footer.addWidget(self.reset_button)
        footer.addStretch(1)
        self.save_button = QPushButton("儲存並套用")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setAccessibleName("儲存並套用介面與系統預設值")
        apply_clickable_affordance(self.save_button, tooltip="儲存此電腦的介面與系統偏好")
        self.save_button.clicked.connect(self._save_and_accept)
        footer.addWidget(self.save_button)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setProperty("variant", "secondary")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setAccessibleName("取消介面變更")
        apply_clickable_affordance(self.cancel_button, tooltip="放棄本次預覽並還原原先的偏好")
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        root.addLayout(footer)

    def _on_browse_export_dir(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "選取預設匯出目錄",
            self._export_dir_input.text().strip() or "",
        )
        if selected_dir:
            self._export_dir_input.setText(selected_dir)

    def _current_preferences(self) -> AppearancePreferences:
        # Tab 0: 外觀與風格
        density = next(val for val, btn in self._density_buttons.items() if btn.isChecked())
        sidebar_density = next(val for val, btn in self._sidebar_density_buttons.items() if btn.isChecked())
        sidebar_icon_mode = next(val for val, btn in self._sidebar_icon_buttons.items() if btn.isChecked())
        accent_color = next(val for val, btn in self._accent_color_buttons.items() if btn.isChecked())
        text_scale = next(val for val, btn in self._text_scale_buttons.items() if btn.isChecked())
        contrast_mode = next(val for val, btn in self._contrast_mode_buttons.items() if btn.isChecked())
        theme_mode = next(val for val, btn in self._theme_mode_buttons.items() if btn.isChecked())
        cjk_font = next(val for val, btn in self._cjk_font_buttons.items() if btn.isChecked())
        window_geometry = next(val for val, btn in self._window_geometry_buttons.items() if btn.isChecked())
        status_bar_detail = next(val for val, btn in self._status_bar_detail_buttons.items() if btn.isChecked())

        # Tab 1: 表格與檢視
        table_density = next(val for val, btn in self._table_density_buttons.items() if btn.isChecked())
        page_limit = next(val for val, btn in self._page_limit_buttons.items() if btn.isChecked())
        date_format = next(val for val, btn in self._date_format_buttons.items() if btn.isChecked())
        double_click_action = next(val for val, btn in self._double_click_buttons.items() if btn.isChecked())
        search_mode = next(val for val, btn in self._search_mode_buttons.items() if btn.isChecked())
        stats_span = next(val for val, btn in self._stats_span_buttons.items() if btn.isChecked())
        list_sort = next(val for val, btn in self._list_sort_buttons.items() if btn.isChecked())
        text_wrapping = next(val for val, btn in self._text_wrapping_buttons.items() if btn.isChecked())

        # Tab 2: 表單與業務
        due_days = next(val for val, btn in self._due_days_buttons.items() if btn.isChecked())
        visit_time_slot = next(val for val, btn in self._visit_time_slot_buttons.items() if btn.isChecked())
        severity_level = next(val for val, btn in self._severity_level_buttons.items() if btn.isChecked())
        sample_size = next(val for val, btn in self._defect_sample_size_buttons.items() if btn.isChecked())

        # Tab 3: 匯出與報表
        export_action = next(val for val, btn in self._export_action_buttons.items() if btn.isChecked())
        export_naming = next(val for val, btn in self._export_naming_buttons.items() if btn.isChecked())
        pdf_orientation = next(val for val, btn in self._pdf_orientation_buttons.items() if btn.isChecked())
        excel_theme = next(val for val, btn in self._excel_theme_buttons.items() if btn.isChecked())
        pdf_density = next(val for val, btn in self._pdf_density_buttons.items() if btn.isChecked())

        # Tab 4: 系統與維護
        startup_page = next(val for val, btn in self._startup_page_buttons.items() if btn.isChecked())
        retention_count = next(val for val, btn in self._retention_count_buttons.items() if btn.isChecked())
        overdue_days = next(val for val, btn in self._overdue_days_buttons.items() if btn.isChecked())
        log_level = next(val for val, btn in self._log_level_buttons.items() if btn.isChecked())
        import_conflict = next(val for val, btn in self._import_conflict_buttons.items() if btn.isChecked())

        return AppearancePreferences(
            density=density,
            sidebar_density=sidebar_density,
            sidebar_icon_mode=sidebar_icon_mode,
            accent_color=accent_color,
            text_scale=text_scale,
            contrast_mode=contrast_mode,
            theme_mode=theme_mode,
            cjk_font_family_preference=cjk_font,
            window_geometry_mode=window_geometry,
            status_bar_detail_level=status_bar_detail,
            table_density=table_density,
            alternating_row_colors=self._alt_row_checkbox.isChecked(),
            table_grid_lines=self._grid_lines_checkbox.isChecked(),
            table_page_limit=page_limit,
            enable_animations=self._animations_checkbox.isChecked(),
            table_double_click_action=double_click_action,
            search_mode=search_mode,
            stats_default_span_months=stats_span,
            pareto_show_cutoff_line=self._pareto_cutoff_checkbox.isChecked(),
            highlight_overdue_rows=self._highlight_overdue_checkbox.isChecked(),
            date_format_display=date_format,
            table_auto_scroll_to_top=self._auto_scroll_top_checkbox.isChecked(),
            table_hover_highlight=self._hover_highlight_checkbox.isChecked(),
            table_text_wrapping=text_wrapping,
            default_list_sort_field=list_sort,
            table_show_row_numbers=self._table_show_row_numbers_checkbox.isChecked(),
            quick_filter_case_sensitive=self._quick_filter_case_checkbox.isChecked(),
            default_responsible_person=self._responsible_person_input.text().strip(),
            default_anomaly_category=self._anomaly_category_combo.currentText().strip(),
            default_sync_visit=self._sync_visit_checkbox.isChecked(),
            default_due_days=due_days,
            default_visit_time_slot=visit_time_slot,
            default_anomaly_source=self._anomaly_source_combo.currentText().strip(),
            default_severity_level=severity_level,
            default_visit_type=self._visit_type_combo.currentText().strip() or "例行訪廠",
            auto_fill_anomaly_no_on_date_change=self._auto_anomaly_no_checkbox.isChecked(),
            default_closer_name=self._closer_name_input.text().strip(),
            default_defect_disposition=self._defect_disposition_combo.currentText().strip(),
            auto_uppercase_part_no=self._auto_uppercase_checkbox.isChecked(),
            default_defect_sample_size=sample_size,
            require_defect_photos=self._require_defect_photos_checkbox.isChecked(),
            default_export_dir=self._export_dir_input.text().strip(),
            export_completion_action=export_action,
            report_organization_header=self._report_header_input.text().strip() or "SQE 供應商品質工程部",
            export_include_charts=self._export_charts_checkbox.isChecked(),
            export_file_naming_rule=export_naming,
            pdf_page_orientation=pdf_orientation,
            pdf_watermark_text=self._pdf_watermark_input.text().strip(),
            excel_autofit_columns=self._excel_autofit_checkbox.isChecked(),
            excel_theme_style=excel_theme,
            pdf_font_density=pdf_density,
            export_include_disclaimer=self._export_disclaimer_checkbox.isChecked(),

            export_include_summary_sheet=self._export_summary_sheet_checkbox.isChecked(),
            pdf_header_logo_visible=self._pdf_header_logo_checkbox.isChecked(),
            default_startup_page=startup_page,
            auto_backup_prompt=self._auto_backup_checkbox.isChecked(),
            backup_retention_count=retention_count,
            confirm_on_delete=self._confirm_delete_checkbox.isChecked(),
            overdue_reminder_days=overdue_days,
            auto_check_unresolved_on_startup=self._auto_check_unresolved_checkbox.isChecked(),
            clean_temp_files_on_exit=self._clean_temp_checkbox.isChecked(),
            log_level=log_level,
            auto_save_drafts=self._auto_save_drafts_checkbox.isChecked(),
            import_conflict_strategy=import_conflict,
            session_restore_last_filters=self._session_restore_filters_checkbox.isChecked(),
            auto_compact_db_on_exit=self._auto_compact_db_checkbox.isChecked(),
        )

    def _set_preferences(self, preferences: AppearancePreferences, *, preview: bool) -> None:
        blockers = [
            *[QSignalBlocker(btn) for btn in self._density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._sidebar_density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._sidebar_icon_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._table_density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._accent_color_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._text_scale_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._contrast_mode_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._theme_mode_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._cjk_font_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._window_geometry_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._status_bar_detail_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._startup_page_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._page_limit_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._date_format_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._due_days_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._visit_time_slot_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._severity_level_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._defect_sample_size_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._export_action_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._export_naming_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._pdf_orientation_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._excel_theme_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._pdf_density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._retention_count_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._overdue_days_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._double_click_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._search_mode_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._stats_span_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._list_sort_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._text_wrapping_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._log_level_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._import_conflict_buttons.values()],
            QSignalBlocker(self._alt_row_checkbox),
            QSignalBlocker(self._grid_lines_checkbox),
            QSignalBlocker(self._hover_highlight_checkbox),
            QSignalBlocker(self._highlight_overdue_checkbox),
            QSignalBlocker(self._auto_scroll_top_checkbox),
            QSignalBlocker(self._animations_checkbox),
            QSignalBlocker(self._table_show_row_numbers_checkbox),
            QSignalBlocker(self._quick_filter_case_checkbox),
            QSignalBlocker(self._auto_backup_checkbox),
            QSignalBlocker(self._auto_compact_db_checkbox),
            QSignalBlocker(self._sync_visit_checkbox),
            QSignalBlocker(self._auto_anomaly_no_checkbox),
            QSignalBlocker(self._auto_uppercase_checkbox),
            QSignalBlocker(self._require_defect_photos_checkbox),
            QSignalBlocker(self._export_charts_checkbox),
            QSignalBlocker(self._excel_autofit_checkbox),
            QSignalBlocker(self._export_disclaimer_checkbox),
            QSignalBlocker(self._export_summary_sheet_checkbox),
            QSignalBlocker(self._pdf_header_logo_checkbox),
            QSignalBlocker(self._confirm_delete_checkbox),
            QSignalBlocker(self._auto_check_unresolved_checkbox),
            QSignalBlocker(self._auto_save_drafts_checkbox),
            QSignalBlocker(self._clean_temp_checkbox),
            QSignalBlocker(self._session_restore_filters_checkbox),
            QSignalBlocker(self._pareto_cutoff_checkbox),
            QSignalBlocker(self._responsible_person_input),
            QSignalBlocker(self._closer_name_input),
            QSignalBlocker(self._anomaly_category_combo),
            QSignalBlocker(self._anomaly_source_combo),
            QSignalBlocker(self._visit_type_combo),
            QSignalBlocker(self._defect_disposition_combo),
            QSignalBlocker(self._export_dir_input),
            QSignalBlocker(self._report_header_input),
            QSignalBlocker(self._pdf_watermark_input),
        ]

        # Tab 0: 外觀與風格
        self._density_buttons[preferences.density].setChecked(True)
        self._sidebar_density_buttons[preferences.sidebar_density].setChecked(True)
        if preferences.sidebar_icon_mode in self._sidebar_icon_buttons:
            self._sidebar_icon_buttons[preferences.sidebar_icon_mode].setChecked(True)
        if preferences.accent_color in self._accent_color_buttons:
            self._accent_color_buttons[preferences.accent_color].setChecked(True)
        self._text_scale_buttons[preferences.text_scale].setChecked(True)
        self._contrast_mode_buttons[preferences.contrast_mode].setChecked(True)
        if preferences.theme_mode in self._theme_mode_buttons:
            self._theme_mode_buttons[preferences.theme_mode].setChecked(True)
        if preferences.cjk_font_family_preference in self._cjk_font_buttons:
            self._cjk_font_buttons[preferences.cjk_font_family_preference].setChecked(True)
        if preferences.window_geometry_mode in self._window_geometry_buttons:
            self._window_geometry_buttons[preferences.window_geometry_mode].setChecked(True)
        if preferences.status_bar_detail_level in self._status_bar_detail_buttons:
            self._status_bar_detail_buttons[preferences.status_bar_detail_level].setChecked(True)

        # Tab 1: 表格與檢視
        self._table_density_buttons[preferences.table_density].setChecked(True)
        self._page_limit_buttons[preferences.table_page_limit].setChecked(True)
        if preferences.date_format_display in self._date_format_buttons:
            self._date_format_buttons[preferences.date_format_display].setChecked(True)
        self._alt_row_checkbox.setChecked(preferences.alternating_row_colors)
        self._grid_lines_checkbox.setChecked(preferences.table_grid_lines)
        self._hover_highlight_checkbox.setChecked(preferences.table_hover_highlight)
        self._highlight_overdue_checkbox.setChecked(preferences.highlight_overdue_rows)
        self._auto_scroll_top_checkbox.setChecked(preferences.table_auto_scroll_to_top)
        self._animations_checkbox.setChecked(preferences.enable_animations)
        self._table_show_row_numbers_checkbox.setChecked(preferences.table_show_row_numbers)
        self._quick_filter_case_checkbox.setChecked(preferences.quick_filter_case_sensitive)

        if preferences.table_double_click_action in self._double_click_buttons:
            self._double_click_buttons[preferences.table_double_click_action].setChecked(True)
        if preferences.search_mode in self._search_mode_buttons:
            self._search_mode_buttons[preferences.search_mode].setChecked(True)
        if preferences.stats_default_span_months in self._stats_span_buttons:
            self._stats_span_buttons[preferences.stats_default_span_months].setChecked(True)
        self._pareto_cutoff_checkbox.setChecked(preferences.pareto_show_cutoff_line)
        if preferences.default_list_sort_field in self._list_sort_buttons:
            self._list_sort_buttons[preferences.default_list_sort_field].setChecked(True)
        if preferences.table_text_wrapping in self._text_wrapping_buttons:
            self._text_wrapping_buttons[preferences.table_text_wrapping].setChecked(True)

        # Tab 2: 表單與業務
        self._responsible_person_input.setText(preferences.default_responsible_person)
        self._closer_name_input.setText(preferences.default_closer_name)
        cat_idx = self._anomaly_category_combo.findText(preferences.default_anomaly_category)
        if cat_idx >= 0:
            self._anomaly_category_combo.setCurrentIndex(cat_idx)
        src_idx = self._anomaly_source_combo.findText(preferences.default_anomaly_source)
        if src_idx >= 0:
            self._anomaly_source_combo.setCurrentIndex(src_idx)
        if preferences.default_severity_level in self._severity_level_buttons:
            self._severity_level_buttons[preferences.default_severity_level].setChecked(True)
        self._sync_visit_checkbox.setChecked(preferences.default_sync_visit)
        self._auto_anomaly_no_checkbox.setChecked(preferences.auto_fill_anomaly_no_on_date_change)
        self._auto_uppercase_checkbox.setChecked(preferences.auto_uppercase_part_no)
        self._require_defect_photos_checkbox.setChecked(preferences.require_defect_photos)
        if preferences.default_due_days in self._due_days_buttons:
            self._due_days_buttons[preferences.default_due_days].setChecked(True)
        visit_type_idx = self._visit_type_combo.findText(preferences.default_visit_type)
        if visit_type_idx >= 0:
            self._visit_type_combo.setCurrentIndex(visit_type_idx)
        disp_idx = self._defect_disposition_combo.findText(preferences.default_defect_disposition)
        if disp_idx >= 0:
            self._defect_disposition_combo.setCurrentIndex(disp_idx)
        if preferences.default_visit_time_slot in self._visit_time_slot_buttons:
            self._visit_time_slot_buttons[preferences.default_visit_time_slot].setChecked(True)
        if preferences.default_defect_sample_size in self._defect_sample_size_buttons:
            self._defect_sample_size_buttons[preferences.default_defect_sample_size].setChecked(True)

        # Tab 3: 匯出與報表
        self._export_dir_input.setText(preferences.default_export_dir)
        if preferences.export_completion_action in self._export_action_buttons:
            self._export_action_buttons[preferences.export_completion_action].setChecked(True)
        if preferences.export_file_naming_rule in self._export_naming_buttons:
            self._export_naming_buttons[preferences.export_file_naming_rule].setChecked(True)
        self._report_header_input.setText(preferences.report_organization_header)
        if preferences.pdf_page_orientation in self._pdf_orientation_buttons:
            self._pdf_orientation_buttons[preferences.pdf_page_orientation].setChecked(True)
        if preferences.excel_theme_style in self._excel_theme_buttons:
            self._excel_theme_buttons[preferences.excel_theme_style].setChecked(True)
        if preferences.pdf_font_density in self._pdf_density_buttons:
            self._pdf_density_buttons[preferences.pdf_font_density].setChecked(True)
        self._pdf_watermark_input.setText(preferences.pdf_watermark_text)
        self._export_charts_checkbox.setChecked(preferences.export_include_charts)
        self._excel_autofit_checkbox.setChecked(preferences.excel_autofit_columns)
        self._export_disclaimer_checkbox.setChecked(preferences.export_include_disclaimer)
        self._export_summary_sheet_checkbox.setChecked(preferences.export_include_summary_sheet)
        self._pdf_header_logo_checkbox.setChecked(preferences.pdf_header_logo_visible)

        # Tab 4: 系統與維護
        self._startup_page_buttons[preferences.default_startup_page].setChecked(True)
        self._confirm_delete_checkbox.setChecked(preferences.confirm_on_delete)
        self._auto_check_unresolved_checkbox.setChecked(preferences.auto_check_unresolved_on_startup)
        self._auto_save_drafts_checkbox.setChecked(preferences.auto_save_drafts)
        self._clean_temp_checkbox.setChecked(preferences.clean_temp_files_on_exit)
        self._session_restore_filters_checkbox.setChecked(preferences.session_restore_last_filters)
        if preferences.overdue_reminder_days in self._overdue_days_buttons:
            self._overdue_days_buttons[preferences.overdue_reminder_days].setChecked(True)
        self._auto_backup_checkbox.setChecked(preferences.auto_backup_prompt)
        self._auto_compact_db_checkbox.setChecked(preferences.auto_compact_db_on_exit)
        if preferences.backup_retention_count in self._retention_count_buttons:
            self._retention_count_buttons[preferences.backup_retention_count].setChecked(True)
        if preferences.log_level in self._log_level_buttons:
            self._log_level_buttons[preferences.log_level].setChecked(True)
        if preferences.import_conflict_strategy in self._import_conflict_buttons:
            self._import_conflict_buttons[preferences.import_conflict_strategy].setChecked(True)

        del blockers
        if preview:
            self._apply_preview(preferences)

    def _preview_from_controls(self, checked: bool) -> None:
        if checked:
            self._apply_preview(self._current_preferences())

    def _apply_preview(self, preferences: AppearancePreferences) -> None:
        from PySide6.QtWidgets import QApplication

        target_app = QApplication.instance()
        if target_app is not None:
            apply_app_theme(target_app, preferences)

    def _reset_defaults(self) -> None:
        self._set_preferences(AppearancePreferences.default(), preview=True)

    def _save_and_accept(self) -> None:
        preferences = self._current_preferences()
        try:
            save_application_preferences(preferences)
        except Exception as exc:
            QMessageBox.warning(self, "無法儲存", f"無法儲存介面與系統偏好：{exc}")
            return
        self._initial_preferences = preferences
        self.accept()

    def reject(self) -> None:
        self._apply_preview(self._initial_preferences)
        super().reject()
