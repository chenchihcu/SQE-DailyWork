# Phase 4 — Authenticode Signing (Deferred)

**狀態：** 延後（使用者於 Phase 3 規劃階段選擇「延後簽章」）  
**Phase 3 前置已完成：** `build-info.json` 追溯、portable checklist SmartScreen 說明、spec `codesign_identity` 注入點待實作

## 決策選項（Phase 4 啟動時三選一）

| 選項 | 適用情境 | 前置條件 |
|------|----------|----------|
| Azure Trusted Signing | 無本地 HSM；CI 簽署 | Azure 訂閱、OIDC/federated credential |
| 本機 PFX + signtool | 企業既有 EV/OV 憑證 | 安全存放、CI secret |
| 繼續延後 | 接受 SmartScreen / AV 風險 | portable checklist 企業例外流程 |

## Phase 4 實作範圍（規劃）

1. [scripts/sqe_dailywork.spec](scripts/sqe_dailywork.spec)：`codesign_identity` 由環境變數或 build 參數注入
2. [scripts/build_windows.ps1](scripts/build_windows.ps1)：建置後 `signtool sign`（exe + 未來 setup.exe）
3. 正式 Inno / MSI installer 簽章與企業部署證據（SmartScreen、AV 掃描紀錄）
4. Release 紀錄：簽章後檔案 SHA256 + `build-info.json`

## 不在 Phase 3 修改

- 生產路徑 `codesign_identity=None` 維持至 Phase 4
- 無簽章 `setup.exe` **不得**標為 production installer

## 驗收標準（Phase 4）

- [ ] `SQE_DailyWork.exe` Authenticode 有效
- [ ] installer（若採用）已簽章
- [ ] SmartScreen 回歸證據或企業白名單紀錄
- [ ] CI/release 文件更新簽章步驟與 secret 管理
