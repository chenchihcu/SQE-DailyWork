"""Commercial-style, reversible display preference, business defaults and system settings dialog."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.appearance_preferences_service import (
    load_application_preferences,
    save_application_preferences,
)
from ui.appearance_preferences import (
    AppearancePreferences,
    BACKUP_RETENTION_COUNT_VALUES,
    DEFAULT_DUE_DAYS_VALUES,
    DEFAULT_VISIT_TIME_SLOT_VALUES,
    EXPORT_COMPLETION_ACTION_VALUES,
    SEARCH_MODE_VALUES,
    STATS_DEFAULT_SPAN_MONTHS_VALUES,
    TABLE_DOUBLE_CLICK_ACTION_VALUES,
)
from ui.layout_constants import FORM_MAX_WIDTH, PANEL_MARGINS, ROW_GAP
from ui.theme import apply_app_theme
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import apply_clickable_affordance
from ui.widgets.defect_form_widgets import ANOMALY_CATEGORY_OPTIONS


class AppearancePreferencesDialog(QDialog):
    """Preview, save, or discard global display, business and system default preferences."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppearancePreferencesDialog")
        self.setWindowTitle("系統與顯示設定")
        self.setModal(True)
        self._initial_preferences = load_application_preferences()
        self._build_ui()
        self._set_preferences(self._initial_preferences, preview=False)
        fit_dialog_to_available_screen(
            self,
            preferred_width=840,
            preferred_height=760,
            maximum_width=FORM_MAX_WIDTH,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PANEL_MARGINS)
        root.setSpacing(ROW_GAP)

        title = QLabel("系統與顯示設定")
        title.setProperty("role", "sectionTitle")
        title.setToolTip("調整本機介面外觀、業務預設、匯出報告與系統偏好；不影響既有品質資料與資料庫架構。")
        title.setAccessibleDescription("調整本機介面外觀、業務預設、匯出報告與系統偏好；不影響既有品質資料與資料庫架構。")
        root.addWidget(title)

        self.preference_tabs = QTabWidget()
        self.preference_tabs.setObjectName("AppearancePreferenceTabs")
        self.preference_tabs.setDocumentMode(True)
        root.addWidget(self.preference_tabs, 1)

        # ── Tab 1: 外觀主題 (Appearance & Theme) ──
        theme_page = QWidget()
        theme_root = QVBoxLayout(theme_page)
        theme_root.setContentsMargins(0, 0, 0, 0)
        theme_root.setSpacing(ROW_GAP)

        density_group = QGroupBox("版面與密度")
        density_layout = QVBoxLayout(density_group)
        density_layout.setSpacing(ROW_GAP)
        self._density_group = QButtonGroup(self)
        self._density_buttons = {}
        density_layout.addWidget(QLabel("全頁面控制項密度"))
        for value, label, description in (
            ("compact", "緊湊", "適合需要一次檢視更多列表與控制項的工作。"),
            ("standard", "標準", "平衡一般工作區的可讀性與資訊密度。"),
            ("comfortable", "舒適", "增加控制項與資料表的垂直留白，降低視覺擁擠。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"介面密度：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._density_group.addButton(radio)
            self._density_buttons[value] = radio
            density_layout.addWidget(radio)

        density_layout.addWidget(QLabel("側欄密度"))
        self._sidebar_density_group = QButtonGroup(self)
        self._sidebar_density_buttons = {}
        for value, label, description in (
            ("compact", "緊湊", "縮短側欄列高以顯示更多工作入口。"),
            ("standard", "標準", "使用既有可讀的側欄列高。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"側欄密度：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._sidebar_density_group.addButton(radio)
            self._sidebar_density_buttons[value] = radio
            density_layout.addWidget(radio)

        color_group = QGroupBox("主題色彩與文字大小")
        color_layout = QVBoxLayout(color_group)
        color_layout.setSpacing(ROW_GAP)

        color_layout.addWidget(QLabel("主題色彩 (Accent Color)"))
        self._accent_color_group = QButtonGroup(self)
        self._accent_color_buttons = {}
        for value, label, description in (
            ("electric_blue", "經典藍 (Classic Blue)", "預設 SQE Electric Blue 經典藍色主題。"),
            ("slate_navy", "海軍灰藍 (Navy Slate)", "沉穩灰藍調，適合長時間盯螢幕閱讀。"),
            ("emerald", "翡翠綠 (Emerald Green)", "清新墨綠調，高辨識度品質管理風格。"),
            ("amber", "溫和琥珀 (Warm Amber)", "暖色系琥珀調，舒適視覺焦點。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"主題色彩：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._accent_color_group.addButton(radio)
            self._accent_color_buttons[value] = radio
            color_layout.addWidget(radio)

        color_layout.addWidget(QLabel("文字大小"))
        self._text_scale_group = QButtonGroup(self)
        self._text_scale_buttons = {}
        for value, label, description in (
            ("standard", "標準", "使用 SQE DailyWork 的既有繁中字級階層。"),
            ("large", "放大", "放大應用程式文字以提升長時間閱讀的舒適度。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"文字大小：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._text_scale_group.addButton(radio)
            self._text_scale_buttons[value] = radio
            color_layout.addWidget(radio)

        color_layout.addWidget(QLabel("對比模式"))
        self._contrast_mode_group = QButtonGroup(self)
        self._contrast_mode_buttons = {}
        for value, label, description in (
            ("standard", "標準", "使用 SQE DailyWork 既有的專業主題。"),
            ("high", "高對比", "提升文字、邊框、焦點與選取狀態的辨識度。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"對比模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._contrast_mode_group.addButton(radio)
            self._contrast_mode_buttons[value] = radio
            color_layout.addWidget(radio)

        theme_root.addWidget(density_group)
        theme_root.addWidget(color_group)
        theme_root.addStretch(1)
        self.preference_tabs.addTab(theme_page, "外觀主題")

        # ── Tab 2: 視覺表格 (Visual & Tables) ──
        table_page = QWidget()
        table_root = QVBoxLayout(table_page)
        table_root.setContentsMargins(0, 0, 0, 0)
        table_root.setSpacing(ROW_GAP)

        table_density_group = QGroupBox("資料表檢視與密度")
        table_density_layout = QVBoxLayout(table_density_group)
        table_density_layout.setSpacing(ROW_GAP)

        table_density_layout.addWidget(QLabel("資料表閱讀密度"))
        self._table_density_group = QButtonGroup(self)
        self._table_density_buttons = {}
        for value, label, description in (
            ("compact", "緊湊", "縮短列高與表頭，適合大量資料比對。"),
            ("standard", "標準", "平衡表格可讀性與可視筆數。"),
            ("comfortable", "舒適", "增加列高與表頭高度，降低長時間閱讀負擔。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"資料表閱讀密度：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._table_density_group.addButton(radio)
            self._table_density_buttons[value] = radio
            table_density_layout.addWidget(radio)

        table_density_layout.addWidget(QLabel("資料表預設單頁筆數 (Table Page Limit)"))
        self._page_limit_group = QButtonGroup(self)
        self._page_limit_buttons = {}
        for value, label, description in (
            (25, "25 筆 / 頁", "每頁預設顯示 25 筆資料。"),
            (50, "50 筆 / 頁 (預設)", "每頁預設顯示 50 筆資料。"),
            (100, "100 筆 / 頁", "每頁預設顯示 100 筆資料。"),
            (0, "不分頁（顯示全部）", "不進行表格分頁，直接載入全部搜尋結果。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"資料表單頁筆數：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._page_limit_group.addButton(radio)
            self._page_limit_buttons[value] = radio
            table_density_layout.addWidget(radio)

        visual_helper_group = QGroupBox("視覺輔助與動效")
        visual_helper_layout = QVBoxLayout(visual_helper_group)
        visual_helper_layout.setSpacing(ROW_GAP)

        self._alt_row_checkbox = QCheckBox("顯示資料表交替行底色 (Alternating Row Colors)")
        self._alt_row_checkbox.setAccessibleName("顯示資料表交替行底色")
        self._alt_row_checkbox.setToolTip("使用雙色交替底色增強表格列視覺對位。")
        self._alt_row_checkbox.setAccessibleDescription("使用雙色交替底色增強表格列視覺對位。")
        self._alt_row_checkbox.toggled.connect(self._preview_from_controls)
        visual_helper_layout.addWidget(self._alt_row_checkbox)

        self._grid_lines_checkbox = QCheckBox("顯示資料表網格線 (Table Grid Lines)")
        self._grid_lines_checkbox.setAccessibleName("顯示資料表網格線")
        self._grid_lines_checkbox.setToolTip("顯示表格欄位與資料列間的微細網格線。")
        self._grid_lines_checkbox.setAccessibleDescription("顯示表格欄位與資料列間的微細網格線。")
        self._grid_lines_checkbox.toggled.connect(self._preview_from_controls)
        visual_helper_layout.addWidget(self._grid_lines_checkbox)

        self._animations_checkbox = QCheckBox("啟用微過場與動畫效果 (Enable Animations)")
        self._animations_checkbox.setAccessibleName("啟用微過場與動畫效果")
        self._animations_checkbox.setToolTip("在控制項懸停與視窗切換時啟用微動畫提示。")
        self._animations_checkbox.setAccessibleDescription("在控制項懸停與視窗切換時啟用微動畫提示。")
        self._animations_checkbox.toggled.connect(self._preview_from_controls)
        visual_helper_layout.addWidget(self._animations_checkbox)

        interaction_group = QGroupBox("資料表互動與搜尋模式")
        interaction_layout = QVBoxLayout(interaction_group)
        interaction_layout.setSpacing(ROW_GAP)

        interaction_layout.addWidget(QLabel("資料表列表列雙擊預設行為"))
        self._double_click_group = QButtonGroup(self)
        self._double_click_buttons = {}
        for value, label, description in (
            ("menu", "彈出操作選單 (預設)", "雙擊列表項目時彈出功能選單（編輯/結案/刪除/預覽等）。"),
            ("preview", "檢視預覽詳情", "雙擊列表項目時直接開啟事件詳情或預覽視窗。"),
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
        for value, label, description in (
            ("live", "即打即篩 (Live Search，預設)", "輸入關鍵字時即時過濾資料表列表。"),
            ("manual", "按 Enter 或點擊搜尋", "輸入完成後按 Enter 鍵或點擊搜尋按鈕才執行過濾。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"搜尋觸發模式：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._search_mode_group.addButton(radio)
            self._search_mode_buttons[value] = radio
            interaction_layout.addWidget(radio)

        stats_group = QGroupBox("品質統計與 Pareto 分析")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(ROW_GAP)

        stats_layout.addWidget(QLabel("預設統計區間跨度 (Default Stats Span)"))
        self._stats_span_group = QButtonGroup(self)
        self._stats_span_buttons = {}
        for value, label, description in (
            (3, "近 3 個月", "進入統計頁面時預設載入最近 3 個月的數據與圖表。"),
            (6, "近 6 個月 (預設)", "進入統計頁面時預設載入最近 6 個月的數據與圖表。"),
            (12, "近 1 年 (12 個月)", "進入統計頁面時預設載入最近 1 年的數據與圖表。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設統計區間：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            self._stats_span_group.addButton(radio)
            self._stats_span_buttons[value] = radio
            stats_layout.addWidget(radio)

        self._pareto_cutoff_checkbox = QCheckBox("顯示 Pareto 80/20 累計百分比警戒參考線 (Pareto 80% Cutoff Line)")
        self._pareto_cutoff_checkbox.setAccessibleName("顯示 Pareto 80/20 警戒參考線")
        self._pareto_cutoff_checkbox.setToolTip("在品質異常 Pareto 分析圖表 80% 處繪製輔助警戒虛線。")
        self._pareto_cutoff_checkbox.setAccessibleDescription("在品質異常 Pareto 分析圖表 80% 處繪製輔助警戒虛線。")
        stats_layout.addWidget(self._pareto_cutoff_checkbox)

        table_root.addWidget(table_density_group)
        table_root.addWidget(visual_helper_group)
        table_root.addWidget(interaction_group)
        table_root.addWidget(stats_group)
        table_root.addStretch(1)
        self.preference_tabs.addTab(table_page, "視覺表格")

        # ── Tab 3: 表單業務預設 (Form & Business Defaults) ──
        form_page = QWidget()
        form_root = QVBoxLayout(form_page)
        form_root.setContentsMargins(0, 0, 0, 0)
        form_root.setSpacing(ROW_GAP)

        anomaly_default_group = QGroupBox("異常事件表單預設")
        anomaly_default_layout = QVBoxLayout(anomaly_default_group)
        anomaly_default_layout.setSpacing(ROW_GAP)

        anomaly_default_layout.addWidget(QLabel("預設責任人員 / SQE 填報人"))
        self._responsible_person_input = QLineEdit()
        self._responsible_person_input.setPlaceholderText("例如：王大明 / SQE001（留空則不自動帶入）")
        self._responsible_person_input.setAccessibleName("預設責任人員")
        self._responsible_person_input.setToolTip("新建異常事件時自動填入責任人員欄位。")
        anomaly_default_layout.addWidget(self._responsible_person_input)

        anomaly_default_layout.addWidget(QLabel("預設異常類別"))
        self._anomaly_category_combo = QComboBox()
        self._anomaly_category_combo.addItems(ANOMALY_CATEGORY_OPTIONS)
        self._anomaly_category_combo.setAccessibleName("預設異常類別")
        self._anomaly_category_combo.setToolTip("新建異常事件時預設選取的異常類別。")
        anomaly_default_layout.addWidget(self._anomaly_category_combo)

        self._sync_visit_checkbox = QCheckBox("新建異常時預設勾選「同步建立訪廠紀錄」")
        self._sync_visit_checkbox.setAccessibleName("新建異常預設同步建立訪廠紀錄")
        self._sync_visit_checkbox.setToolTip("開啟新增異常表單時，預設自動勾選同步產生同日訪廠紀錄。")
        self._sync_visit_checkbox.setAccessibleDescription("開啟新增異常表單時，預設自動勾選同步產生同日訪廠紀錄。")
        anomaly_default_layout.addWidget(self._sync_visit_checkbox)

        anomaly_default_layout.addWidget(QLabel("改善回覆預設期限天數"))
        self._due_days_group = QButtonGroup(self)
        self._due_days_buttons = {}
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
            anomaly_default_layout.addWidget(radio)

        visit_default_group = QGroupBox("訪廠紀錄表單預設")
        visit_default_layout = QVBoxLayout(visit_default_group)
        visit_default_layout.setSpacing(ROW_GAP)

        visit_default_layout.addWidget(QLabel("預設訪廠時段"))
        self._visit_time_slot_group = QButtonGroup(self)
        self._visit_time_slot_buttons = {}
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
            visit_default_layout.addWidget(radio)

        form_root.addWidget(anomaly_default_group)
        form_root.addWidget(visit_default_group)
        form_root.addStretch(1)
        self.preference_tabs.addTab(form_page, "表單業務預設")

        # ── Tab 4: 匯出與報告 (Export & Reports) ──
        export_page = QWidget()
        export_root = QVBoxLayout(export_page)
        export_root.setContentsMargins(0, 0, 0, 0)
        export_root.setSpacing(ROW_GAP)

        export_path_group = QGroupBox("匯出路徑與行為")
        export_path_layout = QVBoxLayout(export_path_group)
        export_path_layout.setSpacing(ROW_GAP)

        export_path_layout.addWidget(QLabel("預設匯出目錄 (Default Export Directory)"))
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

        report_style_group = QGroupBox("報告格式與內容設定")
        report_style_layout = QVBoxLayout(report_style_group)
        report_style_layout.setSpacing(ROW_GAP)

        report_style_layout.addWidget(QLabel("報告單位抬頭名稱 (Organization Header)"))
        self._report_header_input = QLineEdit()
        self._report_header_input.setPlaceholderText("例如：SQE 供應商品質工程部")
        self._report_header_input.setAccessibleName("報告單位抬頭名稱")
        self._report_header_input.setToolTip("用於 PDF 與 Excel 匯出報表首頁與頁首的公司/部門名稱。")
        report_style_layout.addWidget(self._report_header_input)

        self._export_charts_checkbox = QCheckBox("Excel 匯出預設包含 Pareto 統計圖表 (Include Charts in Excel)")
        self._export_charts_checkbox.setAccessibleName("Excel 匯出包含統計圖表")
        self._export_charts_checkbox.setToolTip("在品質統計匯出 Excel 報表時自動嵌入 Pareto 分析圖表與圖片。")
        self._export_charts_checkbox.setAccessibleDescription("在品質統計匯出 Excel 報表時自動嵌入 Pareto 分析圖表與圖片。")
        report_style_layout.addWidget(self._export_charts_checkbox)

        export_root.addWidget(export_path_group)
        export_root.addWidget(report_style_group)
        export_root.addStretch(1)
        self.preference_tabs.addTab(export_page, "匯出與報告")

        # ── Tab 5: 系統與備份 (System & Backup) ──
        system_page = QWidget()
        system_root = QVBoxLayout(system_page)
        system_root.setContentsMargins(0, 0, 0, 0)
        system_root.setSpacing(ROW_GAP)

        startup_group = QGroupBox("啟動與操作防護")
        startup_layout = QVBoxLayout(startup_group)
        startup_layout.setSpacing(ROW_GAP)

        startup_layout.addWidget(QLabel("預設啟動頁面 (Default Startup Page)"))
        self._startup_page_group = QButtonGroup(self)
        self._startup_page_buttons = {}
        for value, label, description in (
            ("home", "首頁儀表板", "開啟應用程式時預設顯示首頁與待辦面板。"),
            ("events", "訪廠與異常事件", "開啟應用程式時預設進入供應商訪廠與品質異常清單。"),
            ("defects", "倉庫不良品紀錄", "開啟應用程式時預設進入實體不良品倉庫清單。"),
            ("stats", "品質統計分析", "開啟應用程式時預設進入品質 Pareto 與統計圖表。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"預設啟動頁面：{label}")
            radio.setToolTip(description)
            radio.setAccessibleDescription(description)
            radio.toggled.connect(self._preview_from_controls)
            self._startup_page_group.addButton(radio)
            self._startup_page_buttons[value] = radio
            startup_layout.addWidget(radio)

        self._confirm_delete_checkbox = QCheckBox("執行資料刪除操作時強制二次確認 (Confirm on Delete)")
        self._confirm_delete_checkbox.setAccessibleName("資料刪除二次確認")
        self._confirm_delete_checkbox.setToolTip("刪除異常單、訪廠或不良品紀錄時跳出確認視窗。")
        self._confirm_delete_checkbox.setAccessibleDescription("刪除異常單、訪廠或不良品紀錄時跳出確認視窗。")
        startup_layout.addWidget(self._confirm_delete_checkbox)

        backup_group = QGroupBox("資料庫自動備份與保留")
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.setSpacing(ROW_GAP)

        self._auto_backup_checkbox = QCheckBox("關閉程式時顯示資料自動備份提醒 (Auto Backup Prompt)")
        self._auto_backup_checkbox.setAccessibleName("關閉程式時顯示資料自動備份提醒")
        self._auto_backup_checkbox.setToolTip("結束工作區時自動檢查並提示建立 SQLite 備份。")
        self._auto_backup_checkbox.setAccessibleDescription("結束工作區時自動檢查並提示建立 SQLite 備份。")
        self._auto_backup_checkbox.toggled.connect(self._preview_from_controls)
        backup_layout.addWidget(self._auto_backup_checkbox)

        backup_layout.addWidget(QLabel("自動備份保留份數上限 (Backup Retention Count)"))
        self._retention_count_group = QButtonGroup(self)
        self._retention_count_buttons = {}
        for value, label, description in (
            (5, "5 份", "保留最近 5 份備份檔案。"),
            (10, "10 份 (預設)", "保留最近 10 份備份檔案。"),
            (20, "20 份", "保留最近 20 份備份檔案。"),
            (30, "30 份", "保留最近 30 份備份檔案。"),
        ):
            radio = QRadioButton(label)
            radio.setAccessibleName(f"備份保留份數：{label}")
            radio.setToolTip(description)
            self._retention_count_group.addButton(radio)
            self._retention_count_buttons[value] = radio
            backup_layout.addWidget(radio)

        system_root.addWidget(startup_group)
        system_root.addWidget(backup_group)
        system_root.addStretch(1)
        self.preference_tabs.addTab(system_page, "系統與備份")

        # ── Footer ──
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
        density = next(val for val, btn in self._density_buttons.items() if btn.isChecked())
        sidebar_density = next(val for val, btn in self._sidebar_density_buttons.items() if btn.isChecked())
        table_density = next(val for val, btn in self._table_density_buttons.items() if btn.isChecked())
        accent_color = next(val for val, btn in self._accent_color_buttons.items() if btn.isChecked())
        text_scale = next(val for val, btn in self._text_scale_buttons.items() if btn.isChecked())
        contrast_mode = next(val for val, btn in self._contrast_mode_buttons.items() if btn.isChecked())
        startup_page = next(val for val, btn in self._startup_page_buttons.items() if btn.isChecked())
        page_limit = next(val for val, btn in self._page_limit_buttons.items() if btn.isChecked())

        due_days = next(val for val, btn in self._due_days_buttons.items() if btn.isChecked())
        visit_time_slot = next(val for val, btn in self._visit_time_slot_buttons.items() if btn.isChecked())
        export_action = next(val for val, btn in self._export_action_buttons.items() if btn.isChecked())
        retention_count = next(val for val, btn in self._retention_count_buttons.items() if btn.isChecked())

        double_click_action = next(val for val, btn in self._double_click_buttons.items() if btn.isChecked())
        search_mode = next(val for val, btn in self._search_mode_buttons.items() if btn.isChecked())
        stats_span = next(val for val, btn in self._stats_span_buttons.items() if btn.isChecked())

        return AppearancePreferences(
            density=density,
            sidebar_density=sidebar_density,
            accent_color=accent_color,
            text_scale=text_scale,
            contrast_mode=contrast_mode,
            table_density=table_density,
            alternating_row_colors=self._alt_row_checkbox.isChecked(),
            table_grid_lines=self._grid_lines_checkbox.isChecked(),
            table_page_limit=page_limit,
            enable_animations=self._animations_checkbox.isChecked(),
            table_double_click_action=double_click_action,
            search_mode=search_mode,
            stats_default_span_months=stats_span,
            pareto_show_cutoff_line=self._pareto_cutoff_checkbox.isChecked(),
            default_responsible_person=self._responsible_person_input.text().strip(),
            default_anomaly_category=self._anomaly_category_combo.currentText().strip(),
            default_sync_visit=self._sync_visit_checkbox.isChecked(),
            default_due_days=due_days,
            default_visit_time_slot=visit_time_slot,
            default_export_dir=self._export_dir_input.text().strip(),
            export_completion_action=export_action,
            report_organization_header=self._report_header_input.text().strip() or "SQE 供應商品質工程部",
            export_include_charts=self._export_charts_checkbox.isChecked(),
            default_startup_page=startup_page,
            auto_backup_prompt=self._auto_backup_checkbox.isChecked(),
            backup_retention_count=retention_count,
            confirm_on_delete=self._confirm_delete_checkbox.isChecked(),
        )

    def _set_preferences(self, preferences: AppearancePreferences, *, preview: bool) -> None:
        blockers = [
            *[QSignalBlocker(btn) for btn in self._density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._sidebar_density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._table_density_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._accent_color_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._text_scale_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._contrast_mode_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._startup_page_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._page_limit_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._due_days_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._visit_time_slot_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._export_action_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._retention_count_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._double_click_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._search_mode_buttons.values()],
            *[QSignalBlocker(btn) for btn in self._stats_span_buttons.values()],
            QSignalBlocker(self._alt_row_checkbox),
            QSignalBlocker(self._grid_lines_checkbox),
            QSignalBlocker(self._animations_checkbox),
            QSignalBlocker(self._auto_backup_checkbox),
            QSignalBlocker(self._sync_visit_checkbox),
            QSignalBlocker(self._export_charts_checkbox),
            QSignalBlocker(self._confirm_delete_checkbox),
            QSignalBlocker(self._pareto_cutoff_checkbox),
            QSignalBlocker(self._responsible_person_input),
            QSignalBlocker(self._anomaly_category_combo),
            QSignalBlocker(self._export_dir_input),
            QSignalBlocker(self._report_header_input),
        ]
        self._density_buttons[preferences.density].setChecked(True)
        self._sidebar_density_buttons[preferences.sidebar_density].setChecked(True)
        self._table_density_buttons[preferences.table_density].setChecked(True)
        self._accent_color_buttons[preferences.accent_color].setChecked(True)
        self._text_scale_buttons[preferences.text_scale].setChecked(True)
        self._contrast_mode_buttons[preferences.contrast_mode].setChecked(True)
        self._startup_page_buttons[preferences.default_startup_page].setChecked(True)
        self._page_limit_buttons[preferences.table_page_limit].setChecked(True)
        self._alt_row_checkbox.setChecked(preferences.alternating_row_colors)
        self._grid_lines_checkbox.setChecked(preferences.table_grid_lines)
        self._animations_checkbox.setChecked(preferences.enable_animations)
        self._auto_backup_checkbox.setChecked(preferences.auto_backup_prompt)

        if preferences.table_double_click_action in self._double_click_buttons:
            self._double_click_buttons[preferences.table_double_click_action].setChecked(True)
        if preferences.search_mode in self._search_mode_buttons:
            self._search_mode_buttons[preferences.search_mode].setChecked(True)
        if preferences.stats_default_span_months in self._stats_span_buttons:
            self._stats_span_buttons[preferences.stats_default_span_months].setChecked(True)
        self._pareto_cutoff_checkbox.setChecked(preferences.pareto_show_cutoff_line)

        self._responsible_person_input.setText(preferences.default_responsible_person)
        cat_idx = self._anomaly_category_combo.findText(preferences.default_anomaly_category)
        if cat_idx >= 0:
            self._anomaly_category_combo.setCurrentIndex(cat_idx)
        self._sync_visit_checkbox.setChecked(preferences.default_sync_visit)
        if preferences.default_due_days in self._due_days_buttons:
            self._due_days_buttons[preferences.default_due_days].setChecked(True)
        if preferences.default_visit_time_slot in self._visit_time_slot_buttons:
            self._visit_time_slot_buttons[preferences.default_visit_time_slot].setChecked(True)

        self._export_dir_input.setText(preferences.default_export_dir)
        if preferences.export_completion_action in self._export_action_buttons:
            self._export_action_buttons[preferences.export_completion_action].setChecked(True)
        self._report_header_input.setText(preferences.report_organization_header)
        self._export_charts_checkbox.setChecked(preferences.export_include_charts)

        if preferences.backup_retention_count in self._retention_count_buttons:
            self._retention_count_buttons[preferences.backup_retention_count].setChecked(True)
        self._confirm_delete_checkbox.setChecked(preferences.confirm_on_delete)

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

