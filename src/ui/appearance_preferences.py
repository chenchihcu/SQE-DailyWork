"""Typed, display-only preferences for the SQE desktop shell.

This module deliberately contains no database access.  It is shared by the
settings service, theme application and dialog so every boundary validates the
same small, versioned contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


Density = Literal["compact", "standard", "comfortable"]
TextScale = Literal["standard", "large"]
SidebarDensity = Literal["compact", "standard"]
SidebarIconMode = Literal["both", "text_only", "compact_icon"]
TableDensity = Literal["compact", "standard", "comfortable"]
ContrastMode = Literal["standard", "high"]
AccentColor = Literal["electric_blue", "slate_navy", "emerald", "amber", "violet", "rose"]
ThemeMode = Literal["light", "dark_slate", "system"]
CjkFontPreference = Literal["default", "noto_sans", "system"]
WindowGeometryMode = Literal["remember", "standard", "maximized"]
StatusBarDetailLevel = Literal["standard", "compact", "detailed"]

StartupPage = Literal["home", "events", "defects", "stats"]
TablePageLimit = Literal[25, 50, 100, 0]
DateFormatDisplay = Literal["YYYY-MM-DD", "YYYY/MM/DD"]
ExportCompletionAction = Literal["open_file", "open_folder", "notify_only"]
ExportNamingRule = Literal["standard", "detailed", "compact"]
PdfPageOrientation = Literal["portrait", "landscape"]
ExcelThemeStyle = Literal["classic_navy", "slate_gray", "forest_green"]
PdfFontDensity = Literal["standard", "compact"]

TableDoubleClickAction = Literal["menu", "preview", "edit"]
SearchMode = Literal["live", "manual"]
StatsDefaultSpanMonths = Literal[3, 6, 12]
OverdueReminderDays = Literal[0, 3, 7, 14]
TableTextWrapping = Literal["elide", "wrap"]
DefaultListSortField = Literal["anomaly_no_desc", "date_desc", "status_first"]
DefaultDefectDisposition = Literal["", "特採", "退貨", "重工", "報廢", "待判定"]

LogLevel = Literal["INFO", "DEBUG", "WARNING"]
ImportConflictStrategy = Literal["prompt", "skip", "overwrite"]

DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard", "comfortable"})
TEXT_SCALE_VALUES: Final[frozenset[str]] = frozenset({"standard", "large"})
SIDEBAR_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard"})
SIDEBAR_ICON_MODE_VALUES: Final[frozenset[str]] = frozenset({"both", "text_only", "compact_icon"})
TABLE_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard", "comfortable"})
CONTRAST_MODE_VALUES: Final[frozenset[str]] = frozenset({"standard", "high"})
ACCENT_COLOR_VALUES: Final[frozenset[str]] = frozenset(
    {"electric_blue", "slate_navy", "emerald", "amber", "violet", "rose"}
)
THEME_MODE_VALUES: Final[frozenset[str]] = frozenset({"light", "dark_slate", "system"})
CJK_FONT_PREFERENCE_VALUES: Final[frozenset[str]] = frozenset({"default", "noto_sans", "system"})
WINDOW_GEOMETRY_MODE_VALUES: Final[frozenset[str]] = frozenset({"remember", "standard", "maximized"})
STATUS_BAR_DETAIL_LEVEL_VALUES: Final[frozenset[str]] = frozenset({"standard", "compact", "detailed"})

STARTUP_PAGE_VALUES: Final[frozenset[str]] = frozenset({"home", "events", "defects", "stats"})
TABLE_PAGE_LIMIT_VALUES: Final[frozenset[int]] = frozenset({25, 50, 100, 0})
DATE_FORMAT_DISPLAY_VALUES: Final[frozenset[str]] = frozenset({"YYYY-MM-DD", "YYYY/MM/DD"})
DEFAULT_DUE_DAYS_VALUES: Final[frozenset[int]] = frozenset({7, 14, 30})
DEFAULT_DEFECT_SAMPLE_SIZE_VALUES: Final[frozenset[int]] = frozenset({0, 50, 100, 200})
DEFAULT_VISIT_TIME_SLOT_VALUES: Final[frozenset[str]] = frozenset({"上午", "下午", "全天"})
DEFAULT_SEVERITY_LEVEL_VALUES: Final[frozenset[str]] = frozenset({"一般", "重大", "極嚴重"})
DEFAULT_VISIT_TYPE_VALUES: Final[frozenset[str]] = frozenset(
    {"例行訪廠", "品質輔導", "年度稽核", "新產品導入輔導"}
)
DEFAULT_DEFECT_DISPOSITION_VALUES: Final[frozenset[str]] = frozenset(
    {"", "特採", "退貨", "重工", "報廢", "待判定"}
)

EXPORT_COMPLETION_ACTION_VALUES: Final[frozenset[str]] = frozenset({"open_file", "open_folder", "notify_only"})
EXPORT_NAMING_RULE_VALUES: Final[frozenset[str]] = frozenset({"standard", "detailed", "compact"})
PDF_PAGE_ORIENTATION_VALUES: Final[frozenset[str]] = frozenset({"portrait", "landscape"})
EXCEL_THEME_STYLE_VALUES: Final[frozenset[str]] = frozenset({"classic_navy", "slate_gray", "forest_green"})
PDF_FONT_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"standard", "compact"})

BACKUP_RETENTION_COUNT_VALUES: Final[frozenset[int]] = frozenset({5, 10, 20, 30})
TABLE_DOUBLE_CLICK_ACTION_VALUES: Final[frozenset[str]] = frozenset({"menu", "preview", "edit"})
SEARCH_MODE_VALUES: Final[frozenset[str]] = frozenset({"live", "manual"})
STATS_DEFAULT_SPAN_MONTHS_VALUES: Final[frozenset[int]] = frozenset({3, 6, 12})
OVERDUE_REMINDER_DAYS_VALUES: Final[frozenset[int]] = frozenset({0, 3, 7, 14})
TABLE_TEXT_WRAPPING_VALUES: Final[frozenset[str]] = frozenset({"elide", "wrap"})
DEFAULT_LIST_SORT_FIELD_VALUES: Final[frozenset[str]] = frozenset(
    {"anomaly_no_desc", "date_desc", "status_first"}
)

LOG_LEVEL_VALUES: Final[frozenset[str]] = frozenset({"INFO", "DEBUG", "WARNING"})
IMPORT_CONFLICT_STRATEGY_VALUES: Final[frozenset[str]] = frozenset({"prompt", "skip", "overwrite"})

V8_FIELDS: Final[frozenset[str]] = frozenset(
    {
        # Tab 1: 外觀與風格 (Appearance & Styling)
        "density",
        "sidebar_density",
        "sidebar_icon_mode",
        "accent_color",
        "text_scale",
        "contrast_mode",
        "theme_mode",
        "cjk_font_family_preference",
        "window_geometry_mode",
        "status_bar_detail_level",
        # Tab 2: 表格與檢視 (Tables & Interaction)
        "table_density",
        "alternating_row_colors",
        "table_grid_lines",
        "table_page_limit",
        "enable_animations",
        "table_double_click_action",
        "search_mode",
        "stats_default_span_months",
        "pareto_show_cutoff_line",
        "highlight_overdue_rows",
        "date_format_display",
        "table_auto_scroll_to_top",
        "table_hover_highlight",
        "table_text_wrapping",
        "default_list_sort_field",
        "table_show_row_numbers",
        "quick_filter_case_sensitive",
        # Tab 3: 表單與業務 (Form & Business Defaults)
        "default_responsible_person",
        "default_anomaly_category",
        "default_sync_visit",
        "default_due_days",
        "default_visit_time_slot",
        "default_anomaly_source",
        "default_severity_level",
        "default_visit_type",
        "auto_fill_anomaly_no_on_date_change",
        "default_closer_name",
        "default_defect_disposition",
        "auto_uppercase_part_no",
        "default_defect_sample_size",
        "require_defect_photos",
        # Tab 4: 匯出與報表 (Export & Reports)
        "default_export_dir",
        "export_completion_action",
        "report_organization_header",
        "export_include_charts",
        "export_file_naming_rule",
        "pdf_page_orientation",
        "pdf_watermark_text",
        "excel_autofit_columns",
        "excel_theme_style",
        "pdf_font_density",
        "export_include_disclaimer",
        "export_include_summary_sheet",
        "pdf_header_logo_visible",
        # Tab 5: 系統與維護 (System, Logs & Maintenance)
        "default_startup_page",
        "auto_backup_prompt",
        "backup_retention_count",
        "confirm_on_delete",
        "overdue_reminder_days",
        "auto_check_unresolved_on_startup",
        "clean_temp_files_on_exit",
        "log_level",
        "auto_save_drafts",
        "import_conflict_strategy",
        "session_restore_last_filters",
        "auto_compact_db_on_exit",
    }
)

V7_FIELDS: Final[frozenset[str]] = frozenset(
    {
        # Tab 1: 外觀與風格 (Appearance & Styling)
        "density",
        "sidebar_density",
        "accent_color",
        "text_scale",
        "contrast_mode",
        "theme_mode",
        "cjk_font_family_preference",
        "window_geometry_mode",
        "status_bar_detail_level",
        # Tab 2: 表格與檢視 (Tables & Interaction)
        "table_density",
        "alternating_row_colors",
        "table_grid_lines",
        "table_page_limit",
        "enable_animations",
        "table_double_click_action",
        "search_mode",
        "stats_default_span_months",
        "pareto_show_cutoff_line",
        "highlight_overdue_rows",
        "date_format_display",
        "table_auto_scroll_to_top",
        "table_hover_highlight",
        "table_text_wrapping",
        "default_list_sort_field",
        # Tab 3: 表單與業務 (Form & Business Defaults)
        "default_responsible_person",
        "default_anomaly_category",
        "default_sync_visit",
        "default_due_days",
        "default_visit_time_slot",
        "default_anomaly_source",
        "default_severity_level",
        "default_visit_type",
        "auto_fill_anomaly_no_on_date_change",
        "default_closer_name",
        "default_defect_disposition",
        "auto_uppercase_part_no",
        # Tab 4: 匯出與報表 (Export & Reports)
        "default_export_dir",
        "export_completion_action",
        "report_organization_header",
        "export_include_charts",
        "export_file_naming_rule",
        "pdf_page_orientation",
        "pdf_watermark_text",
        "excel_autofit_columns",
        "excel_theme_style",
        "pdf_font_density",
        "export_include_disclaimer",
        # Tab 5: 系統與維護 (System, Logs & Maintenance)
        "default_startup_page",
        "auto_backup_prompt",
        "backup_retention_count",
        "confirm_on_delete",
        "overdue_reminder_days",
        "auto_check_unresolved_on_startup",
        "clean_temp_files_on_exit",
        "log_level",
        "auto_save_drafts",
        "import_conflict_strategy",
    }
)

V6_FIELDS: Final[frozenset[str]] = frozenset(
    {
        # Tab 1: 外觀主題
        "density",
        "sidebar_density",
        "accent_color",
        "text_scale",
        "contrast_mode",
        "theme_mode",
        "cjk_font_family_preference",
        # Tab 2: 視覺表格與互動
        "table_density",
        "alternating_row_colors",
        "table_grid_lines",
        "table_page_limit",
        "enable_animations",
        "table_double_click_action",
        "search_mode",
        "stats_default_span_months",
        "pareto_show_cutoff_line",
        "highlight_overdue_rows",
        "date_format_display",
        "table_auto_scroll_to_top",
        # Tab 3: 表單業務預設
        "default_responsible_person",
        "default_anomaly_category",
        "default_sync_visit",
        "default_due_days",
        "default_visit_time_slot",
        "default_anomaly_source",
        "default_severity_level",
        "default_visit_type",
        "auto_fill_anomaly_no_on_date_change",
        # Tab 4: 匯出與報告
        "default_export_dir",
        "export_completion_action",
        "report_organization_header",
        "export_include_charts",
        "export_file_naming_rule",
        "pdf_page_orientation",
        "pdf_watermark_text",
        "excel_autofit_columns",
        # Tab 5: 系統、通知與備份
        "default_startup_page",
        "auto_backup_prompt",
        "backup_retention_count",
        "confirm_on_delete",
        "overdue_reminder_days",
        "auto_check_unresolved_on_startup",
        "clean_temp_files_on_exit",
    }
)

V5_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "density",
        "text_scale",
        "sidebar_density",
        "table_density",
        "contrast_mode",
        "accent_color",
        "alternating_row_colors",
        "table_grid_lines",
        "enable_animations",
        "default_startup_page",
        "table_page_limit",
        "auto_backup_prompt",
        "default_responsible_person",
        "default_anomaly_category",
        "default_sync_visit",
        "default_due_days",
        "default_visit_time_slot",
        "default_export_dir",
        "export_completion_action",
        "report_organization_header",
        "export_include_charts",
        "backup_retention_count",
        "confirm_on_delete",
        "table_double_click_action",
        "search_mode",
        "stats_default_span_months",
        "pareto_show_cutoff_line",
    }
)
V4_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "density",
        "text_scale",
        "sidebar_density",
        "table_density",
        "contrast_mode",
        "accent_color",
        "alternating_row_colors",
        "table_grid_lines",
        "enable_animations",
        "default_startup_page",
        "table_page_limit",
        "auto_backup_prompt",
        "default_responsible_person",
        "default_anomaly_category",
        "default_sync_visit",
        "default_due_days",
        "default_visit_time_slot",
        "default_export_dir",
        "export_completion_action",
        "report_organization_header",
        "export_include_charts",
        "backup_retention_count",
        "confirm_on_delete",
    }
)
V3_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "density",
        "text_scale",
        "sidebar_density",
        "table_density",
        "contrast_mode",
        "accent_color",
        "alternating_row_colors",
        "table_grid_lines",
        "enable_animations",
        "default_startup_page",
        "table_page_limit",
        "auto_backup_prompt",
    }
)
V2_FIELDS: Final[frozenset[str]] = frozenset(
    {"density", "text_scale", "sidebar_density", "table_density", "contrast_mode"}
)
V1_FIELDS: Final[frozenset[str]] = frozenset({"density", "text_scale"})


@dataclass(frozen=True)
class AppearancePreferences:
    """The complete v8 application-appearance, business and system defaults contract.

    The settings affect presentation, defaults, and user system workflows. No core
    record structures or statistics calculations are altered.
    """

    # Tab 1: 外觀與風格 (Appearance & Styling)
    density: Density = "standard"
    sidebar_density: SidebarDensity = "standard"
    sidebar_icon_mode: SidebarIconMode = "both"
    accent_color: AccentColor = "electric_blue"
    text_scale: TextScale = "standard"
    contrast_mode: ContrastMode = "standard"
    theme_mode: ThemeMode = "light"
    cjk_font_family_preference: CjkFontPreference = "default"
    window_geometry_mode: WindowGeometryMode = "remember"
    status_bar_detail_level: StatusBarDetailLevel = "standard"

    # Tab 2: 表格與檢視 (Tables & Interaction)
    table_density: TableDensity = "standard"
    alternating_row_colors: bool = True
    table_grid_lines: bool = True
    table_page_limit: int = 50
    enable_animations: bool = True
    table_double_click_action: TableDoubleClickAction = "menu"
    search_mode: SearchMode = "live"
    stats_default_span_months: int = 6
    pareto_show_cutoff_line: bool = True
    highlight_overdue_rows: bool = True
    date_format_display: DateFormatDisplay = "YYYY-MM-DD"
    table_auto_scroll_to_top: bool = True
    table_hover_highlight: bool = True
    table_text_wrapping: TableTextWrapping = "elide"
    default_list_sort_field: DefaultListSortField = "anomaly_no_desc"
    table_show_row_numbers: bool = False
    quick_filter_case_sensitive: bool = False

    # Tab 3: 表單與業務 (Form & Business Defaults)
    default_responsible_person: str = ""
    default_anomaly_category: str = ""
    default_sync_visit: bool = True
    default_due_days: int = 7
    default_visit_time_slot: str = "下午"
    default_anomaly_source: str = ""
    default_severity_level: str = "一般"
    default_visit_type: str = "例行訪廠"
    auto_fill_anomaly_no_on_date_change: bool = True
    default_closer_name: str = ""
    default_defect_disposition: str = ""
    auto_uppercase_part_no: bool = True
    default_defect_sample_size: int = 0
    require_defect_photos: bool = False

    # Tab 4: 匯出與報表 (Export & Reports)
    default_export_dir: str = ""
    export_completion_action: ExportCompletionAction = "open_file"
    report_organization_header: str = "SQE 供應商品質工程部"
    export_include_charts: bool = True
    export_file_naming_rule: ExportNamingRule = "standard"
    pdf_page_orientation: PdfPageOrientation = "portrait"
    pdf_watermark_text: str = ""
    excel_autofit_columns: bool = True
    excel_theme_style: ExcelThemeStyle = "classic_navy"
    pdf_font_density: PdfFontDensity = "standard"
    export_include_disclaimer: bool = True
    export_include_summary_sheet: bool = True
    pdf_header_logo_visible: bool = True

    # Tab 5: 系統與維護 (System, Logs & Maintenance)
    default_startup_page: StartupPage = "home"
    auto_backup_prompt: bool = True
    backup_retention_count: int = 10
    confirm_on_delete: bool = True
    overdue_reminder_days: int = 7
    auto_check_unresolved_on_startup: bool = True
    clean_temp_files_on_exit: bool = True
    log_level: LogLevel = "INFO"
    auto_save_drafts: bool = True
    import_conflict_strategy: ImportConflictStrategy = "prompt"
    session_restore_last_filters: bool = True
    auto_compact_db_on_exit: bool = False

    @classmethod
    def default(cls) -> "AppearancePreferences":
        return cls()

    @classmethod
    def from_mapping(cls, value: object) -> "AppearancePreferences":
        """Return validated v8 profile, with graceful in-memory upgrades from v7/v6/v5/v4/v3/v2/v1."""
        if not isinstance(value, dict):
            return cls.default()

        if set(value) == V8_FIELDS:
            return cls._from_v8_mapping(value)
        elif set(value) == V7_FIELDS:
            return cls._from_v7_mapping(value)
        elif set(value) == V6_FIELDS:
            return cls._from_v6_mapping(value)
        elif set(value) == V5_FIELDS:
            return cls._from_v5_mapping(value)
        elif set(value) == V4_FIELDS:
            return cls._from_v4_mapping(value)
        elif set(value) == V3_FIELDS:
            return cls._from_v3_mapping(value)
        elif set(value) == V2_FIELDS:
            return cls.from_v2_mapping(value)
        elif set(value) == V1_FIELDS:
            return cls.from_v1_mapping(value)

        return cls.default()

    @classmethod
    def _from_v8_mapping(cls, value: dict) -> "AppearancePreferences":
        # Tab 1: 外觀與風格
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        sidebar_icon_mode = value.get("sidebar_icon_mode", "both")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        accent_color = value.get("accent_color")
        theme_mode = value.get("theme_mode", "light")
        cjk_font_family_preference = value.get("cjk_font_family_preference", "default")
        window_geometry_mode = value.get("window_geometry_mode", "remember")
        status_bar_detail_level = value.get("status_bar_detail_level", "standard")

        # Tab 2: 表格與檢視
        alternating_row_colors = value.get("alternating_row_colors")
        table_grid_lines = value.get("table_grid_lines")
        enable_animations = value.get("enable_animations")
        table_page_limit = value.get("table_page_limit")
        table_double_click_action = value.get("table_double_click_action")
        search_mode = value.get("search_mode")
        stats_default_span_months = value.get("stats_default_span_months")
        pareto_show_cutoff_line = value.get("pareto_show_cutoff_line")
        highlight_overdue_rows = value.get("highlight_overdue_rows", True)
        date_format_display = value.get("date_format_display", "YYYY-MM-DD")
        table_auto_scroll_to_top = value.get("table_auto_scroll_to_top", True)
        table_hover_highlight = value.get("table_hover_highlight", True)
        table_text_wrapping = value.get("table_text_wrapping", "elide")
        default_list_sort_field = value.get("default_list_sort_field", "anomaly_no_desc")
        table_show_row_numbers = value.get("table_show_row_numbers", False)
        quick_filter_case_sensitive = value.get("quick_filter_case_sensitive", False)

        # Tab 3: 表單與業務
        default_responsible_person = value.get("default_responsible_person")
        default_anomaly_category = value.get("default_anomaly_category")
        default_sync_visit = value.get("default_sync_visit")
        default_due_days = value.get("default_due_days")
        default_visit_time_slot = value.get("default_visit_time_slot")
        default_anomaly_source = value.get("default_anomaly_source", "")
        default_severity_level = value.get("default_severity_level", "一般")
        default_visit_type = value.get("default_visit_type", "例行訪廠")
        auto_fill_anomaly_no_on_date_change = value.get("auto_fill_anomaly_no_on_date_change", True)
        default_closer_name = value.get("default_closer_name", "")
        default_defect_disposition = value.get("default_defect_disposition", "")
        auto_uppercase_part_no = value.get("auto_uppercase_part_no", True)
        default_defect_sample_size = value.get("default_defect_sample_size", 0)
        require_defect_photos = value.get("require_defect_photos", False)

        # Tab 4: 匯出與報表
        default_export_dir = value.get("default_export_dir")
        export_completion_action = value.get("export_completion_action")
        report_organization_header = value.get("report_organization_header")
        export_include_charts = value.get("export_include_charts")
        export_file_naming_rule = value.get("export_file_naming_rule", "standard")
        pdf_page_orientation = value.get("pdf_page_orientation", "portrait")
        pdf_watermark_text = value.get("pdf_watermark_text", "")
        excel_autofit_columns = value.get("excel_autofit_columns", True)
        excel_theme_style = value.get("excel_theme_style", "classic_navy")
        pdf_font_density = value.get("pdf_font_density", "standard")
        export_include_disclaimer = value.get("export_include_disclaimer", True)
        export_include_summary_sheet = value.get("export_include_summary_sheet", True)
        pdf_header_logo_visible = value.get("pdf_header_logo_visible", True)

        # Tab 5: 系統與維護
        default_startup_page = value.get("default_startup_page")
        auto_backup_prompt = value.get("auto_backup_prompt")
        backup_retention_count = value.get("backup_retention_count")
        confirm_on_delete = value.get("confirm_on_delete")
        overdue_reminder_days = value.get("overdue_reminder_days", 7)
        auto_check_unresolved_on_startup = value.get("auto_check_unresolved_on_startup", True)
        clean_temp_files_on_exit = value.get("clean_temp_files_on_exit", True)
        log_level = value.get("log_level", "INFO")
        auto_save_drafts = value.get("auto_save_drafts", True)
        import_conflict_strategy = value.get("import_conflict_strategy", "prompt")
        session_restore_last_filters = value.get("session_restore_last_filters", True)
        auto_compact_db_on_exit = value.get("auto_compact_db_on_exit", False)

        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or sidebar_icon_mode not in SIDEBAR_ICON_MODE_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
            or accent_color not in ACCENT_COLOR_VALUES
            or theme_mode not in THEME_MODE_VALUES
            or cjk_font_family_preference not in CJK_FONT_PREFERENCE_VALUES
            or window_geometry_mode not in WINDOW_GEOMETRY_MODE_VALUES
            or status_bar_detail_level not in STATUS_BAR_DETAIL_LEVEL_VALUES
            or not isinstance(alternating_row_colors, bool)
            or not isinstance(table_grid_lines, bool)
            or not isinstance(enable_animations, bool)
            or default_startup_page not in STARTUP_PAGE_VALUES
            or table_page_limit not in TABLE_PAGE_LIMIT_VALUES
            or table_double_click_action not in TABLE_DOUBLE_CLICK_ACTION_VALUES
            or search_mode not in SEARCH_MODE_VALUES
            or stats_default_span_months not in STATS_DEFAULT_SPAN_MONTHS_VALUES
            or not isinstance(pareto_show_cutoff_line, bool)
            or not isinstance(highlight_overdue_rows, bool)
            or date_format_display not in DATE_FORMAT_DISPLAY_VALUES
            or not isinstance(table_auto_scroll_to_top, bool)
            or not isinstance(table_hover_highlight, bool)
            or table_text_wrapping not in TABLE_TEXT_WRAPPING_VALUES
            or default_list_sort_field not in DEFAULT_LIST_SORT_FIELD_VALUES
            or not isinstance(table_show_row_numbers, bool)
            or not isinstance(quick_filter_case_sensitive, bool)
            or not isinstance(default_responsible_person, str)
            or not isinstance(default_anomaly_category, str)
            or not isinstance(default_sync_visit, bool)
            or default_due_days not in DEFAULT_DUE_DAYS_VALUES
            or default_visit_time_slot not in DEFAULT_VISIT_TIME_SLOT_VALUES
            or not isinstance(default_anomaly_source, str)
            or default_severity_level not in DEFAULT_SEVERITY_LEVEL_VALUES
            or default_visit_type not in DEFAULT_VISIT_TYPE_VALUES
            or not isinstance(auto_fill_anomaly_no_on_date_change, bool)
            or not isinstance(default_closer_name, str)
            or default_defect_disposition not in DEFAULT_DEFECT_DISPOSITION_VALUES
            or not isinstance(auto_uppercase_part_no, bool)
            or default_defect_sample_size not in DEFAULT_DEFECT_SAMPLE_SIZE_VALUES
            or not isinstance(require_defect_photos, bool)
            or not isinstance(default_export_dir, str)
            or export_completion_action not in EXPORT_COMPLETION_ACTION_VALUES
            or not isinstance(report_organization_header, str)
            or not isinstance(export_include_charts, bool)
            or export_file_naming_rule not in EXPORT_NAMING_RULE_VALUES
            or pdf_page_orientation not in PDF_PAGE_ORIENTATION_VALUES
            or not isinstance(pdf_watermark_text, str)
            or not isinstance(excel_autofit_columns, bool)
            or excel_theme_style not in EXCEL_THEME_STYLE_VALUES
            or pdf_font_density not in PDF_FONT_DENSITY_VALUES
            or not isinstance(export_include_disclaimer, bool)
            or not isinstance(export_include_summary_sheet, bool)
            or not isinstance(pdf_header_logo_visible, bool)
            or not isinstance(auto_backup_prompt, bool)
            or backup_retention_count not in BACKUP_RETENTION_COUNT_VALUES
            or not isinstance(confirm_on_delete, bool)
            or overdue_reminder_days not in OVERDUE_REMINDER_DAYS_VALUES
            or not isinstance(auto_check_unresolved_on_startup, bool)
            or not isinstance(clean_temp_files_on_exit, bool)
            or log_level not in LOG_LEVEL_VALUES
            or not isinstance(auto_save_drafts, bool)
            or import_conflict_strategy not in IMPORT_CONFLICT_STRATEGY_VALUES
            or not isinstance(session_restore_last_filters, bool)
            or not isinstance(auto_compact_db_on_exit, bool)
        ):
            return cls.default()

        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            sidebar_icon_mode=sidebar_icon_mode,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            theme_mode=theme_mode,
            cjk_font_family_preference=cjk_font_family_preference,
            window_geometry_mode=window_geometry_mode,
            status_bar_detail_level=status_bar_detail_level,
            alternating_row_colors=alternating_row_colors,
            table_grid_lines=table_grid_lines,
            enable_animations=enable_animations,
            default_startup_page=default_startup_page,
            table_page_limit=table_page_limit,
            table_double_click_action=table_double_click_action,
            search_mode=search_mode,
            stats_default_span_months=stats_default_span_months,
            pareto_show_cutoff_line=pareto_show_cutoff_line,
            highlight_overdue_rows=highlight_overdue_rows,
            date_format_display=date_format_display,
            table_auto_scroll_to_top=table_auto_scroll_to_top,
            table_hover_highlight=table_hover_highlight,
            table_text_wrapping=table_text_wrapping,
            default_list_sort_field=default_list_sort_field,
            table_show_row_numbers=table_show_row_numbers,
            quick_filter_case_sensitive=quick_filter_case_sensitive,
            default_responsible_person=default_responsible_person,
            default_anomaly_category=default_anomaly_category,
            default_sync_visit=default_sync_visit,
            default_due_days=default_due_days,
            default_visit_time_slot=default_visit_time_slot,
            default_anomaly_source=default_anomaly_source,
            default_severity_level=default_severity_level,
            default_visit_type=default_visit_type,
            auto_fill_anomaly_no_on_date_change=auto_fill_anomaly_no_on_date_change,
            default_closer_name=default_closer_name,
            default_defect_disposition=default_defect_disposition,
            auto_uppercase_part_no=auto_uppercase_part_no,
            default_defect_sample_size=default_defect_sample_size,
            require_defect_photos=require_defect_photos,
            default_export_dir=default_export_dir,
            export_completion_action=export_completion_action,
            report_organization_header=report_organization_header,
            export_include_charts=export_include_charts,
            export_file_naming_rule=export_file_naming_rule,
            pdf_page_orientation=pdf_page_orientation,
            pdf_watermark_text=pdf_watermark_text,
            excel_autofit_columns=excel_autofit_columns,
            excel_theme_style=excel_theme_style,
            pdf_font_density=pdf_font_density,
            export_include_disclaimer=export_include_disclaimer,
            export_include_summary_sheet=export_include_summary_sheet,
            pdf_header_logo_visible=pdf_header_logo_visible,
            auto_backup_prompt=auto_backup_prompt,
            backup_retention_count=backup_retention_count,
            confirm_on_delete=confirm_on_delete,
            overdue_reminder_days=overdue_reminder_days,
            auto_check_unresolved_on_startup=auto_check_unresolved_on_startup,
            clean_temp_files_on_exit=clean_temp_files_on_exit,
            log_level=log_level,
            auto_save_drafts=auto_save_drafts,
            import_conflict_strategy=import_conflict_strategy,
            session_restore_last_filters=session_restore_last_filters,
            auto_compact_db_on_exit=auto_compact_db_on_exit,
        )

    @classmethod
    def _from_v7_mapping(cls, value: dict) -> "AppearancePreferences":
        # Tab 1: 外觀與風格
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        accent_color = value.get("accent_color")
        theme_mode = value.get("theme_mode", "light")
        cjk_font_family_preference = value.get("cjk_font_family_preference", "default")
        window_geometry_mode = value.get("window_geometry_mode", "remember")
        status_bar_detail_level = value.get("status_bar_detail_level", "standard")

        # Tab 2: 表格與檢視
        alternating_row_colors = value.get("alternating_row_colors")
        table_grid_lines = value.get("table_grid_lines")
        enable_animations = value.get("enable_animations")
        table_page_limit = value.get("table_page_limit")
        table_double_click_action = value.get("table_double_click_action")
        search_mode = value.get("search_mode")
        stats_default_span_months = value.get("stats_default_span_months")
        pareto_show_cutoff_line = value.get("pareto_show_cutoff_line")
        highlight_overdue_rows = value.get("highlight_overdue_rows", True)
        date_format_display = value.get("date_format_display", "YYYY-MM-DD")
        table_auto_scroll_to_top = value.get("table_auto_scroll_to_top", True)
        table_hover_highlight = value.get("table_hover_highlight", True)
        table_text_wrapping = value.get("table_text_wrapping", "elide")
        default_list_sort_field = value.get("default_list_sort_field", "anomaly_no_desc")

        # Tab 3: 表單與業務
        default_responsible_person = value.get("default_responsible_person")
        default_anomaly_category = value.get("default_anomaly_category")
        default_sync_visit = value.get("default_sync_visit")
        default_due_days = value.get("default_due_days")
        default_visit_time_slot = value.get("default_visit_time_slot")
        default_anomaly_source = value.get("default_anomaly_source", "")
        default_severity_level = value.get("default_severity_level", "一般")
        default_visit_type = value.get("default_visit_type", "例行訪廠")
        auto_fill_anomaly_no_on_date_change = value.get("auto_fill_anomaly_no_on_date_change", True)
        default_closer_name = value.get("default_closer_name", "")
        default_defect_disposition = value.get("default_defect_disposition", "")
        auto_uppercase_part_no = value.get("auto_uppercase_part_no", True)

        # Tab 4: 匯出與報表
        default_export_dir = value.get("default_export_dir")
        export_completion_action = value.get("export_completion_action")
        report_organization_header = value.get("report_organization_header")
        export_include_charts = value.get("export_include_charts")
        export_file_naming_rule = value.get("export_file_naming_rule", "standard")
        pdf_page_orientation = value.get("pdf_page_orientation", "portrait")
        pdf_watermark_text = value.get("pdf_watermark_text", "")
        excel_autofit_columns = value.get("excel_autofit_columns", True)
        excel_theme_style = value.get("excel_theme_style", "classic_navy")
        pdf_font_density = value.get("pdf_font_density", "standard")
        export_include_disclaimer = value.get("export_include_disclaimer", True)

        # Tab 5: 系統與維護
        default_startup_page = value.get("default_startup_page")
        auto_backup_prompt = value.get("auto_backup_prompt")
        backup_retention_count = value.get("backup_retention_count")
        confirm_on_delete = value.get("confirm_on_delete")
        overdue_reminder_days = value.get("overdue_reminder_days", 7)
        auto_check_unresolved_on_startup = value.get("auto_check_unresolved_on_startup", True)
        clean_temp_files_on_exit = value.get("clean_temp_files_on_exit", True)
        log_level = value.get("log_level", "INFO")
        auto_save_drafts = value.get("auto_save_drafts", True)
        import_conflict_strategy = value.get("import_conflict_strategy", "prompt")

        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
            or accent_color not in ACCENT_COLOR_VALUES
            or theme_mode not in THEME_MODE_VALUES
            or cjk_font_family_preference not in CJK_FONT_PREFERENCE_VALUES
            or window_geometry_mode not in WINDOW_GEOMETRY_MODE_VALUES
            or status_bar_detail_level not in STATUS_BAR_DETAIL_LEVEL_VALUES
            or not isinstance(alternating_row_colors, bool)
            or not isinstance(table_grid_lines, bool)
            or not isinstance(enable_animations, bool)
            or default_startup_page not in STARTUP_PAGE_VALUES
            or table_page_limit not in TABLE_PAGE_LIMIT_VALUES
            or table_double_click_action not in TABLE_DOUBLE_CLICK_ACTION_VALUES
            or search_mode not in SEARCH_MODE_VALUES
            or stats_default_span_months not in STATS_DEFAULT_SPAN_MONTHS_VALUES
            or not isinstance(pareto_show_cutoff_line, bool)
            or not isinstance(highlight_overdue_rows, bool)
            or date_format_display not in DATE_FORMAT_DISPLAY_VALUES
            or not isinstance(table_auto_scroll_to_top, bool)
            or not isinstance(table_hover_highlight, bool)
            or table_text_wrapping not in TABLE_TEXT_WRAPPING_VALUES
            or default_list_sort_field not in DEFAULT_LIST_SORT_FIELD_VALUES
            or not isinstance(default_responsible_person, str)
            or not isinstance(default_anomaly_category, str)
            or not isinstance(default_sync_visit, bool)
            or default_due_days not in DEFAULT_DUE_DAYS_VALUES
            or default_visit_time_slot not in DEFAULT_VISIT_TIME_SLOT_VALUES
            or not isinstance(default_anomaly_source, str)
            or default_severity_level not in DEFAULT_SEVERITY_LEVEL_VALUES
            or default_visit_type not in DEFAULT_VISIT_TYPE_VALUES
            or not isinstance(auto_fill_anomaly_no_on_date_change, bool)
            or not isinstance(default_closer_name, str)
            or default_defect_disposition not in DEFAULT_DEFECT_DISPOSITION_VALUES
            or not isinstance(auto_uppercase_part_no, bool)
            or not isinstance(default_export_dir, str)
            or export_completion_action not in EXPORT_COMPLETION_ACTION_VALUES
            or not isinstance(report_organization_header, str)
            or not isinstance(export_include_charts, bool)
            or export_file_naming_rule not in EXPORT_NAMING_RULE_VALUES
            or pdf_page_orientation not in PDF_PAGE_ORIENTATION_VALUES
            or not isinstance(pdf_watermark_text, str)
            or not isinstance(excel_autofit_columns, bool)
            or excel_theme_style not in EXCEL_THEME_STYLE_VALUES
            or pdf_font_density not in PDF_FONT_DENSITY_VALUES
            or not isinstance(export_include_disclaimer, bool)
            or not isinstance(auto_backup_prompt, bool)
            or backup_retention_count not in BACKUP_RETENTION_COUNT_VALUES
            or not isinstance(confirm_on_delete, bool)
            or overdue_reminder_days not in OVERDUE_REMINDER_DAYS_VALUES
            or not isinstance(auto_check_unresolved_on_startup, bool)
            or not isinstance(clean_temp_files_on_exit, bool)
            or log_level not in LOG_LEVEL_VALUES
            or not isinstance(auto_save_drafts, bool)
            or import_conflict_strategy not in IMPORT_CONFLICT_STRATEGY_VALUES
        ):
            return cls.default()

        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            theme_mode=theme_mode,
            cjk_font_family_preference=cjk_font_family_preference,
            window_geometry_mode=window_geometry_mode,
            status_bar_detail_level=status_bar_detail_level,
            alternating_row_colors=alternating_row_colors,
            table_grid_lines=table_grid_lines,
            enable_animations=enable_animations,
            default_startup_page=default_startup_page,
            table_page_limit=table_page_limit,
            table_double_click_action=table_double_click_action,
            search_mode=search_mode,
            stats_default_span_months=stats_default_span_months,
            pareto_show_cutoff_line=pareto_show_cutoff_line,
            highlight_overdue_rows=highlight_overdue_rows,
            date_format_display=date_format_display,
            table_auto_scroll_to_top=table_auto_scroll_to_top,
            table_hover_highlight=table_hover_highlight,
            table_text_wrapping=table_text_wrapping,
            default_list_sort_field=default_list_sort_field,
            default_responsible_person=default_responsible_person,
            default_anomaly_category=default_anomaly_category,
            default_sync_visit=default_sync_visit,
            default_due_days=default_due_days,
            default_visit_time_slot=default_visit_time_slot,
            default_anomaly_source=default_anomaly_source,
            default_severity_level=default_severity_level,
            default_visit_type=default_visit_type,
            auto_fill_anomaly_no_on_date_change=auto_fill_anomaly_no_on_date_change,
            default_closer_name=default_closer_name,
            default_defect_disposition=default_defect_disposition,
            auto_uppercase_part_no=auto_uppercase_part_no,
            default_export_dir=default_export_dir,
            export_completion_action=export_completion_action,
            report_organization_header=report_organization_header,
            export_include_charts=export_include_charts,
            export_file_naming_rule=export_file_naming_rule,
            pdf_page_orientation=pdf_page_orientation,
            pdf_watermark_text=pdf_watermark_text,
            excel_autofit_columns=excel_autofit_columns,
            excel_theme_style=excel_theme_style,
            pdf_font_density=pdf_font_density,
            export_include_disclaimer=export_include_disclaimer,
            auto_backup_prompt=auto_backup_prompt,
            backup_retention_count=backup_retention_count,
            confirm_on_delete=confirm_on_delete,
            overdue_reminder_days=overdue_reminder_days,
            auto_check_unresolved_on_startup=auto_check_unresolved_on_startup,
            clean_temp_files_on_exit=clean_temp_files_on_exit,
            log_level=log_level,
            auto_save_drafts=auto_save_drafts,
            import_conflict_strategy=import_conflict_strategy,
        )

    @classmethod
    def _from_v6_mapping(cls, value: dict) -> "AppearancePreferences":
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        accent_color = value.get("accent_color")
        theme_mode = value.get("theme_mode", "light")
        cjk_font_family_preference = value.get("cjk_font_family_preference", "default")

        alternating_row_colors = value.get("alternating_row_colors")
        table_grid_lines = value.get("table_grid_lines")
        enable_animations = value.get("enable_animations")
        table_page_limit = value.get("table_page_limit")
        table_double_click_action = value.get("table_double_click_action")
        search_mode = value.get("search_mode")
        stats_default_span_months = value.get("stats_default_span_months")
        pareto_show_cutoff_line = value.get("pareto_show_cutoff_line")
        highlight_overdue_rows = value.get("highlight_overdue_rows", True)
        date_format_display = value.get("date_format_display", "YYYY-MM-DD")
        table_auto_scroll_to_top = value.get("table_auto_scroll_to_top", True)

        default_responsible_person = value.get("default_responsible_person")
        default_anomaly_category = value.get("default_anomaly_category")
        default_sync_visit = value.get("default_sync_visit")
        default_due_days = value.get("default_due_days")
        default_visit_time_slot = value.get("default_visit_time_slot")
        default_anomaly_source = value.get("default_anomaly_source", "")
        default_severity_level = value.get("default_severity_level", "一般")
        default_visit_type = value.get("default_visit_type", "例行訪廠")
        auto_fill_anomaly_no_on_date_change = value.get("auto_fill_anomaly_no_on_date_change", True)

        default_export_dir = value.get("default_export_dir")
        export_completion_action = value.get("export_completion_action")
        report_organization_header = value.get("report_organization_header")
        export_include_charts = value.get("export_include_charts")
        export_file_naming_rule = value.get("export_file_naming_rule", "standard")
        pdf_page_orientation = value.get("pdf_page_orientation", "portrait")
        pdf_watermark_text = value.get("pdf_watermark_text", "")
        excel_autofit_columns = value.get("excel_autofit_columns", True)

        default_startup_page = value.get("default_startup_page")
        auto_backup_prompt = value.get("auto_backup_prompt")
        backup_retention_count = value.get("backup_retention_count")
        confirm_on_delete = value.get("confirm_on_delete")
        overdue_reminder_days = value.get("overdue_reminder_days", 7)
        auto_check_unresolved_on_startup = value.get("auto_check_unresolved_on_startup", True)
        clean_temp_files_on_exit = value.get("clean_temp_files_on_exit", True)

        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
            or accent_color not in ACCENT_COLOR_VALUES
            or theme_mode not in THEME_MODE_VALUES
            or cjk_font_family_preference not in CJK_FONT_PREFERENCE_VALUES
            or not isinstance(alternating_row_colors, bool)
            or not isinstance(table_grid_lines, bool)
            or not isinstance(enable_animations, bool)
            or default_startup_page not in STARTUP_PAGE_VALUES
            or table_page_limit not in TABLE_PAGE_LIMIT_VALUES
            or table_double_click_action not in TABLE_DOUBLE_CLICK_ACTION_VALUES
            or search_mode not in SEARCH_MODE_VALUES
            or stats_default_span_months not in STATS_DEFAULT_SPAN_MONTHS_VALUES
            or not isinstance(pareto_show_cutoff_line, bool)
            or not isinstance(highlight_overdue_rows, bool)
            or date_format_display not in DATE_FORMAT_DISPLAY_VALUES
            or not isinstance(table_auto_scroll_to_top, bool)
            or not isinstance(default_responsible_person, str)
            or not isinstance(default_anomaly_category, str)
            or not isinstance(default_sync_visit, bool)
            or default_due_days not in DEFAULT_DUE_DAYS_VALUES
            or default_visit_time_slot not in DEFAULT_VISIT_TIME_SLOT_VALUES
            or not isinstance(default_anomaly_source, str)
            or default_severity_level not in DEFAULT_SEVERITY_LEVEL_VALUES
            or default_visit_type not in DEFAULT_VISIT_TYPE_VALUES
            or not isinstance(auto_fill_anomaly_no_on_date_change, bool)
            or not isinstance(default_export_dir, str)
            or export_completion_action not in EXPORT_COMPLETION_ACTION_VALUES
            or not isinstance(report_organization_header, str)
            or not isinstance(export_include_charts, bool)
            or export_file_naming_rule not in EXPORT_NAMING_RULE_VALUES
            or pdf_page_orientation not in PDF_PAGE_ORIENTATION_VALUES
            or not isinstance(pdf_watermark_text, str)
            or not isinstance(excel_autofit_columns, bool)
            or not isinstance(auto_backup_prompt, bool)
            or backup_retention_count not in BACKUP_RETENTION_COUNT_VALUES
            or not isinstance(confirm_on_delete, bool)
            or overdue_reminder_days not in OVERDUE_REMINDER_DAYS_VALUES
            or not isinstance(auto_check_unresolved_on_startup, bool)
            or not isinstance(clean_temp_files_on_exit, bool)
        ):
            return cls.default()

        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            theme_mode=theme_mode,
            cjk_font_family_preference=cjk_font_family_preference,
            alternating_row_colors=alternating_row_colors,
            table_grid_lines=table_grid_lines,
            enable_animations=enable_animations,
            default_startup_page=default_startup_page,
            table_page_limit=table_page_limit,
            table_double_click_action=table_double_click_action,
            search_mode=search_mode,
            stats_default_span_months=stats_default_span_months,
            pareto_show_cutoff_line=pareto_show_cutoff_line,
            highlight_overdue_rows=highlight_overdue_rows,
            date_format_display=date_format_display,
            table_auto_scroll_to_top=table_auto_scroll_to_top,
            default_responsible_person=default_responsible_person,
            default_anomaly_category=default_anomaly_category,
            default_sync_visit=default_sync_visit,
            default_due_days=default_due_days,
            default_visit_time_slot=default_visit_time_slot,
            default_anomaly_source=default_anomaly_source,
            default_severity_level=default_severity_level,
            default_visit_type=default_visit_type,
            auto_fill_anomaly_no_on_date_change=auto_fill_anomaly_no_on_date_change,
            default_export_dir=default_export_dir,
            export_completion_action=export_completion_action,
            report_organization_header=report_organization_header,
            export_include_charts=export_include_charts,
            export_file_naming_rule=export_file_naming_rule,
            pdf_page_orientation=pdf_page_orientation,
            pdf_watermark_text=pdf_watermark_text,
            excel_autofit_columns=excel_autofit_columns,
            auto_backup_prompt=auto_backup_prompt,
            backup_retention_count=backup_retention_count,
            confirm_on_delete=confirm_on_delete,
            overdue_reminder_days=overdue_reminder_days,
            auto_check_unresolved_on_startup=auto_check_unresolved_on_startup,
            clean_temp_files_on_exit=clean_temp_files_on_exit,
        )

    @classmethod
    def _from_v5_mapping(cls, value: dict) -> "AppearancePreferences":
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        accent_color = value.get("accent_color")
        alternating_row_colors = value.get("alternating_row_colors")
        table_grid_lines = value.get("table_grid_lines")
        enable_animations = value.get("enable_animations")
        default_startup_page = value.get("default_startup_page")
        table_page_limit = value.get("table_page_limit")
        auto_backup_prompt = value.get("auto_backup_prompt")

        default_responsible_person = value.get("default_responsible_person")
        default_anomaly_category = value.get("default_anomaly_category")
        default_sync_visit = value.get("default_sync_visit")
        default_due_days = value.get("default_due_days")
        default_visit_time_slot = value.get("default_visit_time_slot")

        default_export_dir = value.get("default_export_dir")
        export_completion_action = value.get("export_completion_action")
        report_organization_header = value.get("report_organization_header")
        export_include_charts = value.get("export_include_charts")

        backup_retention_count = value.get("backup_retention_count")
        confirm_on_delete = value.get("confirm_on_delete")

        table_double_click_action = value.get("table_double_click_action")
        search_mode = value.get("search_mode")
        stats_default_span_months = value.get("stats_default_span_months")
        pareto_show_cutoff_line = value.get("pareto_show_cutoff_line")

        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
            or accent_color not in ACCENT_COLOR_VALUES
            or not isinstance(alternating_row_colors, bool)
            or not isinstance(table_grid_lines, bool)
            or not isinstance(enable_animations, bool)
            or default_startup_page not in STARTUP_PAGE_VALUES
            or table_page_limit not in TABLE_PAGE_LIMIT_VALUES
            or not isinstance(auto_backup_prompt, bool)
            or not isinstance(default_responsible_person, str)
            or not isinstance(default_anomaly_category, str)
            or not isinstance(default_sync_visit, bool)
            or default_due_days not in DEFAULT_DUE_DAYS_VALUES
            or default_visit_time_slot not in DEFAULT_VISIT_TIME_SLOT_VALUES
            or not isinstance(default_export_dir, str)
            or export_completion_action not in EXPORT_COMPLETION_ACTION_VALUES
            or not isinstance(report_organization_header, str)
            or not isinstance(export_include_charts, bool)
            or backup_retention_count not in BACKUP_RETENTION_COUNT_VALUES
            or not isinstance(confirm_on_delete, bool)
            or table_double_click_action not in TABLE_DOUBLE_CLICK_ACTION_VALUES
            or search_mode not in SEARCH_MODE_VALUES
            or stats_default_span_months not in STATS_DEFAULT_SPAN_MONTHS_VALUES
            or not isinstance(pareto_show_cutoff_line, bool)
        ):
            return cls.default()

        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            alternating_row_colors=alternating_row_colors,
            table_grid_lines=table_grid_lines,
            enable_animations=enable_animations,
            default_startup_page=default_startup_page,
            table_page_limit=table_page_limit,
            auto_backup_prompt=auto_backup_prompt,
            default_responsible_person=default_responsible_person,
            default_anomaly_category=default_anomaly_category,
            default_sync_visit=default_sync_visit,
            default_due_days=default_due_days,
            default_visit_time_slot=default_visit_time_slot,
            default_export_dir=default_export_dir,
            export_completion_action=export_completion_action,
            report_organization_header=report_organization_header,
            export_include_charts=export_include_charts,
            backup_retention_count=backup_retention_count,
            confirm_on_delete=confirm_on_delete,
            table_double_click_action=table_double_click_action,
            search_mode=search_mode,
            stats_default_span_months=stats_default_span_months,
            pareto_show_cutoff_line=pareto_show_cutoff_line,
        )

    @classmethod
    def _from_v4_mapping(cls, value: dict) -> "AppearancePreferences":
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        accent_color = value.get("accent_color")
        alternating_row_colors = value.get("alternating_row_colors")
        table_grid_lines = value.get("table_grid_lines")
        enable_animations = value.get("enable_animations")
        default_startup_page = value.get("default_startup_page")
        table_page_limit = value.get("table_page_limit")
        auto_backup_prompt = value.get("auto_backup_prompt")

        default_responsible_person = value.get("default_responsible_person")
        default_anomaly_category = value.get("default_anomaly_category")
        default_sync_visit = value.get("default_sync_visit")
        default_due_days = value.get("default_due_days")
        default_visit_time_slot = value.get("default_visit_time_slot")

        default_export_dir = value.get("default_export_dir")
        export_completion_action = value.get("export_completion_action")
        report_organization_header = value.get("report_organization_header")
        export_include_charts = value.get("export_include_charts")

        backup_retention_count = value.get("backup_retention_count")
        confirm_on_delete = value.get("confirm_on_delete")

        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
            or accent_color not in ACCENT_COLOR_VALUES
            or not isinstance(alternating_row_colors, bool)
            or not isinstance(table_grid_lines, bool)
            or not isinstance(enable_animations, bool)
            or default_startup_page not in STARTUP_PAGE_VALUES
            or table_page_limit not in TABLE_PAGE_LIMIT_VALUES
            or not isinstance(auto_backup_prompt, bool)
            or not isinstance(default_responsible_person, str)
            or not isinstance(default_anomaly_category, str)
            or not isinstance(default_sync_visit, bool)
            or default_due_days not in DEFAULT_DUE_DAYS_VALUES
            or default_visit_time_slot not in DEFAULT_VISIT_TIME_SLOT_VALUES
            or not isinstance(default_export_dir, str)
            or export_completion_action not in EXPORT_COMPLETION_ACTION_VALUES
            or not isinstance(report_organization_header, str)
            or not isinstance(export_include_charts, bool)
            or backup_retention_count not in BACKUP_RETENTION_COUNT_VALUES
            or not isinstance(confirm_on_delete, bool)
        ):
            return cls.default()

        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            alternating_row_colors=alternating_row_colors,
            table_grid_lines=table_grid_lines,
            enable_animations=enable_animations,
            default_startup_page=default_startup_page,
            table_page_limit=table_page_limit,
            auto_backup_prompt=auto_backup_prompt,
            default_responsible_person=default_responsible_person,
            default_anomaly_category=default_anomaly_category,
            default_sync_visit=default_sync_visit,
            default_due_days=default_due_days,
            default_visit_time_slot=default_visit_time_slot,
            default_export_dir=default_export_dir,
            export_completion_action=export_completion_action,
            report_organization_header=report_organization_header,
            export_include_charts=export_include_charts,
            backup_retention_count=backup_retention_count,
            confirm_on_delete=confirm_on_delete,
        )

    @classmethod
    def _from_v3_mapping(cls, value: dict) -> "AppearancePreferences":
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        accent_color = value.get("accent_color")
        alternating_row_colors = value.get("alternating_row_colors")
        table_grid_lines = value.get("table_grid_lines")
        enable_animations = value.get("enable_animations")
        default_startup_page = value.get("default_startup_page")
        table_page_limit = value.get("table_page_limit")
        auto_backup_prompt = value.get("auto_backup_prompt")

        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
            or accent_color not in ACCENT_COLOR_VALUES
            or not isinstance(alternating_row_colors, bool)
            or not isinstance(table_grid_lines, bool)
            or not isinstance(enable_animations, bool)
            or default_startup_page not in STARTUP_PAGE_VALUES
            or table_page_limit not in TABLE_PAGE_LIMIT_VALUES
            or not isinstance(auto_backup_prompt, bool)
        ):
            return cls.default()

        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
            accent_color=accent_color,
            alternating_row_colors=alternating_row_colors,
            table_grid_lines=table_grid_lines,
            enable_animations=enable_animations,
            default_startup_page=default_startup_page,
            table_page_limit=table_page_limit,
            auto_backup_prompt=auto_backup_prompt,
        )

    @classmethod
    def from_v2_mapping(cls, value: object) -> "AppearancePreferences":
        """Upgrade a valid legacy v2 payload in memory without rewriting it."""
        if not isinstance(value, dict) or set(value) != V2_FIELDS:
            return cls.default()
        density = value.get("density")
        text_scale = value.get("text_scale")
        sidebar_density = value.get("sidebar_density")
        table_density = value.get("table_density")
        contrast_mode = value.get("contrast_mode")
        if (
            density not in DENSITY_VALUES
            or text_scale not in TEXT_SCALE_VALUES
            or sidebar_density not in SIDEBAR_DENSITY_VALUES
            or table_density not in TABLE_DENSITY_VALUES
            or contrast_mode not in CONTRAST_MODE_VALUES
        ):
            return cls.default()
        return cls(
            density=density,
            text_scale=text_scale,
            sidebar_density=sidebar_density,
            table_density=table_density,
            contrast_mode=contrast_mode,
        )

    @classmethod
    def from_v1_mapping(cls, value: object) -> "AppearancePreferences":
        """Upgrade a valid legacy v1 payload in memory without rewriting it."""
        if not isinstance(value, dict) or set(value) != V1_FIELDS:
            return cls.default()
        density = value.get("density")
        text_scale = value.get("text_scale")
        if density not in DENSITY_VALUES or text_scale not in TEXT_SCALE_VALUES:
            return cls.default()
        return cls(density=density, text_scale=text_scale)

    def to_mapping(self) -> dict[str, object]:
        return {
            # Tab 1: 外觀與風格
            "density": self.density,
            "text_scale": self.text_scale,
            "sidebar_density": self.sidebar_density,
            "sidebar_icon_mode": self.sidebar_icon_mode,
            "table_density": self.table_density,
            "contrast_mode": self.contrast_mode,
            "accent_color": self.accent_color,
            "theme_mode": self.theme_mode,
            "cjk_font_family_preference": self.cjk_font_family_preference,
            "window_geometry_mode": self.window_geometry_mode,
            "status_bar_detail_level": self.status_bar_detail_level,
            # Tab 2: 表格與檢視
            "alternating_row_colors": self.alternating_row_colors,
            "table_grid_lines": self.table_grid_lines,
            "enable_animations": self.enable_animations,
            "default_startup_page": self.default_startup_page,
            "table_page_limit": self.table_page_limit,
            "table_double_click_action": self.table_double_click_action,
            "search_mode": self.search_mode,
            "stats_default_span_months": self.stats_default_span_months,
            "pareto_show_cutoff_line": self.pareto_show_cutoff_line,
            "highlight_overdue_rows": self.highlight_overdue_rows,
            "date_format_display": self.date_format_display,
            "table_auto_scroll_to_top": self.table_auto_scroll_to_top,
            "table_hover_highlight": self.table_hover_highlight,
            "table_text_wrapping": self.table_text_wrapping,
            "default_list_sort_field": self.default_list_sort_field,
            "table_show_row_numbers": self.table_show_row_numbers,
            "quick_filter_case_sensitive": self.quick_filter_case_sensitive,
            # Tab 3: 表單與業務
            "default_responsible_person": self.default_responsible_person,
            "default_anomaly_category": self.default_anomaly_category,
            "default_sync_visit": self.default_sync_visit,
            "default_due_days": self.default_due_days,
            "default_visit_time_slot": self.default_visit_time_slot,
            "default_anomaly_source": self.default_anomaly_source,
            "default_severity_level": self.default_severity_level,
            "default_visit_type": self.default_visit_type,
            "auto_fill_anomaly_no_on_date_change": self.auto_fill_anomaly_no_on_date_change,
            "default_closer_name": self.default_closer_name,
            "default_defect_disposition": self.default_defect_disposition,
            "auto_uppercase_part_no": self.auto_uppercase_part_no,
            "default_defect_sample_size": self.default_defect_sample_size,
            "require_defect_photos": self.require_defect_photos,
            # Tab 4: 匯出與報表
            "default_export_dir": self.default_export_dir,
            "export_completion_action": self.export_completion_action,
            "report_organization_header": self.report_organization_header,
            "export_include_charts": self.export_include_charts,
            "export_file_naming_rule": self.export_file_naming_rule,
            "pdf_page_orientation": self.pdf_page_orientation,
            "pdf_watermark_text": self.pdf_watermark_text,
            "excel_autofit_columns": self.excel_autofit_columns,
            "excel_theme_style": self.excel_theme_style,
            "pdf_font_density": self.pdf_font_density,
            "export_include_disclaimer": self.export_include_disclaimer,
            "export_include_summary_sheet": self.export_include_summary_sheet,
            "pdf_header_logo_visible": self.pdf_header_logo_visible,
            # Tab 5: 系統與維護
            "auto_backup_prompt": self.auto_backup_prompt,
            "backup_retention_count": self.backup_retention_count,
            "confirm_on_delete": self.confirm_on_delete,
            "overdue_reminder_days": self.overdue_reminder_days,
            "auto_check_unresolved_on_startup": self.auto_check_unresolved_on_startup,
            "clean_temp_files_on_exit": self.clean_temp_files_on_exit,
            "log_level": self.log_level,
            "auto_save_drafts": self.auto_save_drafts,
            "import_conflict_strategy": self.import_conflict_strategy,
            "session_restore_last_filters": self.session_restore_last_filters,
            "auto_compact_db_on_exit": self.auto_compact_db_on_exit,
        }
