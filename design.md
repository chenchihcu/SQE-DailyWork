---
version: alpha
name: SQE DailyWork Design System
description: Unified Industrial Inspection & Quality Engineering Design System (Slate + Electric Blue)

> **Historical note (2026-09-09):** Workbench now uses four tabs (`案件概覽` / `Action 清單` / `根本原因` / `附件與佐證`); the `處理歷程` tab and embedded analysis/hypothesis flows are retired. See `docs/exec-plans/completed/workbench-timeline-tab-retire.md` and `workbench-legacy-analysis-retire.md`. Sections below may describe pre-retirement layout.
colors:
  # ── Surfaces ─────────────────────────────────────────────────────────────
  app-bg: "#F1F5F9"
  surface: "#FFFFFF"
  surface-alt: "#F8FAFC"
  surface-sunken: "#F1F5F9"
  surface-hover: "#FAFBFC"
  surface-active: "#FFFFFF"
  surface-accent: "#F1F5F9"
  surface-disabled: "#F5F7FA"

  # ── Text ─────────────────────────────────────────────────────────────────
  text-primary: "#0F172A"
  text-secondary: "#334155"
  text-muted: "#64748B"
  text-disabled: "#94A3B8"
  text-inverse: "#FFFFFF"

  # ── Borders & Grids ──────────────────────────────────────────────────────
  border: "#CBD5E1"
  border-soft: "#E2E8F0"
  border-strong: "#94A3B8"
  grid: "#E2E8F0"

  # ── Brand & Primary ──────────────────────────────────────────────────────
  primary: "#1E40AF"
  primary-hover: "#1D4ED8"
  primary-press: "#1E3A8A"
  primary-faint: "#F0F4FF"
  focus-ring: "#3B82F6"
  selection-bg: "#E1EAFF"
  accent-cyan: "#0EA5E9"
  brand-green: "#059669"
  accent-report: "#475569"
  accent-overlay: "#EDF2FF"
  accent-overlay-hover: "#E1EAFF"

  # ── Sidebar (Deep Slate-Navy Rail) ────────────────────────────────────────
  sidebar-bg: "#0F172A"
  sidebar-panel: "#1E293B"
  sidebar-hover: "#1E293B"
  sidebar-active-bg: "#1E40AF"
  sidebar-indicator: "#3B82F6"
  sidebar-text: "#94A3B8"
  sidebar-text-active: "#F8FAFC"
  sidebar-muted: "#64748B"
  sidebar-divider: "#1E293B"
  sidebar-master-supplier-chip-bg: "#1E3A5F"
  sidebar-master-product-chip-bg: "#1A3D32"

  # ── Status: Pending (Amber) ──────────────────────────────────────────────
  pending-fg: "#8A5A00"
  pending-bg: "#FFF3D6"
  pending-border: "#F2C66B"
  pending-chart: "#E0922A"

  # ── Status: Success (Green) ──────────────────────────────────────────────
  success-fg: "#0F6B45"
  success-bg: "#DCF6E8"
  success-border: "#84D6AE"
  success-chart: "#16A06A"

  # ── Status: Danger (Red) ─────────────────────────────────────────────────
  danger-fg: "#B11B2B"
  danger-bg: "#FCE6E9"
  danger-border: "#F2A3AD"
  danger-chart: "#D8364C"

  # ── Status: Info (Blue) ──────────────────────────────────────────────────
  info-fg: "#155CC0"
  info-bg: "#E6F0FE"
  info-border: "#9CC4F4"
  info-chart: "#1F6FEB"

  # ── Status: Neutral / NA (Slate) ─────────────────────────────────────────
  na-fg: "#51647A"
  na-bg: "#E7EDF3"
  na-border: "#B9C7D6"
  na-chart: "#6B7C90"

  # ── Charts (Categorical) ─────────────────────────────────────────────────
  chart-1: "#1F6FEB"
  chart-2: "#14A38B"
  chart-3: "#E8833A"
  chart-4: "#B95CF0"
  chart-5: "#E0455E"
  chart-grid: "#E2E9F0"
  chart-axis: "#46566B"
  chart-plot-bg: "#FFFFFF"

  # ── Hero Gradient ────────────────────────────────────────────────────────
  hero-start: "#0E2233"
  hero-mid: "#1B4D70"
  hero-end: "#1F6FEB"

