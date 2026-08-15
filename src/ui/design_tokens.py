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
    # ── Surfaces (light, opaque flat) ────────────────────────────────────────
    "app_bg": "#F1F5F9",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "surface_sunken": "#F1F5F9",
    "surface_hover": "#FAFBFC",
    "surface_active": "#FFFFFF",
    "surface_accent": "#F1F5F9",
    "surface_disabled": "#F5F7FA",

    # ── Text ──────────────────────────────────────────────────────────────────
    "text_primary": "#0F172A",
    "text_secondary": "#334155",
    "text_muted": "#64748B",
    "text_disabled": "#94A3B8",
    "text_inverse": "#FFFFFF",

    # ── Borders / lines ────────────────────────────────────────────────────────
    "border": "#CBD5E1",
    "border_soft": "#E2E8F0",
    "border_strong": "#94A3B8",
    "grid": "#E2E8F0",

    # ── Brand / primary ──────────────────────────────────────────────────────
    "primary": "#1E40AF",
    "primary_hover": "#1D4ED8",
    "primary_press": "#1E3A8A",
    "primary_faint": "#F0F4FF",
    "focus_ring": "#3B82F6",
    "selection_bg": "#E1EAFF",
    "accent_cyan": "#0EA5E9",
    "brand_green": "#059669",
    "accent_report": "#475569",
    "accent_overlay": "#EDF2FF",
    "accent_overlay_hover": "#E1EAFF",

    # ── Sidebar (shared deep navy rail) ──────────────────────────────────────
    "sidebar_bg": "#0F172A",
    "sidebar_panel": "#1E293B",
    "sidebar_hover": "#1E293B",
    "sidebar_active_bg": "#1E40AF",
    "sidebar_indicator": "#3B82F6",
    "sidebar_text": "#94A3B8",
    "sidebar_text_active": "#F8FAFC",
    "sidebar_muted": "#64748B",
    "sidebar_divider": "#1E293B",

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


    # ── Radii (px) — tighter for minimalist flat ────────────────────────────────
    "radius_sm": 3,
    "radius_md": 4,
    "radius_lg": 6,
}
