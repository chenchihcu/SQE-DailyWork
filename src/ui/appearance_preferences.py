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
TableDensity = Literal["compact", "standard", "comfortable"]
ContrastMode = Literal["standard", "high"]
AccentColor = Literal["electric_blue", "slate_navy", "emerald", "amber"]
StartupPage = Literal["home", "events", "defects", "stats"]
TablePageLimit = Literal[25, 50, 100, 0]
ExportCompletionAction = Literal["open_file", "open_folder", "notify_only"]

TableDoubleClickAction = Literal["menu", "preview", "edit"]
SearchMode = Literal["live", "manual"]
StatsDefaultSpanMonths = Literal[3, 6, 12]

DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard", "comfortable"})
TEXT_SCALE_VALUES: Final[frozenset[str]] = frozenset({"standard", "large"})
SIDEBAR_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard"})
TABLE_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard", "comfortable"})
CONTRAST_MODE_VALUES: Final[frozenset[str]] = frozenset({"standard", "high"})
ACCENT_COLOR_VALUES: Final[frozenset[str]] = frozenset({"electric_blue", "slate_navy", "emerald", "amber"})
STARTUP_PAGE_VALUES: Final[frozenset[str]] = frozenset({"home", "events", "defects", "stats"})
TABLE_PAGE_LIMIT_VALUES: Final[frozenset[int]] = frozenset({25, 50, 100, 0})
DEFAULT_DUE_DAYS_VALUES: Final[frozenset[int]] = frozenset({7, 14, 30})
DEFAULT_VISIT_TIME_SLOT_VALUES: Final[frozenset[str]] = frozenset({"上午", "下午", "全天"})
EXPORT_COMPLETION_ACTION_VALUES: Final[frozenset[str]] = frozenset({"open_file", "open_folder", "notify_only"})
BACKUP_RETENTION_COUNT_VALUES: Final[frozenset[int]] = frozenset({5, 10, 20, 30})
TABLE_DOUBLE_CLICK_ACTION_VALUES: Final[frozenset[str]] = frozenset({"menu", "preview", "edit"})
SEARCH_MODE_VALUES: Final[frozenset[str]] = frozenset({"live", "manual"})
STATS_DEFAULT_SPAN_MONTHS_VALUES: Final[frozenset[int]] = frozenset({3, 6, 12})

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
        # v5 additions:
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
    """The complete v5 application-appearance, business and system defaults contract.

    The settings affect presentation, defaults, and user system workflows. No core
    record structures or statistics calculations are altered.
    """

    # Tab 1: 外觀主題 (Appearance & Theme)
    density: Density = "standard"
    sidebar_density: SidebarDensity = "standard"
    accent_color: AccentColor = "electric_blue"
    text_scale: TextScale = "standard"
    contrast_mode: ContrastMode = "standard"

    # Tab 2: 視覺表格與互動 (Visual, Tables & Interaction)
    table_density: TableDensity = "standard"
    alternating_row_colors: bool = True
    table_grid_lines: bool = True
    table_page_limit: int = 50
    enable_animations: bool = True
    table_double_click_action: TableDoubleClickAction = "menu"
    search_mode: SearchMode = "live"
    stats_default_span_months: int = 6
    pareto_show_cutoff_line: bool = True

    # Tab 3: 表單業務預設 (Form & Business Defaults)
    default_responsible_person: str = ""
    default_anomaly_category: str = ""
    default_sync_visit: bool = True
    default_due_days: int = 7
    default_visit_time_slot: str = "下午"

    # Tab 4: 匯出與報告 (Export & Reports)
    default_export_dir: str = ""
    export_completion_action: ExportCompletionAction = "open_file"
    report_organization_header: str = "SQE 供應商品質工程部"
    export_include_charts: bool = True

    # Tab 5: 系統與備份 (System & Backup)
    default_startup_page: StartupPage = "home"
    auto_backup_prompt: bool = True
    backup_retention_count: int = 10
    confirm_on_delete: bool = True

    @classmethod
    def default(cls) -> "AppearancePreferences":
        return cls()

    @classmethod
    def from_mapping(cls, value: object) -> "AppearancePreferences":
        """Return validated v5 profile, with graceful in-memory upgrades from v4/v3/v2/v1."""
        if not isinstance(value, dict):
            return cls.default()

        if set(value) == V5_FIELDS:
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
            "density": self.density,
            "text_scale": self.text_scale,
            "sidebar_density": self.sidebar_density,
            "table_density": self.table_density,
            "contrast_mode": self.contrast_mode,
            "accent_color": self.accent_color,
            "alternating_row_colors": self.alternating_row_colors,
            "table_grid_lines": self.table_grid_lines,
            "enable_animations": self.enable_animations,
            "default_startup_page": self.default_startup_page,
            "table_page_limit": self.table_page_limit,
            "auto_backup_prompt": self.auto_backup_prompt,
            "default_responsible_person": self.default_responsible_person,
            "default_anomaly_category": self.default_anomaly_category,
            "default_sync_visit": self.default_sync_visit,
            "default_due_days": self.default_due_days,
            "default_visit_time_slot": self.default_visit_time_slot,
            "default_export_dir": self.default_export_dir,
            "export_completion_action": self.export_completion_action,
            "report_organization_header": self.report_organization_header,
            "export_include_charts": self.export_include_charts,
            "backup_retention_count": self.backup_retention_count,
            "confirm_on_delete": self.confirm_on_delete,
            "table_double_click_action": self.table_double_click_action,
            "search_mode": self.search_mode,
            "stats_default_span_months": self.stats_default_span_months,
            "pareto_show_cutoff_line": self.pareto_show_cutoff_line,
        }