typography:
  brand-title:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.2
  page-title:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.2
  section-title:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.3
  label-strong:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  body-small:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
  caption:
    fontFamily: "'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI', sans-serif"
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.3
  mono:
    fontFamily: "'Consolas', 'Cascadia Code', monospace"
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.4

rounded:
  sm: 3px
  md: 4px
  lg: 6px
  full: 9999px

spacing:
  xs: 2px
  sm: 4px
  md: 8px
  lg: 12px
  xl: 16px
  2xl: 24px
  3xl: 32px

components:
  sidebar:
    width: 220px
    itemHeight: 38px
    background: "{colors.sidebar-bg}"
    activeBackground: "{colors.sidebar-active-bg}"
    indicatorColor: "{colors.sidebar-indicator}"
    textColor: "{colors.sidebar-text}"
    activeTextColor: "{colors.sidebar-text-active}"
  control:
    minHeight: 30px
    borderRadius: "{rounded.md}"
    borderColor: "{colors.border}"
    focusBorder: "{colors.focus-ring}"
  button-primary:
    minHeight: 30px
    background: "{colors.primary}"
    hoverBackground: "{colors.primary-hover}"
    textColor: "{colors.text-inverse}"
    padding: "4px 16px"
    borderRadius: "{rounded.md}"
  button-secondary:
    minHeight: 30px
    background: "{colors.surface}"
    hoverBackground: "{colors.surface-hover}"
    borderColor: "{colors.border}"
    textColor: "{colors.text-secondary}"
    padding: "4px 16px"
    borderRadius: "{rounded.md}"
  card:
    background: "{colors.surface}"
    borderColor: "{colors.border-soft}"
    borderRadius: "{rounded.md}"
    padding: "12px 10px"
  table:
    rowHeight: 32px
    headerBackground: "{colors.surface-alt}"
    gridColor: "{colors.grid}"
    cellPadding: 6px
  badge:
    borderRadius: "{rounded.sm}"
    padding: "2px 8px"
    fontSize: "{typography.caption.fontSize}"
  form-container:
    maxWidth: 960px
    gutter: 12px
    rowGap: 8px
---

# SQE DailyWork Design System

Unified Design Specification & Token Reference for SQE DailyWork (Supplier Quality Engineering & Incident Management).  
This document serves as the single source of truth (SSOT) for UI design, layout architecture, and tokens for cross-agent collaboration (Google Stitch AI, Claude Code, Cursor, Codex, and Antigravity).

---

## Overview

### Brand Identity & Style
SQE DailyWork is an industrial-grade desktop workstation designed for Supplier Quality Engineers (SQE), incoming quality control (IQC), and manufacturing defect management. Inspired by MITCorp's precision industrial inspection hardware, the interface projects reliability, high information density, structural rigor, and instant scanning capability.

- **Aesthetic**: High density, flat Slate surfaces (`#F1F5F9` / `#FFFFFF`), crisp Electric Blue primary accents (`#1E40AF` / `#1D4ED8`), and a deep Slate-Navy navigation rail (`#0F172A`).
- **Target Audience**: Quality engineers, SQE leads, plant managers, and factory technical personnel operating under laptop (1360×860 / 1024×680) and multi-monitor shop-floor setups.
- **Brand Motifs**: Clean rectangular double-dot brand mark (`14px × 4px` rectangle pairing Deep Cyan `#0EA5E9` and Industrial Green `#059669`).

### Core Design Principles
1. **Minimum Necessary Input (最低必要輸入)**:
   Intake and creation flows require only mission-critical fields. Complex defect documentation, 8D analyses, attachments, and hypotheses are progressively disclosed in detail tabs.
