# 決策記錄：Agent Orchestration Coding Protocol

> 版本：v2026.07.05-02 ｜ 狀態：**EXECUTED / VERIFIED（本 session 落地）**
> 前身：v-01 為「交接給另一個 session」的規格；使用者後改為在本 session 直接執行並升版 v-02。
> 落地後**單一真相來源為實際檔案**（見下），本檔僅保留決策與 RCA，不重複嵌入內容。

## 已落地檔案（SSOT）

- 新增 `docs/harness/agent-orchestration.md` — 協定正本（RACI、任務分級、Evidence Standard、Review Severity、錯誤學習、Routing Table、Boundaries）。
- 新增 `docs/harness/contradiction-log.md` — 跨工具規則衝突落點。
- 編輯 `AGENTS.md` — Knowledge Map 加指標 1 行；§8 Multi-Assistant Coexistence 加 Agent Orchestration 條目。
- 編輯 `scripts/harness_check.ps1` — `$requiredFiles` 註冊 2 新檔；加 9 條 `Require-Text` 斷言（含 AGENTS 指標、RACI/Task Tiering/Evidence Standard/Review Severity/Routing Table/native Windows Qt/contradiction-log 錨點、衝突紀錄格式）。
- 編輯 `docs/harness/README.md` — Sources 加 2 行。

## 三份文件的評估收斂（為什麼是現在這個形狀）

1. **Institution Spec（第一份）**：拆零件、不搬架構；保留 `AGENTS.md`-as-SSOT，用其「薄索引」原則安置本協定為獨立檔＋指標。
2. **Coding Rules（第二份）**：採 RACI 骨架（真實工具、無 Hermes），補上最缺的「跨 agent 分工」層。
3. **Gap Analysis（第三份）**：經自行查證後，9 缺口只吸收約 3 個（重定為 Qt/solo 情境）。

## v-01 → v-02 的實質變更（來自第三份的查證吸收）

- **任務分級 2 級 → 3 級**：加 **L0 直通道**（typo/註解/純文字直接做，不寫 canonical spec）；Standard / Heavy 照舊，Heavy 綁既有 Hard Triggers。
- **新增 Review Severity P0–P3**：讓 review 可決策（P0 擋、P1 修好再收、P2 說明風險、P3 不擋）；驗收需無 P0/P1。
- **新增 Evidence Standard（Qt/桌面版）**：逐修改類型對應有效證據，**明確排除 browser/login/payment**；UI 改需原生 before/after 截圖、bug 需重現+regression、refactor 需行為不變聲明。
- **衝突處理補「任務狀態路由」**：Codex 認規格不可行→回 Claude 改規格；驗證失敗→回 Codex；review 分歧→以 canonical spec + acceptance 為準。（規則衝突仍走 contradiction-log。）

## 經查證後「不採納」的缺口（證據導向，非省事）

- **人工核准 gate（缺口 7）**：已被 `sqe-dailywork-pre-tool-use.ps1`（擋 `--apply` 需 `SQE_DAILYWORK_CONFIRM_APPLY=1`、擋遞迴刪除、擋 `data/*.db`）＋ `.codex/rules`（migration/`--apply` prompt）機器閉合。協定只**引用**，不新建。
- **Spec Versioning YAML（缺口 6）**：solo + TBD + git 已是版本控制，change_log YAML 屬 ceremony。
- **Task Packet YAML（缺口 8）**：與輕量 canonical spec 重疊，不加第二份派工 YAML。
- **Codex 測試矩陣（缺口 3）/ Final Checklist（缺口 9）**：多為 web/E2E 型或與既有完成格式重疊，僅在 Heavy 任務按需使用，不強制。

## 驗證（本 session 實跑）

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/harness_check.ps1
```
輸出：`Harness check passed.`（含 9 條新斷言與 `AGENTS.md` < 32768 bytes 預算）。

## 殘餘風險

- UNKNOWN：各工具能否顯式選 model/effort 未解 → 協定已把相關自動化標 VERIFY，不阻擋落地。
- RACI 與分級屬文字層規則（除已綁 gate/hook 外靠判斷）——solo 刻意取捨，非缺陷。

## Next action

- 依 exec-plan 慣例可將本檔移至 `docs/exec-plans/completed/`（本 session 未移動、未刪除任何檔）。
