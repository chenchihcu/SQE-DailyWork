# Portable Install QA Checklist — SQE DailyWork

**適用版本：** 1.2.0+  
**交付物：** `dist/SQE_DailyWork-win64.zip`（PyInstaller onedir portable）  
**自動化 gate：** `scripts/portable_install_smoke.ps1`（zip 解壓 → scratch DB → `--smoke-exit`）

## 發佈前自動化（必跑）

- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1`
- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\portable_install_smoke.ps1 -UseExistingDist`
- [ ] 確認 `dist\SQE_DailyWork\build-info.json` 含 `version`、`git_commit`、`build_timestamp`

## 本機手動驗證（建議每次 major release）

### 乾淨解壓與路徑

- [ ] 在非 repo 目錄解壓 zip（例如 `%USERPROFILE%\Downloads`）
- [ ] 路徑含空格（例如 `C:\Apps\SQE DailyWork portable\`）可正常啟動
- [ ] **本機必測：** 使用者目錄含中文路徑時可啟動與寫入 `data\`、`logs\`

### 權限與帳戶

- [ ] 標準使用者（非 Admin）可啟動、建立 scratch `data\sqe_v2.db`
- [ ] 安裝至僅使用者可寫目錄時，`Outputs\` 與 `logs\` 可建立

### 資料遷移（README 契約）

- [ ] 複製既有 `data\` 與 `Outputs\` 至 exe 同層後可開啟舊資料
- [ ] 新安裝不內嵌 production DB；首次啟動建立 disposable/scratch 或空 formal DB

### 防毒與 SmartScreen（未簽章預期行為）

- [ ] 首次執行可能出現 Windows SmartScreen「無法驗證發行者」— **Phase 3 預期行為**（簽章延後 Phase 4）
- [ ] 企業 AV 全碟掃描後首次啟動仍成功（記錄 AV 產品與日期）
- [ ] 記錄是否需 IT 白名單或「仍要執行」

### 證據欄位（填寫於 release 紀錄）

| 欄位 | 值 |
|------|-----|
| 測試日期 | |
| 測試者 | |
| zip 路徑 / git commit | |
| zip SHA256 | |
| build-info.json zip_sha256 | |
| 解壓路徑 | |
| SmartScreen 行為 | |
| AV 產品 | |
| 中文路徑測試 | pass / fail / skip |

## 不在本 checklist 範圍

- Formal `data/sqe_v2.db` migration（需使用者明確授權）
- Visual baseline 像素回歸（見 `scripts/verify.ps1 -Profile Full`）
- 已簽章 installer（Phase 4）