2. **Case First, Documents Second (案例優先，文件其次)**:
   The Incident Case (案例) is the core operational entity. Photos, FA reports, 8D forms, and supplier communications attach to the case rather than splintering into detached workflows.
3. **Next Action Drives Daily Work (Next Action 驅動日常)**:
   Quality daily routines center on actionable tasks: *What needs to be done? Who owns it? When is it due? Is it overdue?* List views and workbenches feature immediate status, responsible owner, next action, and due date.
4. **Evidence Before Conclusion (先有證據再下結論)**:
   Root cause investigations strictly separate `FACT`, `INFERENCE`, `ASSUMPTION`, and `UNKNOWN`. UI avoids "check-to-prove" fallacies by visually segregating hypothesis evidence from root cause conclusion badges.
5. **Zero-Noise Analytics (統計看板純淨化)**:
   Analytics surfaces display only high-value interactive charts, date range filters, and export controls. AI-generated textual summaries, verbose insight boxes, and decorative banners are banned.
6. **Operational Workbench over Decorative Landing (工作台導向)**:
   The application launches straight into operational query queues (`事件查詢`). Decorative cover landing pages, hero banners, and "card-in-card" nesting wrappers are eliminated.

---

## Colors

### Surface Hierarchy
Surfaces use a neutral light slate palette designed for extended reading without eye fatigue:

| Token Name | Hex | CSS Variable / Tailwind | Usage & Semantics |
| :--- | :--- | :--- | :--- |
| `app-bg` | `#F1F5F9` | `var(--app-bg)` / `slate-100` | Application window background canvas |
| `surface` | `#FFFFFF` | `var(--surface)` / `white` | Standard card, panel, and table canvas |
| `surface-alt` | `#F8FAFC` | `var(--surface-alt)` / `slate-50` | Table headers, toolbar bars, and tab panels |
| `surface-sunken` | `#F1F5F9` | `var(--surface-sunken)` / `slate-100` | Sunken inputs, code blocks, and subtle wells |
| `surface-hover` | `#FAFBFC` | `var(--surface-hover)` | Subtle row and button hover state |
| `surface-disabled` | `#F5F7FA` | `var(--surface-disabled)` | Disabled input backgrounds |

### Typography Colors
Text contrast strictly complies with WCAG AA standards against all surface layers:

| Token Name | Hex | CSS Variable / Tailwind | Usage & Semantics |
| :--- | :--- | :--- | :--- |
| `text-primary` | `#0F172A` | `var(--text-primary)` / `slate-900` | Primary content, form labels, headings, table data |
| `text-secondary` | `#334155` | `var(--text-secondary)` / `slate-700` | Secondary labels, descriptions, toolbar button text |
| `text-muted` | `#64748B` | `var(--text-muted)` / `slate-500` | Placeholders, timestamps, helper text, inactive tabs |
| `text-disabled` | `#94A3B8` | `var(--text-disabled)` / `slate-400` | Disabled control text |
| `text-inverse` | `#FFFFFF` | `var(--text-inverse)` / `white` | Text on primary brand and dark backgrounds |

### Brand & Interactive Colors
| Token Name | Hex | CSS Variable / Tailwind | Usage & Semantics |
| :--- | :--- | :--- | :--- |
| `primary` | `#1E40AF` | `var(--primary)` / `blue-800` | Primary action button, active tab indicator, core brand |
| `primary-hover` | `#1D4ED8` | `var(--primary-hover)` / `blue-700` | Primary button hover state |
| `primary-press` | `#1E3A8A` | `var(--primary-press)` / `blue-900` | Primary button active/pressed state |
| `primary-faint` | `#F0F4FF` | `var(--primary-faint)` | Active filter chip background, selection highlight |
| `focus-ring` | `#3B82F6` | `var(--focus-ring)` / `blue-500` | Focus outline on interactive inputs (2px offset) |
| `selection-bg` | `#E1EAFF` | `var(--selection-bg)` | Table row selection, text highlight background |
| `accent-cyan` | `#0EA5E9` | `var(--accent-cyan)` / `sky-500` | Secondary brand dot, active filter border |
| `brand-green` | `#059669` | `var(--brand-green)` / `emerald-600` | Tertiary brand dot, success operational metric |

