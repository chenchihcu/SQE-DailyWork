"""Unified design tokens — single source of truth for the merged SQE DailyWork app.

Both the SQE DailyWork shell (``ui/theme.py`` ``TOKENS``) and the embedded NCR module
(``ncr/ui/ui_style.py`` ``COLOR_*``) re-source their colours from ``PALETTE`` here,
so the whole window reads as one piece of software.

New unified palette (decision 2026-06-02): a fresh light-based professional scheme
— clean neutral surfaces, a brighter primary blue, and a single deep slate-navy
navigation rail shared by both modules. Replaces SQE DailyWork's older teal-blue light
theme and the former standalone warehouse-tracking dark theme.
"""
from __future__ import annotations

PALETTE: dict[str, object] = {
    # ── Surfaces (light) ────────────────────────────────────────────────────
    "app_bg": "#F4F6F9",
    "surface": "#FFFFFF",
    "surface_alt": "#F7F9FC",
    "surface_sunken": "#EDF1F6",
    "surface_hover": "#EEF4FC",
    "surface_active": "#E2EEFC",
    "surface_accent": "#DCEBFB",
    "surface_disabled": "#EDF1F6",

    # ── Text ──────────────────────────────────────────────────────────────────
    "text_primary": "#1A2330",
    "text_secondary": "#46566B",
    "text_muted": "#6B7C90",
    "text_disabled": "#9AA8B6",
    "text_inverse": "#FFFFFF",

    # ── Borders / lines ────────────────────────────────────────────────────────
    "border": "#D5DEE8",
    "border_soft": "#E2E9F0",
    "border_strong": "#AFBED0",
    "grid": "#DCE4ED",

    # ── Brand / primary ──────────────────────────────────────────────────────
    "primary": "#1F6FEB",
    "primary_hover": "#1A5FD0",
    "primary_press": "#164FB0",
    "primary_faint": "#E8F1FE",
    "focus_ring": "#5C9DF5",
    "selection_bg": "#CFE2FD",
    "accent_cyan": "#2BA6E0",
    "brand_green": "#1FA85B",
    "steel": "#5E7184",
    "accent_overlay": "rgba(31, 111, 235, 0.10)",
    "accent_overlay_hover": "rgba(31, 111, 235, 0.16)",

    # ── Sidebar (shared deep navy rail) ──────────────────────────────────────
    "sidebar_bg": "#0E2233",
    "sidebar_panel": "#122B40",
    "sidebar_hover": "#16344C",
    "sidebar_active_bg": "#1B4D70",
    "sidebar_indicator": "#36A8E0",
    "sidebar_text": "#C7DBEA",
    "sidebar_text_active": "#FFFFFF",
    "sidebar_muted": "#7C93A8",
    "sidebar_divider": "#1C3B54",

    # ── Status: pending (amber) ────────────────────────────────────────────────
    "pending_fg": "#8A5A00",
    "pending_bg": "#FFF3D6",
    "pending_border": "#F2C66B",
    "pending_chart": "#E0922A",
    # ── Status: success (green) ────────────────────────────────────────────────
    "success_fg": "#0F6B45",
    "success_bg": "#DCF6E8",
    "success_border": "#84D6AE",
    "success_chart": "#16A06A",
    # ── Status: danger (red) ───────────────────────────────────────────────────
    "danger_fg": "#B11B2B",
    "danger_bg": "#FCE6E9",
    "danger_border": "#F2A3AD",
    "danger_chart": "#D8364C",
    # ── Status: info (blue) ────────────────────────────────────────────────────
    "info_fg": "#155CC0",
    "info_bg": "#E6F0FE",
    "info_border": "#9CC4F4",
    "info_chart": "#1F6FEB",
    # ── Status: neutral / NA (slate) ──────────────────────────────────────────
    "na_fg": "#51647A",
    "na_bg": "#E7EDF3",
    "na_border": "#B9C7D6",
    "na_chart": "#6B7C90",

    # ── Charts (categorical) ───────────────────────────────────────────────────
    "chart_1": "#1F6FEB",
    "chart_2": "#14A38B",
    "chart_3": "#E8833A",
    "chart_4": "#B95CF0",
    "chart_5": "#E0455E",
    "chart_grid": "#E2E9F0",
    "chart_axis": "#46566B",
    # Plot area background, kept distinct from the figure surface (the card's
    # panel_bg) so the plotting region reads as its own layer (universal §10).
    "chart_plot_bg": "#FFFFFF",

    # ── Hero banner gradient (SQE DailyWork home) ──────────────────────────────────
    "hero_start": "#0E2233",
    "hero_mid": "#1B4D70",
    "hero_end": "#1F6FEB",
    "on_hero_subtitle": "#CFE4F5",
    "on_hero_meta": "#E4EFF8",

    # ── Radii (px) ─────────────────────────────────────────────────────────────
    "radius_sm": 4,
    "radius_md": 6,
    "radius_lg": 8,
}


def color(name: str) -> object:
    """Return a palette colour by name (raises KeyError if missing — fail fast)."""
    return PALETTE[name]
