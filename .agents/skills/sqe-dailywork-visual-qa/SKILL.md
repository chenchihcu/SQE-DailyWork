---
name: sqe-dailywork-visual-qa
version: 2.0.0
description: 用於 SQE DailyWork 的 PySide6 視覺檢查與功能按鈕審核。包含 Windows Qt 視覺截圖、CJK 中文字體渲染、動態按鈕崩潰測試與回歸審查。
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
