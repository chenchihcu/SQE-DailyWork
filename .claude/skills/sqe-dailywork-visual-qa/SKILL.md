---
name: sqe-dailywork-visual-qa
version: 2.0.0
description: "SQE DailyWork PySide6 視覺檢查：Windows Qt 截圖、CJK 字體、動態按鈕崩潰與回歸審查。Use when 做 native Windows Qt 視覺 QA 或按鈕崩潰測試。Do NOT use for OS 桌面截圖（改用 capture-desktop-screenshot）、Web Playwright（改用 automate-playwright-browser）或通用 Qt theme（改用 configure-qt-layout-theme）。"
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork Visual QA

用於 PySide6 桌面應用程式之 UI 視覺品質檢驗（佈局、主題、CJK 字體渲染、截圖）與動態按鈕審查。

## 觸發時機
- 完成 UI/UX 變更後的視覺回歸驗證
- 驗證 CJK 繁體中文字元渲染是否異常截斷或亂碼
- 執行自動化按鈕動態點擊與無崩潰健全度測試 (Dynamic Button Audit)

## 參考指引 (Reference Routing)
詳細腳本與驗證清單請依需求查閱：
- **視覺檢驗與自動化測試腳本**：請讀取 `references/visual_qa_checklist.md`
  - 核心包含：離線截圖命令範本、按鈕遞迴點擊測試腳本、字型與色彩對比驗收矩陣。
