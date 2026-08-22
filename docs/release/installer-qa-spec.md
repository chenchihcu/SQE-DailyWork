# Installer QA Specification — SQE DailyWork

**狀態：** Phase 3（規格 + Inno POC）；**正式 signed installer 屬 Phase 4**  
**現行正式通道：** portable zip `dist/SQE_DailyWork-win64.zip`

## 1. 目標與範圍

定義 Windows 安裝程式（setup）的 QA 契約，與 [src/app_paths.py](src/app_paths.py) frozen 路徑一致：執行檔目錄為 writable root，`data/`、`Outputs/`、`logs/` 與 exe 並存。

**Phase 3 DoD：**

- 本規格文件
- 可選 Inno Setup POC（`installer/sqe_dailywork.iss`）
- **無簽章 `setup.exe` 不視為 production installer**

## 2. 安裝路徑策略

| 模式 | 預設路徑 | 寫入權限 | Phase 3 |
|------|----------|----------|---------|
| Per-user（建議 POC） | `{localappdata}\SQE_DailyWork` | 標準使用者 | POC 預設 |
| Per-machine | `{pf}\SQE DailyWork` | 需 Admin / UAC | 僅文件化；需簽章後評估 |

## 3. 捷徑與解除安裝

- 開始功能表捷徑：指向 `SQE_DailyWork.exe`
- 解除安裝：**預設保留** `{app}\data\`、`{app}\Outputs\`（使用者資料不隨 uninstall 刪除）
- Uninstall 登錄僅移除程式檔；文件須說明手動刪除資料夾時機

## 4. 升級契約

| 情境 | 預期行為 |
|------|----------|
| 同目錄覆蓋升級 | 保留 `data/`、`Outputs/`；新 exe 啟動後 migration 正常 |
| 並存版本 | 不支援為預設；若 IT 需要，須另開目錄並手動遷移 `data/` |
| 追溯 | 比對 `build-info.json` 的 `version`、`git_commit`、`build_timestamp` |

**Phase 3 Wave 2（規劃）：** fixture DB 或備份快照 → 新安裝 exe → migration meta 斷言（disposable 模式）。

## 5. 與 app_paths 對齊驗證清單

- [ ] Frozen：`runtime_root()` = exe 父目錄
- [ ] `SQE_DB_PATH` override 時 `data_dir()` 為 override 父目錄
- [ ] `logs/smoke_exit.ok` 寫入 `{runtime_root}/logs/`
- [ ] `--smoke-exit` 在安裝目錄可完成（見 portable / Inno POC smoke）

## 6. Inno Setup POC

| 項目 | 路徑 |
|------|------|
| 腳本 | `installer/sqe_dailywork.iss` |
| 輸入 | `dist/SQE_DailyWork/` onedir |
| 輸出 | `dist/SQE_DailyWork-setup.exe`（experimental） |
| 建置 | Inno Setup 6 CLI：`iscc installer\sqe_dailywork.iss` |

POC 安裝後執行與 portable smoke 相同之 scratch DB `--smoke-exit`（手動或延伸 `portable_install_smoke.ps1`）。

## 7. MSI / WiX（未實作）

企業 MSI 需求列 Phase 4，與 Authenticode 簽章一併評估。WiX 須定義 Major Upgrade、元件 GUID、與資料目錄保留策略。

## 8. 驗收標準（Phase 3）

- [ ] 本規格覆蓋路徑、升級、解除安裝、資料保留
- [ ] Inno POC 可在 scratch 目錄完成安裝 + exe smoke（可選 CI `continue-on-error`）
- [ ] README / release 註明：正式企業分發仍為 zip，直至 Phase 4 signed installer

## 9. 殘餘風險

| 風險 | 緩解 |
|------|------|
| 無簽章 setup 被 SmartScreen 擋 | Phase 4 簽章；Phase 3 僅內部 POC |
| Program Files 寫入失敗 | POC per-user；文件化 UAC |
| 雙交付物維護 | POC 不取代 zip；單一 PyInstaller 產物餵 Inno |
