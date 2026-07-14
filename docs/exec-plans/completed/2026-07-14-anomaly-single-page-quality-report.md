# 異常單頁表單與品質異常單要求

## Done

- 日期選擇器在 Windows 原生主題下保持可讀。
- 異常新增／編輯／預覽改為單一可捲動頁面與固定 footer。
- `quality_report_required` 由 SQLite、服務、表單、查詢串接到 Excel 明細。
- 聚焦測試、Excel 開檔檢查、原生 Qt 視覺證據與文件同步完成。

## Non-goals

- 不改倉庫 NCR、PDF、統計公式或新增統計工作表。
- 不回填既有異常資料；歷史值維持未設定。

## Verification

- Focused pytest：108 passed。
- Compileall：passed。
- Excel：四張工作表重新開啟並渲染；明細欄位值與樣式通過。
- Native Qt：`form-density` 於 100% / 125% / 150% DPI 通過。
- `scripts/verify.ps1`：執行超過 5 分鐘後由外層逾時終止，未取得失敗測試。
- `scripts/harness_check.ps1`：因任務開始前已修改的 Claude hook/skill 缺少既有治理字串而失敗；未納入本次修改。
