"""Commercial-style, reversible display preference and system defaults dialog."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
from ui.appearance_preferences import AppearancePreferences
from ui.layout_constants import FORM_MAX_WIDTH, PANEL_MARGINS, ROW_GAP
from ui.theme import apply_app_theme
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import apply_clickable_affordance


class AppearancePreferencesDialog(QDialog):
    """Preview, save, or discard global display-only & system default preferences."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppearancePreferencesDialog")
        self.setWindowTitle("顯示設定")
        self.setModal(True)
        self._initial_preferences = load_application_preferences()
        self._build_ui()
        self._set_preferences(self._initial_preferences, preview=False)
        fit_dialog_to_available_screen(
            self,
            preferred_width=760,
            preferred_height=740,
            maximum_width=FORM_MAX_WIDTH,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PANEL_MARGINS)
        root.setSpacing(ROW_GAP)

        title = QLabel("顯示設定")
        title.setProperty("role", "sectionTitle")
        title.setToolTip("調整本機顯示與系統預設偏好；不影響既有品質資料與資料庫架構。")
        title.setAccessibleDescription("調整本機顯示與系統預設偏好；不影響既有品質資料與資料庫架構。")
        root.addWidget(title)

        self.preference_tabs = QTabWidget()
        self.preference_tabs.setObjectName("AppearancePreferenceTabs")
        self.preference_tabs.setDocumentMode(True)
        root.addWidget(self.preference_tabs, 1)

        # Tab 1: 外觀與密度
        layout_page = QWidget()
        layout_root = QVBoxLayout(layout_page)
        layout_root.setContentsMargins(0, 0, 0, 0)
        layout_root.setSpacing(ROW_GAP)

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

        density_layout.addWidget(QLabel("資料表閱讀密度"))
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
            density_layout.addWidget(radio)

        layout_root.addWidget(density_group)
        layout_root.addStretch(1)
        self.preference_tabs.addTab(layout_page, "外觀與密度")

        # Tab 2: 視覺與色彩
        visual_page = QWidget()
        visual_root = QVBoxLayout(visual_page)
        visual_root.setContentsMargins(0, 0, 0, 0)
        visual_root.setSpacing(ROW_GAP)

        color_group = QGroupBox("主題與對比")
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

        visual_helper_group = QGroupBox("資料表與視覺效果輔助")
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

        visual_root.addWidget(color_group)
        visual_root.addWidget(visual_helper_group)
        visual_root.addStretch(1)
        self.preference_tabs.addTab(visual_page, "視覺與色彩")

        # Tab 3: 系統與預設
        system_page = QWidget()
        system_root = QVBoxLayout(system_page)
        system_root.setContentsMargins(0, 0, 0, 0)
        system_root.setSpacing(ROW_GAP)

        startup_group = QGroupBox("啟動與分頁預設")
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

        startup_layout.addWidget(QLabel("資料表預設單頁筆數 (Table Page Limit)"))
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
            startup_layout.addWidget(radio)

        backup_group = QGroupBox("系統提示與自動化預設")
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.setSpacing(ROW_GAP)

        self._auto_backup_checkbox = QCheckBox("關閉程式時顯示資料自動備份提醒 (Auto Backup Prompt)")
        self._auto_backup_checkbox.setAccessibleName("關閉程式時顯示資料自動備份提醒")
        self._auto_backup_checkbox.setToolTip("結束工作區時自動檢查並提示建立 SQLite 備份。")
        self._auto_backup_checkbox.setAccessibleDescription("結束工作區時自動檢查並提示建立 SQLite 備份。")
        self._auto_backup_checkbox.toggled.connect(self._preview_from_controls)
        backup_layout.addWidget(self._auto_backup_checkbox)

        system_root.addWidget(startup_group)
        system_root.addWidget(backup_group)
        system_root.addStretch(1)
        self.preference_tabs.addTab(system_page, "系統與預設")

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

        self.setTabOrder(self._density_buttons["compact"], self._density_buttons["standard"])
        self.setTabOrder(self._density_buttons["standard"], self._density_buttons["comfortable"])
        self.setTabOrder(self._density_buttons["comfortable"], self.reset_button)
        self.setTabOrder(self.reset_button, self.save_button)
        self.setTabOrder(self.save_button, self.cancel_button)

    def _current_preferences(self) -> AppearancePreferences:
        density = next(val for val, btn in self._density_buttons.items() if btn.isChecked())
        sidebar_density = next(val for val, btn in self._sidebar_density_buttons.items() if btn.isChecked())
        table_density = next(val for val, btn in self._table_density_buttons.items() if btn.isChecked())
        accent_color = next(val for val, btn in self._accent_color_buttons.items() if btn.isChecked())
        text_scale = next(val for val, btn in self._text_scale_buttons.items() if btn.isChecked())
        contrast_mode = next(val for val, btn in self._contrast_mode_buttons.items() if btn.isChecked())
        startup_page = next(val for val, btn in self._startup_page_buttons.items() if btn.isChecked())
        page_limit = next(val for val, btn in self._page_limit_buttons.items() if btn.isChecked())
        return AppearancePreferences(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            alternating_row_colors=self._alt_row_checkbox.isChecked(),
            table_grid_lines=self._grid_lines_checkbox.isChecked(),
            enable_animations=self._animations_checkbox.isChecked(),
            default_startup_page=startup_page,
            table_page_limit=page_limit,
            auto_backup_prompt=self._auto_backup_checkbox.isChecked(),
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
            QSignalBlocker(self._alt_row_checkbox),
            QSignalBlocker(self._grid_lines_checkbox),
            QSignalBlocker(self._animations_checkbox),
            QSignalBlocker(self._auto_backup_checkbox),
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