### Deep Slate-Navy Navigation Rail (Sidebar)
The left navigation bar is unified in a deep slate-navy tone to establish a strong visual anchor:

| Token Name | Hex | Usage & Semantics |
| :--- | :--- | :--- |
| `sidebar-bg` | `#0F172A` | Left sidebar background canvas (`220px` fixed width) |
| `sidebar-panel` | `#1E293B` | Sidebar grouping panels and divider lines |
| `sidebar-hover` | `#1E293B` | Navigation item hover background |
| `sidebar-active-bg` | `#1E40AF` | Currently active navigation item background |
| `sidebar-indicator` | `#3B82F6` | Active item left indicator bar (`3px` solid) |
| `sidebar-text` | `#94A3B8` | Unselected navigation item text and icon |
| `sidebar-text-active` | `#F8FAFC` | Active navigation item text |
| `sidebar-muted` | `#64748B` | Category section headers (`11px` bold uppercase) |

### Status Badges & Indicators
Every status category possesses an explicit foreground/background/border/chart tuple:

| Status Role | Foreground (`fg`) | Background (`bg`) | Border (`border`) | Chart Color (`chart`) | Business Semantics |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pending (待處理)** | `#8A5A00` | `#FFF3D6` | `#F2C66B` | `#E0922A` | Open case, pending supplier response, overdue task |
| **Success (已結案)** | `#0F6B45` | `#DCF6E8` | `#84D6AE` | `#16A06A` | Case closed, verification passed, verified root cause |
| **Danger (嚴重/退件)**| `#B11B2B` | `#FCE6E9` | `#F2A3AD` | `#D8364C` | Critical severity, rejected 8D, audit failure |
| **Info (處理中)** | `#155CC0` | `#E6F0FE` | `#9CC4F4` | `#1F6FEB` | In progress, containment active, under analysis |
| **Neutral / NA (未指定)**| `#51647A` | `#E7EDF3` | `#B9C7D6` | `#6B7C90` | Not applicable, draft, inactive, unassigned |

### Categorical Charts
Visual analytics strictly apply the following categorical color sequence:
- `chart_1`: `#1F6FEB` (Primary Blue - Occurrence / Anomaly Volume)
- `chart_2`: `#14A38B` (Teal Green - Pass rate / Closure Volume)
- `chart_3`: `#E8833A` (Warm Amber - Pareto Cumulative Line / Material Defect)
- `chart_4`: `#B95CF0` (Purple - Outsource Line / SMT Defect)
- `chart_5`: `#E0455E` (Rose Red - Critical Alarm / Scrap Count)
- `chart_plot_bg`: `#FFFFFF` (Plot area canvas, visually demarcated from container panels)
- `chart_grid`: `#E2E9F0` (Subtle 1px dotted coordinate lines)

---

## Typography

### CJK Font Stack & Fallback Chain
Traditional Chinese (zh-TW) is the authoritative interface language, supported by an exact cross-platform fallback sequence:

```css
font-family: 'Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI',
             'PingFang TC', 'Noto Sans TC', 'Noto Sans CJK TC',
             'Source Han Sans TC', sans-serif;
```

For numerical and code display (e.g. 11-digit Anomaly Numbers, ERP Part Numbers):
```css
font-family: 'Consolas', 'Cascadia Code', 'Segoe UI Mono', monospace;
```

