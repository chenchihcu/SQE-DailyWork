---
name: sqe-dailywork-ui-ux-flow-optimizer
version: 2.0.0
description: 用於 SQE DailyWork 緊湊度、字體、操作動線最佳化、一鍵流、工具列優化、多級 Context 聯動性、Workflow Shell 骨架穩定、跨 Tab 輸入流、Safe Key Fallback、唯讀視圖與 Qt SizePolicy 規範。Use this skill 進行 UI 佈局緊湊、操作動線簡化或視覺優化。
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
