"""QSS section: sidebar, page header, overdue banner, brand dots."""

from __future__ import annotations

from textwrap import dedent

from ui.theme_tokens import TOKENS
from ui.layout_constants import PAGE_HEADER_HEIGHT, SIDEBAR_NAV_ITEM_HEIGHT


def get_sidebar_qss() -> str:
    return dedent(f"""\
        /* ── 左側導覽側欄 ─────────────────────────────── */
        QFrame#SidebarNav {{
            background: {TOKENS["sidebar_bg"]};
            border: none;
            border-right: 1px solid rgba(255, 255, 255, 0.12);
        }}

        QScrollArea#SidebarScroll {{
            background: transparent;
            border: none;
        }}

        QScrollArea#SidebarScroll > QWidget {{
            background: transparent;
        }}

        QWidget#SidebarNavBody {{
            background: transparent;
        }}

        QWidget#SidebarLogoSection {{
            background: {TOKENS["sidebar_panel"]};
            border-bottom: 1px solid {TOKENS["sidebar_divider"]};
        }}

        QLabel#SidebarAppTitle {{
            color: {TOKENS["nav_dark_text_active"]};
            font-size: 16px;
            font-weight: 700;
            background: transparent;
        }}

        QLabel#SidebarAppSubtitle {{
            color: {TOKENS["nav_dark_text"]};
            font-size: 11px;
            background: transparent;
        }}

        QPushButton#NavButton {{
            text-align: left;
            padding: 0px 16px;
            min-height: {SIDEBAR_NAV_ITEM_HEIGHT}px;
            border: none;
            border-left: 4px solid transparent;
            border-radius: 0px;
            background: transparent;
            color: {TOKENS["sidebar_text"]};
            font-size: 13px;
            font-weight: 400;
        }}

        /* D1 fix: child QLabels inside NavButton must inherit sidebar text colour */
        QPushButton#NavButton QLabel {{
            color: {TOKENS["sidebar_text"]};
            background: transparent;
            font-size: 13px;
            font-weight: 400;
        }}

        QPushButton#NavButton:hover {{
            background: {TOKENS["sidebar_hover_bg"]};
            color: {TOKENS["sidebar_text_active"]};
        }}

        QPushButton#NavButton:hover QLabel {{
            color: {TOKENS["sidebar_text_active"]};
        }}

        /* D2 fix: stronger active state — wider indicator + higher contrast bg */
        QPushButton#NavButton[nav_active="true"] {{
            background: {TOKENS["sidebar_active_bg"]};
            color: {TOKENS["sidebar_text_active"]};
            border-left: 4px solid {TOKENS["sidebar_active_indicator"]};
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            font-weight: 700;
        }}

        QPushButton#NavButton[nav_active="true"]:hover {{
            background: {TOKENS["sidebar_active_bg"]};
        }}

        QPushButton#NavButton[nav_active="true"] QLabel {{
            color: {TOKENS["sidebar_text_active"]};
            font-weight: 700;
        }}

        /* 並排緊湊主檔導覽（資料庫設定群組） */
        QPushButton#NavButton[nav_compact="true"] {{
            padding: 0px 4px;
            font-size: 11px;
            border-left-width: 3px;
        }}

        QPushButton#NavButton[nav_compact="true"] QLabel {{
            font-size: 11px;
        }}

        QPushButton#NavButton[nav_compact="true"][nav_active="true"] {{
            border-left-width: 3px;
        }}

        QWidget#NavButtonRow {{
            background: transparent;
        }}

        QLabel#NavIcon {{
            background: transparent;
            border: none;
        }}

        QLabel#NavBadge {{
            background: {TOKENS["status_danger_chart"]};
            color: #FFFFFF;
            font-size: 10px;
            font-weight: 700;
            border-radius: {TOKENS["radius_sm"]}px;
            padding: 2px 7px;
            min-width: 18px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}

        QWidget#NavMasterSubGroup {{
            background: transparent;
        }}

        /* 資料庫設定主檔子群組 pill 標籤（供應商主檔 / 料號主檔） */
        QLabel#SidebarMasterSubGroupLabel {{
            color: {TOKENS["sidebar_text"]};
            font-size: 10px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: {TOKENS["radius_sm"]}px;
            margin: 0px 12px 0px 12px;
        }}

        QLabel#SidebarMasterSubGroupLabel[master_subgroup="supplier"] {{
            background: {TOKENS["sidebar_master_supplier_chip_bg"]};
            color: {TOKENS["sidebar_text_active"]};
        }}

        QLabel#SidebarMasterSubGroupLabel[master_subgroup="product"] {{
            background: {TOKENS["sidebar_master_product_chip_bg"]};
            color: {TOKENS["sidebar_text_active"]};
        }}

        /* 側欄領域分組標題（無底色極簡上標） */
        QLabel#SidebarGroupHeader {{
            color: {TOKENS["sidebar_muted"]};
            background: transparent;
            font-size: 10px;
            font-weight: 700;
            padding: 6px 16px 2px 16px;
            border-radius: 0;
            margin: 6px 0 2px 0;
            letter-spacing: 1px;
        }}

        /* ── 頁面頂部標題列 ─────────────────────────────── */
        QFrame#PageHeaderBar {{
            background: {TOKENS["page_header_bg"]};
            border: none;
            border-bottom: 1px solid {TOKENS["page_header_shadow"]};
            min-height: {PAGE_HEADER_HEIGHT}px;
            max-height: {PAGE_HEADER_HEIGHT}px;
        }}

        QLabel#PageHeaderTitle {{
            color: {TOKENS["text_primary"]};
            font-size: 18px;
            font-weight: 700;
            background: transparent;
        }}

        QLabel#PageHeaderBreadcrumb {{
            color: {TOKENS["text_muted"]};
            font-size: 11px;
            background: transparent;
        }}

        /* ── 逾期警示橫幅 ─────────────────────────────── */
        QFrame#OverdueBanner {{
            background: {TOKENS["overdue_banner_bg"]};
            border: 1px solid {TOKENS["overdue_banner_border"]};
            border-radius: {TOKENS["radius_sm"]}px;
        }}

        QLabel#OverdueBannerIcon {{
            color: {TOKENS["overdue_banner_text"]};
            font-size: 16px;
            font-weight: 700;
            background: transparent;
            min-width: 24px;
            border: none;
            border-bottom: 2px solid {TOKENS["overdue_banner_border"]};
            min-height: 48px;
            max-height: 48px;
        }}

        QLabel#OverdueBannerText {{
            color: {TOKENS["overdue_banner_text"]};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        }}

        QPushButton#OverdueBannerLink {{
            color: {TOKENS["overdue_banner_link"]};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
            border: none;
            text-decoration: underline;
            padding: 0px 4px;
        }}

        QPushButton#OverdueBannerLink:hover {{
            color: {TOKENS["brand_cyan"]};
        }}

        /* ── Mitcorp 雙色品牌矩形裝飾 ───────────────────── */
        QLabel#BrandDot1 {{
            background: {TOKENS["brand_primary"]};
            border-radius: 2px;
        }}

        QLabel#BrandDot2 {{
            background: {TOKENS["brand_green"]};
            border-radius: 2px;
        }}
    """).strip()