### Scale & Hierarchy
| Token Name | Size | Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- | :--- |
| `brand-title` | `22px` | 700 (Bold) | 1.2 | Main window header brand label (`SQE DailyWork`) |
| `page-title` | `24px` | 700 (Bold) | 1.2 | Standalone full-page title |
| `section-title` | `16px` | 600 (Semi-bold)| 1.3 | Group box headers, modal section headers, card titles |
| `label-strong` | `14px` | 600 (Semi-bold)| 1.4 | Form field labels, prominent table headers, KPI metrics |
| `body` (Base) | `13px` | 400 (Regular) | 1.5 | Primary data table cells, inputs, descriptions, list rows |
| `body-small` | `12px` | 400 (Regular) | 1.4 | Helper text, secondary descriptions, metadata rows |
| `caption` | `11px` | 400 / 600 | 1.3 | Status badges, category tags, sidebar section headers |
| `mono` | `11px` | 400 (Regular) | 1.4 | Part numbers, anomaly numbers, ERP timestamps |

### Centralized Chart Typography Contract
All QtCharts and analytics visual components must strictly adhere to the single source of truth in `chart_style.py`:
- **Chart Title**: `11pt Bold` (`CHART_TITLE_POINT_SIZE`)
- **Axis Title**: `9pt Bold` (`CHART_AXIS_TITLE_POINT_SIZE`)
- **Axis Labels**: `9pt Regular` (`CHART_AXIS_LABEL_POINT_SIZE`)
- **Legend Labels**: `8pt Regular` (`CHART_LEGEND_POINT_SIZE`)
- **Data / Slice Labels**: `8pt Regular / Bold` (`CHART_DATA_LABEL_POINT_SIZE`)

---

## Layout

### Window & Screen Adaptation
- **Default Resolution**: `1360px × 860px` (optimized for laptop workspaces).
- **Minimum Resolution**: `1024px × 680px` (guaranteed usable without clipping primary controls).
- **Screen Boundary Cap**: Max width/height strictly capped at `95%` of the active monitor's work area (`WINDOW_SCREEN_FRACTION = 0.95`).
- **Form Area Max Width**: `960px` (`FORM_MAX_WIDTH`) centered in desktop viewport to prevent overly wide, unreadable input fields.

### Spacing & Grid Rhythm
The system operates on a compact `4px / 8px` base unit grid:

```
GRID_GUTTER = 12px (Horizontal gap between columns)
ROW_GAP     = 8px  (Vertical gap between form rows)
```

| Layout Target | Margin (px) | Spacing (px) | Rule / Purpose |
| :--- | :--- | :--- | :--- |
| **Top-Level Page Canvas** | `(24, 24, 24, 24)` | `8px` | `PAGE_OUTER_MARGINS`: Outer page padding |
| **Panel / Card Inner** | `(12, 10, 12, 10)` | `8px` | `PANEL_MARGINS`: High density container padding |
| **Modal Dialog Canvas** | `(16, 14, 16, 14)` | `8px` | `DIALOG_OUTER_MARGINS`: Compact dialog boundaries |
| **Symmetric Form Grid** | `(16, 12, 16, 14)` | `12px H / 8px V` | 2-column symmetric form layout |
| **Compact Command Row** | `(12, 6, 12, 6)` | `8px` | Toolbar filter and action container |

### Symmetric 2-Column Grid Standard
Multi-field data entry forms use a strictly symmetric 2-column grid (`field_count = 2`):
- **Column 0 & 2**: Labels (`NCR_LABEL_WIDTH = 92px`, right-aligned with `18px` horizontal padding).
- **Column 1 & 3**: Input controls (`1:1` stretch ratio).
- *Never mix column offsets or nest unbalanced rows within a single grid layout.*

### Bottom Action Bar Standard (方案 A 底部操作列)
All full-page create and entry surfaces (`CreateWorkflowShell` / `DefectFormWidget`) position primary action buttons at the bottom of the viewport:
- **Left Side**: Reset / secondary actions (`清除 / 重置` - `variant="secondary"`).
- **Right Side**: Primary workflow navigation and commit actions (`返回清單` - `variant="secondary"` + `儲存` - `variant="primary"`).
- *Primary submit buttons must NEVER be placed in the top header.*

