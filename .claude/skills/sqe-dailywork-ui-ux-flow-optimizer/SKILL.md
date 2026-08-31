---
name: sqe-dailywork-ui-ux-flow-optimizer
version: 2.0.0
description: "SQE DailyWork PySide6 緊湊度、字體、操作動線、Workflow Shell、跨 Tab 輸入流與 SizePolicy。Use when 修本專案 UI 佈局緊湊、動線或視覺規範。Do NOT use for 通用 Qt theme（改用 configure-qt-layout-theme）或通用動態參數面板（改用 build-qt-parameter-selector）。"
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork UI/UX 佈局與操作動線最佳化技能

本技能規範 SQE DailyWork 桌面應用程式的 UI/UX 空間利用率、排版緊湊度、操作動線流暢性、骨架外框（Workflow Shell）整合性、一鍵流模式與 Qt 佈局規則。

## 觸發時機
- 調整視窗與佈局緊湊度、壓縮空白邊距 (margins/spacing)
- 新增或重構跨 Tab 輸入流、多級上下文聯動選單
- 實作一鍵流（One-Click Flow）操作體驗與快捷工具列
- 修復字體縮放、動態標籤重疊與 Qt SizePolicy 截斷問題

## 參考指引 (Reference Routing)
詳細之設計規範與代碼範例請依需求查閱：
- **詳細排版與空間幾何規範**：請讀取 `references/ui_rules_and_spec.md`
  - 核心包含：4px/8px 緊湊網格、QFormLayout 標籤對齊、跨 Tab 狀態傳遞契約、Safe Key 解析機制與 QSplitter 響應式配置。
