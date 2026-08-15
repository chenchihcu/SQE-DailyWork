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

DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard", "comfortable"})
TEXT_SCALE_VALUES: Final[frozenset[str]] = frozenset({"standard", "large"})
SIDEBAR_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard"})
TABLE_DENSITY_VALUES: Final[frozenset[str]] = frozenset({"compact", "standard", "comfortable"})
CONTRAST_MODE_VALUES: Final[frozenset[str]] = frozenset({"standard", "high"})
ACCENT_COLOR_VALUES: Final[frozenset[str]] = frozenset({"electric_blue", "slate_navy", "emerald", "amber"})
STARTUP_PAGE_VALUES: Final[frozenset[str]] = frozenset({"home", "events", "defects", "stats"})
TABLE_PAGE_LIMIT_VALUES: Final[frozenset[int]] = frozenset({25, 50, 100, 0})

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
    """The complete v3 application-appearance and system defaults contract.

    The settings affect presentation and user system defaults. No business rules,
    record workflows, or statistics calculations are altered.
    """

    density: Density = "standard"
    text_scale: TextScale = "standard"
    sidebar_density: SidebarDensity = "standard"
    table_density: TableDensity = "standard"
    contrast_mode: ContrastMode = "standard"
    accent_color: AccentColor = "electric_blue"
    alternating_row_colors: bool = True
    table_grid_lines: bool = True
    enable_animations: bool = True
    default_startup_page: StartupPage = "home"
    table_page_limit: int = 50
    auto_backup_prompt: bool = True

    @classmethod
    def default(cls) -> "AppearancePreferences":
        return cls()

    @classmethod
    def from_mapping(cls, value: object) -> "AppearancePreferences":
        """Return validated v3 profile, with graceful in-memory upgrades from v2/v1."""
        if not isinstance(value, dict):
            return cls.default()

        if set(value) == V3_FIELDS:
            return cls._from_v3_mapping(value)
        elif set(value) == V2_FIELDS:
            return cls.from_v2_mapping(value)
        elif set(value) == V1_FIELDS:
            return cls.from_v1_mapping(value)

        return cls.default()

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
        }