### Responsive List Reading Chain
All data tables follow a standardized left-to-right cognitive scanning order:
$$\text{單號 / 日期} \longrightarrow \text{供應商} \longrightarrow \text{料號} \longrightarrow \text{品名} \longrightarrow \text{階段} \longrightarrow \text{異常類別} \longrightarrow \text{責任人} \longrightarrow \text{摘要 / 描述} \longrightarrow \text{期限 / 處置} \longrightarrow \text{狀態}$$

- **重點欄位 (Core Columns)**: When window width $< 1024\text{px}$, tables switch to core columns (`異常單號 106px`, `供應商 110px`, `料號 130px`, `品名 140px`, `異常類別 115px`, `狀態 78px`).
- **完整欄位 (Full Columns)**: Displays full ERP trace and warehouse resolution fields with horizontal scrolling.

---

## Elevation & Depth

SQE DailyWork employs an **Industrial Flat Surface** philosophy. Heavy drop shadows, multi-tier elevations, and glassmorphism blurs are avoided to maximize readability and performance on resource-constrained industrial workstations.

```
Level 0: Window Canvas (app-bg: #F1F5F9)
  │
  ├── Level 1: Flat Panels & Cards (surface: #FFFFFF, border: #CBD5E1)
  │     │
  │     ├── Level 2: Subpanels & Table Headers (surface-alt: #F8FAFC, border-soft: #E2E8F0)
  │     │
  │     └── Sub-level: Sunken Input Wells (surface-sunken: #F1F5F9, border: #CBD5E1)
  │
  └── Level 3: Modal Dialogs & Menus (surface: #FFFFFF, 1px solid #94A3B8, subtle 4px shadow)
```

- **Borders over Shadows**: Hierarchical separation is achieved via `1px solid #CBD5E1` (standard border) and `1px solid #E2E8F0` (soft divider).
- **Interactive State Elevation**: Buttons and table rows indicate focus and hover via surface color shifts (`#FAFBFC` hover, `#E1EAFF` selection) and 2px focus rings (`#3B82F6`), never by geometric expansion or shadow growth.

---

## Shapes

### Corner Radii
Corners are tightly controlled to project an engineered, robust appearance:
- `radius_sm` (`3px`): Status badges, filter chips, table selection markers.
- `radius_md` (`4px`): Text inputs, combo boxes, push buttons, card containers, dialog bodies.
- `radius_lg` (`6px`): Application window framing, modal outer containers.
- `radius_full` (`9999px`): Status pill badges, category markers.

### Signature Brand Geometry
- **MITCorp Signature Mark**: Double-dot rectangular geometry (`BRAND_ACCENT_DOT_W = 14px`, `BRAND_ACCENT_DOT_H = 4px`), featuring `accent-cyan` (`#0EA5E9`) alongside `brand-green` (`#059669`).

---

## Components

### Archetype 1: `CreateWorkflowShell` (Full-Page Form)
- **Container Structure**: One outer page container, exactly one top-to-bottom vertical `QScrollArea`, and a pinned bottom action bar (`Bottom Action Bar - 方案 A`).
- **Input Area**: Centered `960px` max-width container (`FORM_MAX_WIDTH`), utilizing symmetric 2-column grid.
- **Section Headers**: Structured with semantic iconography (`📋 基本資訊`, `🔍 不良現象與問題描述`, `📸 現場照片佐證`).
- **Dynamic Rows**: Uses `BulletListWidget` for multi-item narrative descriptions.
- **Action Bar**:
  ```
  [ 清除 / 重置 (Secondary) ] ────────────── [ 返回清單 (Secondary) ] [ 儲存異常 (Primary) ]
  ```

### Archetype 2: Data Tables & Scope Filter Chips (`EventListWidget`)
- **Top Command Row**: Filter controls (`Search`, `Supplier ComboBox`, `Status ComboBox`, `Month Range`) aligned at `CONTROL_MIN_HEIGHT = 30px`.
- **Scope Chips**: Horizontal chip group displaying operational scopes with live counts: `單獨異常 (N)` and `已結案 (N)`.
- **Table Density**: Row height `32px` (`TABLE_ITEM_MIN_HEIGHT`), cell padding `6px`, alternating row backgrounds (`#FFFFFF` / `#F8FAFC`).
- **Anomaly Number Formatting**: Strictly formatted as 11 digits pure numbers (`YYYYMMDDNNN`, e.g., `20260908001`). Column width pinned to `106px`.
- **Status Badges**: Inline pills (`2px 8px` padding, `3px` radius) mapped to the 5 semantic status colors.

### Archetype 3: Anomaly Management Workbench (`AnomalyManagementPage`)
- **Fixed Header**: Case identity banner displaying Anomaly No, Supplier, Responsible Person, Creation Date, and current Status Badge.
- **Header Lifecycle Action**: Dynamic contextual button (shows `結案` for open cases, `重新開啟` for closed cases).
- **Tabbed Layout**: Four tabs with independent scroll ownership (2026-09-09):
  1. `案件概覽 (Case Overview)`: 2×2 quick overview card, Next Action card with due date countdown, and embedded basic anomaly edit.
  2. `Action 清單 (Action List)`: Read-only `AnomalyActionTable` with workflow buttons; create/edit via dialogs using `ActionItemListWidget`.
  3. `根本原因 (Root Cause)`: Investigation badges and the single root-cause card.
  4. `附件與佐證 (Attachments & Evidence)`: Visual thumbnail grid with attachment category badges and live upload dropzone; Supplier 8D via attachment category.
  - Retired: `處理歷程 (Audit Timeline)` tab — audit rows still write to `anomaly_audit_logs` in the background.

### Archetype 4: Zero-Noise Analytics Dashboard (`StatsViewWidget`)
- **Header Controls**: Minimalist toolbar containing only `Date Range Filter`, `重新整理 (Secondary Button)`, and `匯出 Excel (Primary Button)`.
- **Clean Visualization**: 2×2 grid of interactive Qt charts (Categorical Pareto, Trend Line, Supplier Risk Distribution, SMT Keyword Analysis).
- **Zero-Noise Standard**: All auto-generated textual summaries, verbose management paragraphs, and floating insight banners are permanently removed from the layout.
- **Pareto Cutoff**: Integrated 80/20 threshold line with clear secondary axis typography.

### Specialized UI Controls
- **`BulletListWidget` (條列式逐條審閱元件)**:
  Used for itemized defect descriptions and tracking items.
  ```
  [ 01 ] [ 輸入描述項目內容...                         ] [ ✕ 刪除 ]
  [ 02 ] [ 輸入描述項目內容...                         ] [ ✕ 刪除 ]
  [ + 新增條目 ]
  ```
- **`TagInputWidget` (製程關鍵字標籤選擇器)**:
  Displays selected SMT/Process keyword chips with interactive removal, autocomplete suggestions, and quick preset management.
- **`SidebarNav` (導覽側欄)**:
  `220px` width, `38px` row height, 4 major domain groups: `供應商事件`, `倉庫不合格品`, `資料庫設定`, `系統`. Distinct pill highlights for master data subgroups (`原物料` vs `委外加工`).

---

## Do's and Don'ts

| Category | DO (必須遵循) | DON'T (嚴格禁止) |
| :--- | :--- | :--- |
| **Form Layout** | All full-page create views must use **Bottom Action Bar (Scheme A)** with primary commit on the bottom right. | **Never** place primary submit buttons (`儲存`) in the top navigation bar or page header. |
| **Form Layout** | Multi-field grids must use symmetric 2-column layouts (`Col 0/2 Label: 92px`, `Col 1/3 Input: 1:1 stretch`). | **Do not** mix column offsets or nest random 3-column rows within standard forms. |
| **CJK Typography** | Checkbox and RadioButton controls must maintain standard `LeftToRight` layout direction. | **Never** invoke `setLayoutDirection(RightToLeft)` on CJK controls (avoids indicator overlap bug in Windows Qt). |
| **Information Density** | Surfaces must be flat and bordered (`1px solid #CBD5E1`), keeping default entrypoint on operational queues. | **Do not** reintroduce decorative landing hubs, hero covers, marketing cards, or card-in-card wrappers. |
| **Analytics** | Dashboard pages must strictly feature only filters, refresh/export buttons, and visual charts. | **Do not** generate or display verbose textual insight paragraphs or diagnosis banners (**Zero-Noise** rule). |
| **Component Structure** | Use `BulletListWidget` for narrative lists to support item-by-item review and newline compatibility. | **Do not** force multi-item defect lists into single unstructured multi-line textareas. |
| **Chart Styling** | Consume typography tokens strictly from `chart_style.py` (`11pt` title, `9pt` axis, `8pt` data). | **Never** hardcode ad-hoc `QFont` point sizes in chart builder methods. |
| **Workflow Boundary** | Supplier Event line (`anomalies`) and Warehouse Defect line (`defect_records`) must remain separate. | **Never** merge statistics, exports, or database records between the two distinct quality workflows. |
| **Identifier Rules** | Anomaly Numbers must be validated as exactly 11 digits (`YYYYMMDDNNN`) aligned with the selected date. | **Do not** permit non-numeric characters, hyphens, or date-mismatched serial numbers. |
| **Scroll Ownership** | Pages and tabs must maintain exactly one dedicated vertical scroll owner. | **Do not** nest scroll areas inside scroll areas (`QScrollArea` in `QScrollArea`). |

---

## Technical Mapping Reference (CSS / Tailwind / QSS)

| Design Token | Value | Tailwind Class / CSS Variable | PySide6 QSS Equivalent |
| :--- | :--- | :--- | :--- |
| `colors.app-bg` | `#F1F5F9` | `bg-slate-100` / `var(--app-bg)` | `background-color: #F1F5F9;` |
| `colors.surface` | `#FFFFFF` | `bg-white` / `var(--surface)` | `background-color: #FFFFFF;` |
| `colors.surface-alt` | `#F8FAFC` | `bg-slate-50` / `var(--surface-alt)` | `background-color: #F8FAFC;` |
| `colors.text-primary` | `#0F172A` | `text-slate-900` / `var(--text-primary)`| `color: #0F172A;` |
| `colors.text-secondary`| `#334155` | `text-slate-700` / `var(--text-secondary)`| `color: #334155;` |
| `colors.text-muted` | `#64748B` | `text-slate-500` / `var(--text-muted)`| `color: #64748B;` |
| `colors.border` | `#CBD5E1` | `border-slate-300` / `var(--border)` | `border: 1px solid #CBD5E1;` |
| `colors.border-soft` | `#E2E8F0` | `border-slate-200` / `var(--border-soft)`| `border: 1px solid #E2E8F0;` |
| `colors.primary` | `#1E40AF` | `bg-blue-800` / `var(--primary)` | `QPushButton[variant="primary"] { background-color: #1E40AF; }` |
| `colors.primary-hover`| `#1D4ED8` | `hover:bg-blue-700` | `QPushButton[variant="primary"]:hover { background-color: #1D4ED8; }` |
| `colors.focus-ring` | `#3B82F6` | `ring-2 ring-blue-500` | `border: 2px solid #3B82F6;` |
| `rounded.sm` | `3px` | `rounded-[3px]` | `border-radius: 3px;` |
| `rounded.md` | `4px` | `rounded` | `border-radius: 4px;` |
| `rounded.lg` | `6px` | `rounded-md` | `border-radius: 6px;` |
| `spacing.md` | `8px` | `p-2` / `gap-2` | `padding: 8px;` / `spacing: 8px;` |
| `spacing.lg` | `12px` | `p-3` / `gap-3` | `padding: 12px;` / `spacing: 12px;` |
| `spacing.xl` | `16px` | `p-4` / `gap-4` | `padding: 16px;` / `spacing: 16px;` |
