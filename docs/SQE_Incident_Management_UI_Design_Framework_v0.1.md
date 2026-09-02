# SQE 異常案件管理系統 — UI 設計框架

> **文件用途**:定義 SQE 異常案件管理系統 Web 端的 UI 設計框架(設計原則、資訊架構、通用元件與各頁面規格),作為開發、審查與後續模組擴充的共通基準。
> **適用範圍**:第 4-6 章對應 `sqe-incident-manager` 已實作的 Web 畫面(建立案件、異常案件查詢、案件詳情 7 分頁);第 7 章為 SQE DailyWork 桌面程式的整合映射;第 8 章附欄位對照表與 VERIFY 清單。
> **讀者**:SQE 工程師、Web 前端開發者、UI/UX 審查者與文件維護者。
> **版本**:v0.1 · **日期**:2026-08-18

---

## 目錄

- [第 0 章 寫作規範(House Style)](#第-0-章-寫作規範house-style)
- [第 1 章 設計原則與通用規則](#第-1-章-設計原則與通用規則)
- [第 2 章 資訊架構與導覽](#第-2-章-資訊架構與導覽)
- [第 3 章 通用元件與互動狀態](#第-3-章-通用元件與互動狀態)
- [第 4 章 建立案件](#第-4-章-建立案件)
- [第 5 章 異常案件查詢](#第-5-章-異常案件查詢)
- [第 6 章 案件詳情(7 個分頁)](#第-6-章-案件詳情7-個分頁)
- [第 7 章 SQE DailyWork 整合映射](#第-7-章-sqe-dailywork-整合映射)
- [第 8 章 附錄](#第-8-章-附錄)

## TL;DR 摘要

> 本框架定義 SQE 異常案件管理系統 Web 端的 UI 設計:從開案(第 4 章)到查詢(第 5 章)到案件詳情 7 分頁(第 6 章),以「最低必要輸入、案例優先、Next Action 驅動、證據先於結論」四原則貫穿;欄位與標籤以 `src/lib/labels.ts` 為正本,所有 wireframe 為純 ASCII。第 7 章把 Web 端設計對齊 SQE DailyWork 桌面程式,附 15 條「取其優點」建議;第 8 章收錄 §26 欄位對照表與 15 項 VERIFY,供文件維護者與對應 repo 負責人裁決。

---
## 第 0 章 寫作規範(House Style)

> 本章(第 0 章)定義全文件的寫作規範(術語、欄位表、wireframe 慣例),第 1-8 章一律以此為準。
> 事實來源:架構文件 `docs/SQE_Incident_Management_Web_Architecture_Draft_v0.1.md`(§3 / §10 / §30 / §42)、`Institution/06-ui-ux-universal.md`、`.omo/notepads/ui-design-framework/web-truth.md`、`sqe-incident-manager/src/lib/labels.ts`。

### HS-1 術語規則

1. 第 4-6 章(建立案件、異常案件查詢、案件詳情)的欄位標籤、按鈕文字、狀態文字,一律使用 Web 端 zh-TW 標籤。正本 = `sqe-incident-manager/src/lib/labels.ts`;若 labels.ts 無對應(key 未收錄),以元件實際字串為準。不得自創譯名。
2. 第 7 章(DailyWork 整合映射)須先給「術語對照表」,兩套用語(Web ↔ DailyWork)並陳;第 4-6 章不得混入 DailyWork 用語。
3. severity 值(Low / Medium / High / Critical)不翻譯,原文照寫(labels.ts:6 註明)。
4. timeline eventType 目前無 zh-TW 對照(labels.ts 無 EVENT_TYPE 對應表),文件照實描述「直接顯示原始 enum,如 CASE_CREATED」,不得自行翻譯。
5. 專有名詞採中英對照,首次出現以「中文(English)」呈現,如 案例(Case)、根本原因(Root Cause);後續可省略英文。無慣用中文譯名者保留原文(如 Overdue、Stale)。
6. 案件狀態與動作狀態的「狀態」一詞在條文內以語境區分;需要時以 Case Status / Action Status 標註,避免歧義。

### HS-2 欄位表統一格式

所有欄位表使用同一結構,四欄:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |

- 欄位(中文):照抄 labels.ts 或元件實際字串,不加工。
- 英文 key:以元件 props / DB 欄位名為準;架構 §26 的 snake_case 為主 key,元件 camelCase 於說明欄括註。
- 必填級別:三級固定為 必填 / 選填 / 系統。情境性必填(如「結案時必填」「Not Established 時必填」)在說明欄註明條件。
- 說明:一行內寫用途、顯示規則或驗證規則;不得複製原始碼。

### HS-3 Wireframe 慣例

1. 純 ASCII:只用 `-` `|` `+` `=` 與空格構成框線,不得使用 box-drawing unicode 符號(如 ─ │ ┌ ┐ └ ┘)。
2. 每個 wireframe 開頭標註寬度註記,格式 `(寬度 ~Npx)`,例如 `(寬度 ~1200px)`。
3. 欄位輸入用 `[ ]`(空括號)表示;已填值寫在括號內,如 `[料號 ABC-123]`。
4. 按鈕用 `( )` 表示,如 `(建立案件) (取消)`;主要按鈕在前(左)、次要按鈕在後(右)。
5. 區段標題用 `==` 行包夾,如 `== 案件資訊 ==`。
6. 必填欄位標註 `* 必填`,放在欄位標籤後方。
7. 狀態標註用 `> 說明` 或括註,如 `> 狀態: 處理中`。
8. 長內容省略以 `…` 表示,並註記 tooltip 行為,如 `[異常摘要很長…(tooltip 顯示全文)]`。

示範 wireframe(案例:建立案件,寬度 ~960px):

```
(寬度 ~960px)
====================================================
== 建立異常案件 ==
* 必填 供應商:   [選擇供應商……]
* 必填 案件類型: [選擇案件類型……]
* 必填 異常來源: [選擇異常來源……]
* 必填 發現日期: [2026/08/18]
* 必填 異常摘要: [輸入異常摘要……]

== 下一步處置 ==
* 必填 處置內容: [輸入處置內容……]
* 必填 到期日:   [2026/08/25]

== 詳細資料(選填) ==
料號:      [          ]    品名:      [          ]
不良模式:  [          ]    嚴重程度:  [未指定 v]

(建立案件) (取消)
> 送出成功後轉跳至 /cases/{id}
```

---

## 第 1 章 設計原則與通用規則

> 來源:架構文件 §3(設計原則)、§10(Overdue 邏輯)、§30(UI/UX 需求)、Institution 06(通用規則)。本章濃縮為可執行原則,不照抄原文。

### 1.1 最低必要輸入(Minimum Necessary Input)

開案只要求最低必要資料,避免大量必填欄位造成亂填、資料品質下降與使用阻力(架構 §3.1)。設計取捨:能選填就不必填;能自動計算就不要求手動輸入;詳細資料留給後續 tab 補齊。

### 1.2 Case First, Documents Second(案例優先,文件其次)

案例(Case)是核心資料主體;8D、FA、照片、報告、規格等文件均掛在案例之下(架構 §3.2)。因此建立案件只收案件本體欄位,文件一律在案件詳情的對應 tab(附件 / Supplier 8D)中管理,不另立獨立文件流程。

### 1.3 Next Action 驅動日常(Next Action Drives Daily Work)

使用者每日最重要的操作是知道:現在要做什麼、誰負責、什麼時候到期、是否逾期(架構 §3.3)。採「Next Action + Due Date」作為案件日常追蹤核心;案件清單與詳情頁第一視口必須呈現:狀態、下一步處置、到期日、Overdue、供應商、異常摘要(架構 §30 Case Detail)。

### 1.4 Evidence Before Conclusion(先有證據再下結論)

異常分析允許記錄 FACT / INFERENCE / ASSUMPTION / UNKNOWN 四類證據、根本原因(Root Cause)、矯正措施(Corrective Action)與有效性驗證,但不要求所有欄位強制填寫(架構 §3.4)。UI 不得以「填完即證明」的互動誤導使用者;結論狀態(badge)與佐證欄位分開呈現。

### 1.5 Status 與 Overdue 分離(Separate Status From Due Date)

Case Status 表示案件目前階段;Overdue 由系統依據有效 Next Action 的 Due Date 自動判定,不允許使用者手動設定「Overdue」(架構 §3.5、§10)。判定規則(架構 §10):

```
Case is not Closed / Cancelled
AND
Current Next Action exists
AND
Due Date < current date/time
AND
Action Status = Open
=
Overdue
```

Dashboard 與案件清單必須使用同一判定邏輯;元件端以 `caseDetail.overdue` 布林值渲染 OverdueBadge(見第 3 章 3.1)。

### 1.6 CJK 與可掃描性

- 長中文在表格 / 標籤 / 卡片一律省略截斷(elide)並以 tooltip 顯示全文,不靜默截斷(Institution 06 §6)。
- 密集桌面頁面保持可掃描:直接標籤、穩定表格欄寬、可見動作列;不用 card-in-card 包裝層(Institution 06 §3)。
- 高資訊密度但不雜亂(架構 §30 General)。
- CJK 字重優先用 400 與 700,避免 500 / 600(Windows 渲染不一致)。

### 1.7 四態完整(Empty / Loading / Error / Success)

空資料、載入中、錯誤、成功四種狀態都要有明確畫面,不留空白(Institution 06 §2)。每個資料區塊都要定義四態行為;詳細準則見第 3 章 3.5。

### 1.8 Token 語意化

顏色、間距、字級、圓角、控件尺寸集中為共用 token / 常數,語意命名(如 `TEXT_DISABLED`、`SURFACE_ACTIVE`),不用外觀命名(如 `GREY_DARK`)。`DISABLED`(不可互動)與 `MUTED`(次要但可讀)分開,不互換。色彩用於傳達意義,不只裝飾;狀態不可只靠顏色區分,配合圖示或文字(Institution 06 §3、§5)。

---

## 第 2 章 資訊架構與導覽

### 2.1 Web 側欄(資訊架構主幹)

以實際元件 `sqe-incident-manager/src/components/layout/sidebar.tsx` 為準,扁平 5 項導覽:

| 側欄標籤 | 路徑 | 用途 |
| --- | --- | --- |
| 儀表板 | /dashboard | 總覽與追蹤(本文件不以主章節展開) |
| 異常案件 | /cases | 案件查詢與篩選(第 5 章) |
| 建立案件 | /cases/new | 開案(第 4 章) |
| 供應商 | /suppliers | 供應商清單(不以主章節展開) |
| 搜尋 | /search | 全文搜尋(第 5 章提及) |

互動狀態:目前路徑項目以 `bg-sidebar-accent` 標示且帶 `aria-current="page"`,hover 用 `bg-sidebar-muted`(sidebar.tsx:45-51)。

### 2.2 每日工作流(IA 對應的使用者路徑)

1. 上班先看儀表板:KPI(開放案件 / Overdue 案件 / 待供應商回覆)與營運佇列。
2. 進「異常案件」依篩選條件縮小範圍,排序後逐案處理。
3. 開新案走「建立案件」,只填最低必要輸入(第 1 章 1.1)。
4. 案件詳情以第一視口讀取狀態 / 下一步處置 / 到期日 / Overdue(第 6 章),再依 tab 補齊分析、8D、CA、附件。

### 2.3 與 DailyWork Sidebar 的對照脈絡

SQE DailyWork 桌面程式採 workflow-first 四群組側欄:供應商事件、倉庫不合格品、資料庫設定、系統（來源 `src/ui/sidebar_nav.py` `_NAV_GROUPS`）。供應商事件側欄為 `新增異常` / `事件查詢` / `作業佇列` / `異常事件統計`；逾期案件、根因待查、處置項目、案件總覽為 **作業佇列** 頁內 chips，非獨立側欄列。首頁 hub 已退休。Web 端為扁平 5 項,兩者資訊架構策略不同:DailyWork 以作業類型分群組並掛 badge 計數,Web 以功能頁分項。本文件第 7 章提供完整映射與術語對照,本章僅確立脈絡。

---

## 第 3 章 通用元件與互動狀態

> 事實來源:`.omo/notepads/ui-design-framework/web-truth.md` §4.4(badge 清單)與 §②(欄位盤點);文字以 `src/lib/labels.ts` 為正本。元件來源檔:`sqe-incident-manager/src/components/status-badges.tsx`。

### 3.1 Badge 元件

九個 badge 元件如下;每個 badge 的顯示文字、樣式語意與使用位置皆以 web-truth.md §4.4 為準。

| Badge | 顯示文字(來源) | 樣式語意(狀態 → variant) | 使用位置 |
| --- | --- | --- | --- |
| CaseStatusBadge | caseStatusLabel(labels.ts:24-31) | Open=default;Pending Supplier=secondary;Investigating=outline;Pending Verification=amber;Closed=success;Cancelled=muted | 查詢表格、詳情頁 header、overview |
| ActionStatusBadge | actionStatusLabel(labels.ts:33-37) | Open=default;Completed=success;Cancelled=muted | overview 目前處置 |
| RootCauseStatusBadge | rootCauseStatusLabel(labels.ts:39-45) | Not Started=muted;Under Investigation=secondary;Proposed=amber;Verified=success;Not Established=outline | overview 品質結論、investigation |
| CaStatusBadge | caStatusLabel(labels.ts:47-55) | Planned=secondary;In Progress=default;Implemented=outline;Verification Pending=amber;Effective=success;Ineffective=destructive;Cancelled=muted | overview 品質結論、CA 卡片 |
| VerificationResultBadge | verificationStatusLabel(labels.ts:57-65) | Pending=secondary;Effective=success;Ineffective=destructive;Inconclusive=amber | overview 品質結論、VerificationPanel |
| EightDReviewStatusBadge | eightDReviewStatusLabel(labels.ts:67-74) | Accepted=success;Return for Revision=amber;Need More Evidence=destructive | Supplier 8D 審查紀錄 |
| OverdueBadge | 固定文字「逾期」 | destructive 紅(red-100 / red-800) | 查詢表格逾期欄、overview 目前處置、詳情頁 header |
| StaleBadge | `{days} 天未更新`(days = daysAging(updatedAt)) | amber | 查詢表格案件天數欄、overview 案件天數 |
| SeverityBadge | value 原文字(Low / Medium / High / Critical,不翻譯) | Low=muted;Medium=secondary;High=amber;Critical=destructive | 詳情頁 header、建立表單 |

補充規則:

- 逾期判定:OverdueBadge 依 §1.5 規則,元件端用 `caseDetail.overdue` 布林。
- Stale 門檻:`STALE_THRESHOLD_DAYS = 14`(`src/lib/rules/aging.ts:11`);`daysAging(updatedAt)` 為 null 或 < 14 天不渲染;天數以整日計算並 clamp 0(aging.ts:4-8)。
- timeline eventType 不經 badge 翻譯,直接顯示原始 enum(web-truth.md §2.2 VERIFY)。

### 3.2 表格慣例

- 長中文省略截斷(elide)並以 tooltip 顯示全文,不靜默截斷;適用於 異常摘要、料號、不良模式、下一步處置、變更前/後 等欄(web-truth.md ② 各處 truncate + tooltip)。
- 日期格式統一 `YYYY/MM/DD`(`src/lib/format.ts:1` formatDate)。
- 天數計算:案件天數 = daysAging(updatedAt),顯示 `{aging} 天`;≥ 14 天未更新附 StaleBadge(web-truth.md §4.3、§4.4)。
- 無值顯示「—」(em dash 字元),除欄位本身有明確佔位語意。
- 案件編號為連結,指向 `/cases/{id}`;表格列含分頁列「第 X–Y 筆,共 N 筆」與上一頁 / 下一頁。

### 3.3 表單慣例

- 必填欄位用統一紅色 `*` 標記,不混用多種標法(Institution 06 §2)。
- 驗證在欄位層級即時呈現(錯誤邊框 / inline 提示),不只送出時彈窗;錯誤訊息說明「如何修正」。
- 送出中狀態回饋(如按鈕改為「建立中…」),避免介面在無提示下凍結。
- 表單有未儲存變更時,關閉 / 離開前提示(dirty tracking)。
- 送出前整體檢查:非 HTML required 的欄位以送出前邏輯把關(如建立案件要求 供應商、案件類型、異常來源 三者,new-case-form.tsx:120-134)。

### 3.4 對話框慣例

- 主要按鈕順序固定:確認 / 儲存在左、取消在右(對齊 Windows 原生與 Institution 06 §2)。
- 破壞性動作(刪除附件、取消處置、結案)未選取對象前維持 disabled,並先確認再執行。
- 避免不必要的對話框串連(modal chains);能 inline 就不開 dialog(架構 §30 General)。
- 對話框內容長度需含捲動 / 溢出提示,不隱藏捲軸。

### 3.5 四態準則(Empty / Loading / Error / Success)

| 狀態 | 實作準則 |
| --- | --- |
| 空狀態(empty) | 每區塊定義明確空文案與建議動作;範例:「尚無異常案件。建立您的第一個案件開始追蹤。」「尚無待處置動作。」「尚未上傳附件。」(web-truth.md ③ / ② 各 tab) |
| 載入中(loading) | 資料區塊在載入完成前顯示明確 loading 指示,不留空白也不顯示假資料 |
| 錯誤(error) | 錯誤訊息附「如何修正」;表單送出失敗用 Alert 呈現(如「無法建立案件」),不靜默失敗 |
| 成功(success) | 成功後有明確回饋或轉跳(建立案件送出後轉跳 /cases/{id});狀態更新後 badge 立即反映 |

---

## 第 4 章 建立案件

> 事實來源:架構文件 `docs/SQE_Incident_Management_Web_Architecture_Draft_v0.1.md` §6.3(建立案件規格)與 §26(欄位清單)、`sqe-incident-manager/src/components/cases/new-case-form.tsx`、`src/app/cases/new/page.tsx`、`src/lib/labels.ts`、`.omo/notepads/ui-design-framework/web-truth.md` §③。
> 本章欄位標籤、區段標題、按鈕文字一律照抄元件實際字串(HS-1);元件 = 權威,架構 §26 僅作交叉引用。

### 4.1 頁面定位

建立案件位於側欄「建立案件」,路徑 `/cases/new`(第 2 章 2.1)。頁面標題「建立異常案件」,副標題「以最低必要資訊建立新的異常案件。」(`new/page.tsx:25,27`),呼應第 1 章 1.1 最低必要輸入(Minimum Necessary Input)原則。

頁面為 Server Component(`new/page.tsx:13` `force-dynamic`),建立案件前先查詢供應商清單;表單本體 `NewCaseForm` 為 Client Component(`"use client"`,new-case-form.tsx:1)。供應商清單為空時,整頁不渲染表單,改顯示「尚無供應商」guard 卡(見 4.4.1)。

### 4.2 Wireframe(寬度 ~960px)

依元件實際結構繪製:必填資訊 5 欄、下一步處置 2 欄、選填資訊 13 欄。必填區段於 `lg` 斷點為 3 欄 grid、`sm` 為 2 欄(供應商／案件類型／異常來源／發現日期 4 項在同一 grid 內換行);異常摘要、處置內容、不良描述為整行寬。

```
(寬度 ~960px)
====================================================================
== 建立異常案件 ==
> 以最低必要資訊建立新的異常案件。

== 必填資訊 ==
* 必填 供應商:   [請選擇供應商 v]           * 必填 案件類型: [請選擇案件類型 v]
* 必填 異常來源: [請選擇異常來源 v]           * 必填 發現日期: [YYYY/MM/DD]
* 必填 異常摘要: [簡述問題……]

== 下一步處置 ==
* 必填 處置內容: [接下來要做什麼,例如向供應商要求 8D 報告…(rows=2)]
* 必填 到期日:   [YYYY/MM/DD]

== 選填資訊 ==
料號:        [          ]   品名:        [          ]
批號 Lot No.:[          ]   PO:          [          ]
工單 WO:     [          ]   產品／機種:  [          ]
不良模式:    [          ]   嚴重程度:    [未指定 v]
發現位置:    [          ]   收料數量:    [          ]
檢驗數量:    [          ]   不良數量:    [          ]
不良描述:    [不良情形的詳細描述……(rows=3)]

(建立案件) (取消)
> 送出中:按鈕停用並顯示「建立中…」。
> 送出成功:轉跳至新案件詳情頁 /cases/{id}(元件實際行為,見 4.4.5)。
> 送出失敗:頁內顯示錯誤 Alert「無法建立案件」。
```

必填欄位以紅色 `* 必填` 統一標記(Institution 06 §2、第 3 章 3.3);主要按鈕「建立案件」在左、次要按鈕「取消」在右(HS-3.4)。

### 4.3 欄位表

四欄格式(HS-2)。英文 key 以元件 props 名為準,架構 §26 的 snake_case 於 key 括註;來源行號為 `new-case-form.tsx`。

#### 4.3.1 必填資訊(區段標題 :118)

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 供應商 | supplierId(`supplier_id`) | 必填 | Select,placeholder「請選擇供應商」;選項顯示 `{code} — {name}`(:129);送出前邏輯檢查,三者缺一顯示「請選擇供應商、案件類型與異常來源。」(:76-81) |
| 案件類型 | caseType(`case_type`) | 必填 | Select,placeholder「請選擇案件類型」;選項以 caseTypeLabel 顯示:供應商品質異常／進料 NCR／供應商稽核缺失(labels.ts:76-80);送出前邏輯檢查同上 |
| 異常來源 | source(`source`) | 必填 | Select,placeholder「請選擇異常來源」;選項以 caseSourceLabel 顯示:供應商稽核／進料／倉庫／IQC(labels.ts:82-87);送出前邏輯檢查同上 |
| 發現日期 | detectedAt(`detected_at`) | 必填 | HTML required,`type="date"`(:168-176) |
| 異常摘要 | title(`title`) | 必填 | HTML required,placeholder「簡述問題」;整行寬(:178-186) |

#### 4.3.2 下一步處置(區段標題 :190)

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 處置內容 | nextActionDescription(架構 `case_action.description`) | 必填 | Textarea rows=2,HTML required,placeholder「接下來要做什麼,例如向供應商要求 8D 報告」(:192-199) |
| 到期日 | nextActionDueDate(架構 `case_action.due_date`) | 必填 | HTML required,`type="date"`(:203-209) |

送出時此二欄合併為 `nextAction` 物件存入案件(架構 §26.4 CASE ACTION);對應第 1 章 1.3 Next Action 驅動日常原則。

#### 4.3.3 選填資訊(區段標題 :215)

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 料號 | partNumber(`part_number`) | 選填 | 文字輸入(:218-219) |
| 品名 | partName(`part_name`) | 選填 | 文字輸入(:222-223) |
| 批號 Lot No. | lotNo(`lot_no`) | 選填 | 文字輸入(:226-227) |
| PO | poNo(`po_no`) | 選填 | 文字輸入(:230-231) |
| 工單 WO | woNo(`wo_no`) | 選填 | 文字輸入(:234-235) |
| 產品／機種 | productModel(`product_model`) | 選填 | 文字輸入(:238-239) |
| 不良模式 | failureMode(`failure_mode`) | 選填 | 文字輸入(:242-243) |
| 嚴重程度 | severity(`severity`) | 選填 | Select,選項:未指定／Low／Medium／High／Critical(:246-262);severity 值不翻譯(labels.ts:6,HS-1.3);預設「未指定」 |
| 發現位置 | detectionLocation(`detection_location`) | 選填 | 文字輸入(:265-266) |
| 收料數量 | qtyReceived(`qty_received`) | 選填 | `type="number"`,min=0,step=1(:269-277) |
| 檢驗數量 | qtyInspected(`qty_inspected`) | 選填 | 同上(:279-287) |
| 不良數量 | qtyNg(`qty_ng`) | 選填 | 同上(:289-297) |
| 不良描述 | defectDescription(`defect_description`) | 選填 | Textarea rows=3,placeholder「不良情形的詳細描述」;整行寬(:300-306) |

#### 4.3.4 系統產生欄位(非表單欄位)

以下欄位由系統產生,不在建立表單收集(架構 §6.3 System Generated;§26 均標 ✓):

- 案件編號 `caseNumber`:建立時由系統產生,顯示格式可設定(§26:1035,架構 §6.3「Case ID 顯示格式應可設定」)。
- 建立時間 `openedAt`、最後更新 `updatedAt`、建立者／更新者 `createdBy`／`updatedBy`(§26:1082,1087-1088)。
- 狀態 `status`:系統於建立時設定,不需使用者選擇(§26:1080)。
- 逾期旗標 `overdue`:計算值,依第 1 章 1.5 規則自動判定,不可手動設定(§26:1090)。

### 4.4 互動狀態

#### 4.4.1 供應商空白 guard

供應商清單為空時(`suppliers.length === 0`),整頁以卡片取代表單(`new/page.tsx:31-44`):

```
(寬度 ~960px)
== 建立異常案件 ==
> 以最低必要資訊建立新的異常案件。

[ 尚無供應商 ]
案件需要指定供應商。請先建立供應商再建立案件。
(前往供應商)
```

「前往供應商」按鈕連結 `/suppliers`。原因:案件必須指定供應商(架構 §6.3 Required),無供應商即無開案對象;此為第 1 章 1.7 四態中空狀態(empty)的實作,空狀態附明確建議動作。

#### 4.4.2 送出前邏輯驗證

供應商、案件類型、異常來源三個 Select 使用 Radix Select,無隱藏 form input,瀏覽器原生 required 無法覆蓋,故以送出前邏輯把關(new-case-form.tsx:73-81):三者缺一,回傳錯誤「請選擇供應商、案件類型與異常來源。」,頁內以 destructive Alert「無法建立案件」呈現(:310-315)。錯誤訊息說明「如何修正」(指出缺哪些欄位),符合第 3 章 3.3 與 Institution 06 §2。

#### 4.4.3 HTML required

發現日期、異常摘要、處置內容、到期日 四欄標 `required`,由瀏覽器原生驗證把關,缺值時不觸發送出。

#### 4.4.4 送出中

送出按鈕 `disabled={pending}`,文字切換「建立中…」(未送出時為「建立案件」),避免重複送出,符合第 3 章 3.3 送出中狀態回饋。取消按鈕為 outline 樣式,連結 `/cases`(案件清單頁),不做送出驗證。

#### 4.4.5 成功與失敗

- 成功:建立後 `router.push('/cases/{id}')`,轉跳至新建立案件的詳情頁(:108),使用者可直接接續處理。
- 失敗:destructive Alert「無法建立案件」+ 錯誤說明;表單欄位值保留(React state),可修正後重送,不靜默失敗。

> 註記(轉跳目標,已統一):以元件實際行為為準,送出成功後轉跳至 `/cases/{id}`(new-case-form.tsx:108)。早期草稿(web-truth.md §③、HS-3 示範)的「/cases」描述於本文件不再採用,統一為 `/cases/{id}`。

### 4.5 與架構 §6.3 對照

架構 §6.3 開案規格 vs 本 UI 實作對照;判別基準:架構 §26「已實作 ✓」旗標 + 元件實際欄位。未實作者標「規劃中/未實作」,不列入 4.3 欄位表。

| §6.3 項目 | UI 落點 | 狀態 |
| --- | --- | --- |
| Case Type | 必填資訊.案件類型 | 已實作 |
| Source | 必填資訊.異常來源 | 已實作 |
| Supplier | 必填資訊.供應商 | 已實作(含空白 guard) |
| Problem Summary / Title | 必填資訊.異常摘要 | 已實作 |
| Detected Date | 必填資訊.發現日期 | 已實作 |
| SQE Owner | 建立表單未收集 | 與 §6.3 Required 差異:`sqe_owner_id` 於 §26:1079 標 ✓,但僅落點於案件詳情(SQE 負責人)、詳情頁 header 與篩選器,建立流程無此欄;建立時推測以目前使用者為預設 |
| Next Action | 下一步處置.處置內容 | 已實作 |
| Due Date | 下一步處置.到期日 | 已實作 |
| Part Number / Part Name / Lot No. / PO / WO / Product / Model / Failure Mode / Defect Description / Qty Received / Qty Inspected / Qty NG / Severity / Detection Location | 選填資訊 13 欄 | 全部已實作(見 4.3.3) |
| Defect Rate | 無對應表單欄位 | 計算值(§26:1060,依 qty_ng／分母計算),非建立表單收集;分母 `defect_rate_denominator`(§26:1061)未實作,規劃中 |
| Initial Attachment | 無對應表單欄位 | 規劃中:建立流程未提供附件欄,附件於案件詳情「附件」tab 管理(第 6 章) |
| source_ref_no(來源單據號碼) | 無對應表單欄位 | 規劃中/未實作(§26:1077 無 ✓) |
| priority(優先級) | 無對應表單欄位 | 規劃中/未實作(§26:1072 無 ✓;與 severity 並存,severity 為品質影響程度) |
| supplier_plant(供應商廠區) | 無對應表單欄位 | 規劃中/未實作(§26:1048 無 ✓) |
| manufacturing_date(製造日期) | 無對應表單欄位 | 規劃中/未實作(§26:1050 無 ✓) |
| date_code | 無對應表單欄位 | 規劃中/未實作(§26:1052 無 ✓) |
| inspection_standard(檢驗標準) | 無對應表單欄位 | 規劃中/未實作(§26:1054 無 ✓) |
| containment_action(立即圍堵措施) | 無對應表單欄位 | 規劃中/未實作(§26:1068 無 ✓) |
| Unique Case ID / Created At / Updated At / Created By / Current Status / Overdue Flag | 系統產生,非表單欄位 | 已實作(見 4.3.4) |

#### VERIFY 註記

> ⚠️ VERIFY(severity 選項衝突):架構 §26:1075 說明寫「品質影響程度(Critical/Major/Minor)」,元件選項為 **Low / Medium / High / Critical**(new-case-form.tsx:34;SeverityBadge 樣式表 status-badges.tsx:249-254 同)。以元件為準,severity 值不翻譯(labels.ts:6);架構 §26 說明需更新。
>
> 註記(轉跳目標,已統一):見 4.4.5;以元件行為 `/cases/{id}` 為準,不再採用「/cases」描述。

## 第 5 章 異常案件查詢

> 事實來源:`.omo/notepads/ui-design-framework/web-truth.md` §④(查詢頁);元件 `sqe-incident-manager/src/app/cases/page.tsx` 與 `src/components/cases/case-filter-bar.tsx`;架構文件 `docs/SQE_Incident_Management_Web_Architecture_Draft_v0.1.md` §6.2(查詢規格)、§10(Overdue 邏輯)、§23(Manager View)。
> 本章對應 IA 側欄「異常案件(/cases)」,是每日追蹤的主要入口(第 2 章 2.2 工作流第 2 步)。

### 5.1 頁面總覽

查詢頁路由為 `/cases`,頁面頂部提供:

- 標題「異常案件」與描述「管理與追蹤所有回報的異常案件及其狀態。」(cases/page.tsx:147-150)。
- 右上角「建立案件」按鈕,指向 `/cases/new`(cases/page.tsx:152-157)。

查詢頁為 Server Component(`force-dynamic`,cases/page.tsx:24),篩選與排序狀態以 URL search params 為唯一真相來源(Single Source of Truth):表單初始值由 URL 參數還原,套用後以 URL 重建連結,因此重整 / 分享連結即可完整還原目前查詢條件。以下 Wireframe 先給版面全貌,再逐項展開 12 個篩選參數、14 欄表格、排序、badge 與四態行為。

### 5.2 Wireframe(寬度 ~1280px)

依 House Style HS-3 慣例:欄位輸入以 `[ ]`、按鈕以 `( )`、區段標題以 `==` 包夾、長內容以 `…` 省略並註記 tooltip。

```
(寬度 ~1280px)
================================================================================
== 異常案件                                                  (＋ 建立案件)    ==
== 管理與追蹤所有回報的異常案件及其狀態。                                      ==
================================================================================

+------------------------------------------------------------------------------+
| 關鍵字:     [案件編號、供應商、料號、不良模式或關鍵字…]                                             |
| 案件狀態:   [全部狀態 v]   供應商: [全部供應商 v]  案件類型: [全部案件類型 v]                          |
| 異常來源:   [全部來源 v]   SQE 負責人: [全部負責人 v]  料號: [料號…]                             |
| 不良模式:   [不良模式…]   排序方式: [最後更新 v]                                             |
| 發現日期（起）: [        ]  發現日期（迄）: [        ]  [x] 僅顯示逾期案件                        |
| (套用篩選) (清除)                                                                  |
+------------------------------------------------------------------------------+

+------------------------------------------------------------------------------+
| 案件編號 | 異常摘要 | 供應商 | 案件類型 | 異常來源 | 料號 | 不良模式 | 狀態                             |
| 下一步處置 | 到期日 | 逾期 | 案件天數 | 發現日期 | 最後更新                                        |
+------------------------------------------------------------------------------+
| CASE-0001 | 進料檢驗發現尺寸超差… | ACME 精密 | 進料 NCR | 進料 | 77123-A |                  |
| 尺寸 | (處理中) | 通知供應商重工… | 2026/08/25 | (逾期) | 5 天 | 2026/08/18                 |
| 2026/08/18 |                                                                 |
| CASE-0002 | 供應商稽核缺失-文件… | BETA 科技 | 供應商稽核缺失 | 供應商稽核 |                        |
| … | … | (調查中) | 補件待回覆… | 2026/09/01 | — | 3 天 | 2026/08/15 |                 |
| 2026/08/18 |                                                                 |
+------------------------------------------------------------------------------+
| 顯示第 1–20 筆,共 87 筆          (上一頁)  第 1 頁 / 共 5 頁  (下一頁)                       |
+------------------------------------------------------------------------------+

> 表格列高依內容自動調整;異常摘要、料號、不良模式、下一步處置 省略截斷以 … 表示,懸停以 tooltip 顯示全文。
> 狀態欄為 CaseStatusBadge;逾期欄為 OverdueBadge「逾期」或 —;案件天數 ≥ 14 天未更新時附 StaleBadge「N 天未更新」。
> 無篩選且無案件:顯示「尚無異常案件。建立您的第一個案件開始追蹤。」與 (建立案件) 鈕。
> 有篩選且無結果:顯示「找不到符合條件的案件,請調整或清除上方篩選條件。」
```

版面組成:篩選列(關鍵字、6 個下拉、2 個文字輸入、2 個日期、逾期 checkbox、排序)+ 動作列(套用篩選 / 清除)+ 14 欄表格 + 分頁列。表格容器以 Card 呈現(表格與篩選列各一 Card,cases/page.tsx:160-186、188-306)。

### 5.3 篩選參數(12 個 FILTER_KEYS)

篩選列共 12 個參數,以 `cases/page.tsx:27-40` 的 `FILTER_KEYS` 為準。篩選 UI 標籤照 `case-filter-bar.tsx` 實際字串;URL param 值維持英文,不翻譯。未設定即「全部」。

| key | 篩選 UI 標籤(元件字串) | 型別與值域 | URL param 語意 |
| --- | --- | --- | --- |
| q | 關鍵字(placeholder「案件編號、供應商、料號、不良模式或關鍵字…」) | string,自由文字;trim 後非空才生效 | 依搜尋範圍比對(案件編號 / 供應商 / 料號 / 不良模式 / 關鍵字) |
| status | 案件狀態(placeholder「全部狀態」) | enum,限 CASE_STATUSES(Open / Pending Supplier / Investigating / Pending Verification / Closed / Cancelled);值域外忽略 | 依案件狀態(Case Status)篩選 |
| supplierId | 供應商(placeholder「全部供應商」;選項格式 `{code} — {name}`) | string,供應商 ID;值域外忽略 | 依供應商篩選 |
| caseType | 案件類型(placeholder「全部案件類型」) | enum,限 CASE_TYPES(Supplier Quality Issue / Incoming Material NCR / Supplier Audit Finding);值域外忽略 | 依案件類型篩選 |
| source | 異常來源(placeholder「全部來源」) | enum,限 CASE_SOURCES(Supplier Audit / Incoming Material / Warehouse / IQC);值域外忽略 | 依異常來源篩選 |
| ownerId | SQE 負責人(placeholder「全部負責人」) | string,使用者 ID;MVP 為單一使用者 | 依 SQE 負責人篩選 |
| partNumber | 料號(placeholder「料號…」) | string,自由文字;trim;部分符合 | 依料號篩選 |
| failureMode | 不良模式(placeholder「不良模式…」) | string,自由文字;trim;部分符合 | 依不良模式篩選 |
| overdueOnly | 僅顯示逾期案件(checkbox) | 僅接受 `"1"` 或 `"true"`;其餘值視為未設定 | 僅顯示逾期案件(Overdue 依 §1.5 / 架構 §10 自動判定,不允許手動設定) |
| dateFrom | 發現日期（起） | `YYYY-MM-DD`(正則驗證);解析為當日 `00:00:00`;格式不符忽略 | 發現日期範圍下限(含) |
| dateTo | 發現日期（迄） | `YYYY-MM-DD`(正則驗證);解析為當日 `23:59:59.999`(end of day);格式不符忽略 | 發現日期範圍上限(含) |
| sort | 排序方式(placeholder「最後更新」) | enum,限 SORT_OPTIONS(見 5.5);值域外忽略 | 排序方式;未設定 = 最後更新 |

補充規則:

- 解析容錯:值域外的參數值(未知 status、格式不符的日期等)由 `parseFilters` 忽略,不報錯、不中斷頁面(cases/page.tsx:59-98)。
- URL 重建:套用篩選後依 `FILTER_KEYS` 順序重建 `/cases?{params}`(`buildPageHref`,cases/page.tsx:107-119);無任何參數時回歸 `/cases`;分頁 `page` 參數附加於後。
- 互動:「套用篩選」送出即 `router.push`;「清除」清空表單並回 `/cases`(case-filter-bar.tsx:103-123)。
- 側欄另有獨立全文搜尋頁「搜尋(/search)」(第 2 章 2.1);本頁 `q` 為案件清單範圍內的結構化搜尋,兩者定位不同。

### 5.4 表格欄位與分頁(14 欄)

表頭依 `cases/page.tsx:213-227`;欄位標籤照抄元件字串。查詢表格為顯示用途,無編輯動作。

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 案件編號 | caseNumber | —(顯示) | 連結指向 `/cases/{id}`(font-medium、hover underline) |
| 異常摘要 | title | —(顯示) | `max-w-64 truncate`;tooltip 顯示全文 |
| 供應商 | supplier.name | —(顯示) | 供應商名稱 |
| 案件類型 | caseType | —(顯示) | caseTypeLabel 轉 zh-TW(供應商品質異常 / 進料 NCR / 供應商稽核缺失) |
| 異常來源 | source | —(顯示) | caseSourceLabel 轉 zh-TW(供應商稽核 / 進料 / 倉庫 / IQC) |
| 料號 | partNumber | —(顯示) | truncate;無值顯示「—」 |
| 不良模式 | failureMode | —(顯示) | truncate;無值顯示「—」 |
| 狀態 | status | —(顯示) | CaseStatusBadge(見 5.6) |
| 下一步處置 | currentAction.description | —(顯示) | truncate;無進行中處置顯示「—」 |
| 到期日 | currentAction.dueDate | —(顯示) | formatDate(YYYY/MM/DD) |
| 逾期 | overdue | —(顯示) | OverdueBadge「逾期」或「—」;依 §1.5 自動判定 |
| 案件天數 | aging(updatedAt) | —(顯示) | 右對齊;`{aging} 天`;daysAging(updatedAt) ≥ 14 附 StaleBadge |
| 發現日期 | detectedAt | —(顯示) | formatDate |
| 最後更新 | updatedAt | —(顯示) | formatDate |

分頁列位於表格下方(cases/page.tsx:275-302):

- 左側:顯示第 {rowStart}–{rowEnd} 筆,共 {total} 筆(total = 0 時 rowStart = 0)。
- 右側:「上一頁」/「下一頁」按鈕(邊界時 disabled)+ 第 {page} 頁 / 共 {totalPages} 頁。
- 分頁為連結,經 `buildPageHref` 保留目前篩選參數;`page` 為正整數,小於 1 視為 1(cases/page.tsx:129-131)。

### 5.5 排序選項(SORT_OPTIONS 4 個)

`SORT_OPTIONS = ["caseNumber", "detectedAt", "status", "dueDate"]`(cases/page.tsx:26);zh-TW 標籤照 `case-filter-bar.tsx:25-30`。

| value | zh-TW 標籤 | 排序行為 |
| --- | --- | --- |
| caseNumber | 案件編號（A–Z） | 依案件編號升序 |
| detectedAt | 發現日期（最新優先） | 依發現日期降序(最新在前) |
| status | 狀態（A–Z） | 依案件狀態字串升序 |
| dueDate | 到期日（最早優先） | DB 先以最後更新降序回傳,JS 端再依到期日升序重排;無到期日者排最後 |

補充規則:

- 預設:未設定 `sort` 即「最後更新」(case-filter-bar.tsx:268、271 的 placeholder),依最後更新時間降序。
- 空篩選判定排除 `sort`:`hasActiveFilters` 不將排序視為「有篩選」(cases/page.tsx:100-104),因此只變更排序不會誤觸「找不到符合條件的案件」空狀態。

### 5.6 Badge 應用

查詢頁使用三個 badge(cases/page.tsx:14 匯入;樣式表 `status-badges.tsx`):

**CaseStatusBadge** — 六態,顯示文字以 labels.ts:24-31 為正本:

| 值 | zh-TW | 樣式(variant) |
| --- | --- | --- |
| Open | 處理中 | default |
| Pending Supplier | 待供應商回覆 | secondary |
| Investigating | 調查中 | outline |
| Pending Verification | 待有效性驗證 | amber |
| Closed | 已結案 | success |
| Cancelled | 已取消 | muted |

**OverdueBadge** — 固定文字「逾期」,destructive 紅(red-100 / red-800);顯示條件依 §1.5(案件未結案 / 未取消、存在進行中的 Next Action、到期日早於目前時間、Action Status = Open),元件端以 `caseDetail.overdue` 布林值渲染,不允許手動設定。

**StaleBadge** — 文字 `{days} 天未更新`,amber;days = `daysAging(updatedAt)`(整日計算、clamp 0,aging.ts:4-8);門檻 `STALE_THRESHOLD_DAYS = 14`(aging.ts:11);`updatedAt` 為 null 或不足 14 天不渲染。

- 查詢表格無嚴重程度欄;SeverityBadge 用於案件詳情頁(第 6 章),本章不展開。

### 5.7 空 / 載入 / 錯誤狀態

| 狀態 | 查詢頁行為 |
| --- | --- |
| 空(有篩選) | 顯示「找不到符合條件的案件,請調整或清除上方篩選條件。」(cases/page.tsx:192-194),提示動作 = 調整或清除篩選 |
| 空(無篩選) | 顯示「尚無異常案件。建立您的第一個案件開始追蹤。」+「建立案件」按鈕(cases/page.tsx:196-206) |
| 載入中 | 依 第 3 章 3.5:資料區塊在載入完成前顯示明確 loading 指示,不留空白也不顯示假資料;本頁為 Server Component(`force-dynamic`,cases/page.tsx:24),由 Next.js App Router 載入邊界處理 |
| 錯誤 | 依 第 3 章 3.5:錯誤訊息附「如何修正」,不靜默失敗;另篩選參數解析為容錯設計,無效參數值被忽略而非報錯(cases/page.tsx:59-98) |

空狀態判定依據:`total === 0` 進入空狀態;再以 `hasActiveFilters`(排除 `sort`)區分「有篩選」與「無篩選」兩種文案(cases/page.tsx:190-207)。

### 5.8 與架構 §6.2 對照

**分頁標籤對照**:架構 §6.2 定義的查詢頁分頁標籤(All / Open / Overdue / Pending Supplier / Pending Verification / Closed),在 Web 實作以「狀態篩選下拉 + 僅顯示逾期案件 checkbox」的組合達成,而非固定分頁:

| §6.2 分頁標籤 | Web 達成方式 |
| --- | --- |
| All | 不設 `status`(全部狀態) |
| Open | `status=Open`(處理中) |
| Overdue | `overdueOnly=1`(僅顯示逾期案件;Overdue 依 §10 自動判定) |
| Pending Supplier | `status=Pending Supplier`(待供應商回覆) |
| Pending Verification | `status=Pending Verification`(待有效性驗證) |
| Closed | `status=Closed`(已結案) |

同一資訊以可組合的結構化篩選呈現;`overdueOnly` 與 `status` 可並存(例如 `status=Open` 且 `overdueOnly=1`)。

**篩選清單對照**:§6.2 Filters(Supplier / Case Type / Source / Status / SQE Owner / Part Number / Failure Mode / Date Range / Overdue)全部對應:supplierId、caseType、source、status、ownerId、partNumber、failureMode、dateFrom + dateTo、overdueOnly(5.3)。

**搜尋對照**:§6.2 Search 的範圍(Case ID / Supplier / Part Number / Failure Mode / Keyword)對應單一 `q` 關鍵字框,placeholder「案件編號、供應商、料號、不良模式或關鍵字…」即列舉搜尋範圍(5.3)。

**Manager View**:架構 §23 的 Manager Summary View(每列含 Case ID / Supplier / Problem Summary / Status / Priority / Current Next Action / Due Date / Overdue / Root Cause Status / CA Status / Verification Status / Last Update)在本章僅提及、非主章節。查詢表格已涵蓋其中 案件編號 / 供應商 / 異常摘要 / 狀態 / 下一步處置 / 到期日 / 逾期 / 最後更新 八欄;Priority 與品質狀態欄位(Root Cause / CA / Verification)未納入查詢表格,若日後實作 Manager View 屬獨立檢視,不在本章範圍。

## 第 6 章 案件詳情(7 個分頁)

> 事實來源:`sqe-incident-manager/src/components/case-detail/` 各 tab 元件與 `src/app/cases/[id]/page.tsx`、`src/lib/labels.ts`(zh-TW 標籤正本)、架構文件 §7 / §11–§18 / §26、`.omo/notepads/ui-design-framework/web-truth.md` §① / §②。
> 本章僅描述案件詳情頁的 7 個分頁。建立案件與查詢頁分別見第 4 章、第 5 章。

案件詳情頁(路徑 `/cases/[id]`)由「header + tab bar」構成。header 由 `src/app/cases/[id]/page.tsx` 渲染;tab 內容由 `CaseDetailTabs` 以 `defaultValue="overview"` 掛載,7 個分頁的標題為現行 UI 用語,一字不差取自 `case-detail-tabs.tsx:17-23`,與架構 §7 建議的英文 tab 名對照如下:

| key | zh-TW 分頁標題 | 對應元件 | 本章節 |
| --- | --- | --- | --- |
| overview | 案件概況 | OverviewTab | 6.1 |
| timeline | 處理歷程 | TimelineTab | 6.2 |
| investigation | 異常分析 | InvestigationTab | 6.3 |
| eight-d | Supplier 8D | EightDTab | 6.4 |
| corrective-actions | 改善措施 | CorrectiveActionsTab | 6.5 |
| attachments | 附件 | AttachmentsTab | 6.6 |
| history | 變更紀錄 | HistoryTab | 6.7 |

詳情頁版面(`cases/[id]/page.tsx:22-43`):

```
(寬度 ~1280px)
============================================================
[CASE-2026-0001] [處理中] [High] [逾期]
> 料件外觀刮傷導致功能異常
> 供應商：ABC 精密工業 · 負責人：張三

(結案) (重新開啟)
============================================================
== 潛在重複異常 ==
> 同供應商的相似歷史案件(RepeatIssuesPanel,僅在有相似案件時顯示表格)

== Tabs ==
[案件概況] [處理歷程] [異常分析] [Supplier 8D] [改善措施] [附件] [變更紀錄]
```

header 行為規則:

- 第一行 = 案件編號 + CaseStatusBadge + SeverityBadge(有 severity 時才顯示)+ OverdueBadge(逾期時才顯示)(page.tsx:25-28)。
- 第二行為 title;第三行為「供應商：{名稱} · 負責人：{SQE 負責人}」(無負責人時省略負責人段)(page.tsx:30-34)。
- 右上動作:CloseCaseDialog(結案)與 ReopenCaseDialog(重新開啟)。案件為已結案／已取消時,結案按鈕 disabled;反之重新開啟按鈕 disabled(page.tsx:37-38)。
- header 與 tabs 之間為「潛在重複異常」面板(RepeatIssuesPanel),呈現同供應商的相似歷史案件,無相似案件時顯示「無相似案件」(repeat-issues-panel.tsx:39)。
- 資料載入:詳情頁為 Server Component,`getCaseDetail(id)` 找不到案件時 `notFound()` 轉 404(整頁層級錯誤態,page.tsx:16)。

---

### 6.1 案件概況(Overview)

對應元件 `src/components/case-detail/overview-tab.tsx`。依序為三張卡片(案件資料、品質結論、目前處置)與一列動作區。Wireframe 如下:

```
(寬度 ~1280px)
== 案件資料 ==
案件編號:  CASE-2026-0001      異常摘要:  料件外觀刮傷導致功能異常
狀態:      [處理中] [逾期]     變更狀態:  [處理中 v]
嚴重程度:  High                供應商:    ABC 精密工業
SQE 負責人: 張三                建立時間:  2026/08/01
關案時間:  —                   重開時間:  —
不良率:    3.25%               案件天數:  17 天 [17 天未更新]
案件類型:  供應商品質異常       異常來源:  進料
料號:      ABC-123             品名:      連接器
不良模式:  外觀刮傷             不良描述:  表面有刮痕…(tooltip 顯示全文)
最後更新:  2026/08/18

== 品質結論 ==
Root Cause: [尚未開始]   矯正措施: [執行中]   有效性驗證: [待驗證]

== 目前處置 ==
[待處理] [逾期]
> 要求供應商 3 天內提交 FA 報告
> 負責人：李四 · 到期日：2026/08/20
(完成) (取消)

(建立處置) (結案) (重新開啟)
> 結案於已結案/已取消時 disabled;重新開啟反之
```

**卡片一:案件資料**(overview-tab.tsx:35-140)。三欄 `dl` 清單,全部為顯示欄位,無值以「—」呈現;長內容省略並以 tooltip 顯示全文:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 案件編號 | `case_number` | 必填 | 顯示 caseDetail.caseNumber(:42-43),不可編輯 |
| 異常摘要 | `title` | 必填 | 顯示案件標題(:46-47) |
| 狀態 | `status` | 必填 | caseStatusLabel 顯示;逾期時附 OverdueBadge(:50-54) |
| 變更狀態 | `status` | 必填 | CaseStatusSelect 下拉,可切換 Open / Pending Supplier / Investigating / Pending Verification 四種;案件已結案／已取消時 disabled(case-status-select.tsx:16-21,37) |
| 嚴重程度 | `severity` | 選填 | 顯示原始值 Low / Medium / High / Critical(不翻譯);無值「—」(:67-68) |
| 供應商 | `supplier_id` | 必填 | 顯示 supplier.name(:71-72) |
| SQE 負責人 | `sqe_owner_id` | 選填 | 顯示 sqeOwner.name;無值「—」(:75-76) |
| 建立時間 | `opened_at` | 系統 | formatDate(openedAt)(:79-80) |
| 關案時間 | `closed_at` | 系統 | formatDate(closedAt);未結案顯示「—」(:83-84) |
| 重開時間 | `reopened_at` | 系統 | formatDate(reopenedAt);未重開顯示「—」(:87-88) |
| 不良率 | `defect_rate` | 選填 | 顯示 `${(defectRate*100).toFixed(2)}%`;null 顯示「—」(:91-94) |
| 案件天數 | `aging`(計算值) | 系統 | 顯示 `${aging} 天`;daysAging(updatedAt) ≥ 14(門檻 STALE_THRESHOLD_DAYS = 14)附 StaleBadge「{n} 天未更新」(:97-103,lib/rules/aging.ts:11) |
| 案件類型 | `case_type` | 必填 | caseTypeLabel 顯示(:106-107) |
| 異常來源 | `source` | 必填 | caseSourceLabel 顯示(:110-111) |
| 料號 | `part_number` | 選填 | 無值「—」(:114-115) |
| 品名 | `part_name` | 選填 | 無值「—」(:118-119) |
| 不良模式 | `failure_mode` | 選填 | 無值「—」(:122-123) |
| 不良描述 | `defect_description` | 選填 | `max-w-64 truncate`,title tooltip 顯示全文;無值「—」(:126-132) |
| 最後更新 | `updated_at` | 系統 | formatDate(updatedAt)(:135-136) |

**卡片二:品質結論**(overview-tab.tsx:142-174)。三項聚合狀態,以 badge 摘要呈現,細部內容在各對應 tab 維護:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| Root Cause | `root_cause.status` | 系統 | RootCauseStatusBadge;案件無 Root Cause 時以 "Not Started"(尚未開始)為預設值(:149-154) |
| 矯正措施 | 聚合值(getWorstCaStatus) | 系統 | CaStatusBadge 顯示案件所有矯正措施中最差狀態;無矯正措施時顯示「—」(:157-160) |
| 有效性驗證 | 聚合值(getLatestVerificationResult) | 系統 | VerificationResultBadge 顯示最新驗證結果;無驗證紀錄時顯示「—」(:163-170) |

**卡片三:目前處置**(overview-tab.tsx:176-200)。呈現案件唯一的 Current Next Action:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 處置狀態 | `status` | 必填 | ActionStatusBadge 顯示(待處理／已完成／已取消);案件逾期時附 OverdueBadge(:184-185) |
| 處置內容 | `description` | 必填 | currentAction.description(:187) |
| 負責人／到期日 | `owner` / `due_date` | 選填／必填 | 一行呈現「負責人：{值} · 到期日：{日期}」;負責人無值「—」(:189) |
| 完成按鈕 | `completed_at` | 系統 | 開啟「完成處置」dialog(:192) |
| 取消按鈕 | `cancelled_at` | 系統 | 開啟「取消處置」dialog;destructive 樣式(:193) |

無目前處置時顯示「尚無待處置動作。」(:197)。

**動作區**(overview-tab.tsx:202-206):建立處置(主按鈕)、結案、重新開啟。

**Dialog 欄位**(overview-tab.tsx 內建 + case-close-reopen.tsx)。全部 dialog 遵循 ActionDialog 慣例:確認／儲存在左、取消在右;送出失敗時顯示 Alert「錯誤」;成功後 dialog 自動關閉(action-dialog.tsx:37-75,110-117):

| Dialog | 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- | --- |
| 建立下一步處置 | 處置內容 | `description` | 必填 | Textarea,placeholder「接下來要做什麼？」(:227-233) |
| | 負責人 | `owner` | 選填 | 自由文字「人員或職位」(:236-237) |
| | 到期日 | `due_date` | 必填 | date 輸入(:240-241);送出鈕「建立處置」 |
| 完成處置 | 完成說明 | `completion_note` | 完成時必填 | required Textarea,placeholder「做了什麼？」(:259-265);送出鈕「完成處置」 |
| 取消處置 | 取消原因 | `cancel_note` | 取消時必填 | required Textarea,placeholder「為什麼要取消此處置？」(:284-290);送出鈕「取消處置」,destructive |
| 結案 | 結案說明 | `closure_note` | 結案時必填 | required Textarea,placeholder「為什麼要關閉此案件？」;送出鈕「確認結案」(case-close-reopen.tsx:31-37) |
| 重新開啟 | 重開原因 | `reopened_reason` | 重開時必填 | required Textarea,placeholder「為什麼要重新開啟此案件？」(:69-75) |
| | 下一步處置內容 | `description` | 必填 | required Textarea,placeholder「接下來要做什麼？」(:78-85) |
| | 負責人 | `owner` | 選填 | (:87-89) |
| | 到期日 | `due_date` | 必填 | required date(:91-92);送出鈕「確認重新開啟」 |

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 無目前處置:「尚無待處置動作。」;各選填欄位無值顯示「—」(嚴重程度、SQE 負責人、料號、品名、不良模式、不良描述、關案／重開時間);品質結論無矯正措施／無驗證結果顯示「—」 |
| 載入中(loading) | 詳情頁為 Server Component;資料取得完成前不渲染假資料,依通用準則(第 3 章 3.5)顯示明確 loading 指示 |
| 錯誤(error) | 案件不存在時 `notFound()` 轉 404;變更狀態失敗時下拉下方顯示紅色錯誤文字(case-status-select.tsx:67);dialog 送出失敗時 Alert「錯誤」+ 錯誤說明 |
| 成功(success) | 建立／完成／取消處置、結案／重新開啟成功後 dialog 自動關閉,目前處置卡與 header badge 立即更新;變更狀態成功後下拉即時反映新狀態 |

---

### 6.2 處理歷程(Timeline)

對應元件 `src/components/case-detail/timeline-tab.tsx`。以時間順序列出案件重要事件(架構 §17:Timeline 是日常查看,History 是稽核追溯)。單張卡片:

```
(寬度 ~960px)
== 處理歷程 ==
- 案件建立 CASE-2026-0001
  CASE_CREATED · 張三 · 2026/08/01
- 狀態變更為調查中
  STATUS_CHANGED · 張三 · 2026/08/03
- 建立下一步處置
  ACTION_CREATED · 李四 · 2026/08/03
> 空狀態:尚無處理歷程。
```

每筆事件為一行描述 + 一行中繼資料,格式固定為 `{eventType} · {actor} · {日期}`(:26-30):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| (事件描述) | `description` | 必填 | 直接顯示,無標籤(:26) |
| eventType | `event_type` | 必填 | 直接顯示原始 enum 字串(如 CASE_CREATED),無 zh-TW 對照(:28) |
| 操作者 | `actor_id` | 選填 | actor.name;null 顯示「未知」(:28) |
| 日期 | `created_at` | 系統 | formatDate(createdAt)(:29) |

**eventType 清單**(架構 §26.5:1167,共 22 種)。MVP 實作 15 種,Phase 2 新增 7 種:

| 階段 | eventType(原始 enum) |
| --- | --- |
| MVP | CASE_CREATED |
| MVP | STATUS_CHANGED |
| MVP | ACTION_CREATED |
| MVP | ACTION_COMPLETED |
| MVP | ACTION_CANCELLED |
| MVP | ATTACHMENT_UPLOADED |
| MVP | EIGHT_D_REVIEWED |
| MVP | INVESTIGATION_UPDATED |
| MVP | ROOT_CAUSE_UPDATED |
| MVP | CA_CREATED |
| MVP | CA_UPDATED |
| MVP | CA_COMPLETED |
| MVP | EFFECTIVENESS_RESULT |
| MVP | CASE_CLOSED |
| MVP | CASE_REOPENED |
| Phase 2 | CONTAINMENT_UPDATED |
| Phase 2 | DISPOSITION_SET |
| Phase 2 | PRIORITY_CHANGED |
| Phase 2 | CASE_LINKED |
| Phase 2 | COST_RECORDED |
| Phase 2 | ESCALATION_CREATED |
| Phase 2 | ESCALATION_RESOLVED |

> VERIFY:eventType 直接輸出原始 enum(labels.ts 無 TimelineEventType 對應表,grep `EVENT_TYPE` 於 labels.ts 無命中;web-truth.md §2.2)。文件不自行翻譯,若後續補 zh-TW 對照需另建 label 表並同步本節。

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 「尚無處理歷程。」(:17) |
| 載入中(loading) | 事件清單為唯讀顯示;載入完成前依 第 3 章 3.5 顯示明確 loading 指示 |
| 錯誤(error) | 資料取得失敗時顯示錯誤指示並附修正建議(依 第 3 章 3.5,不靜默失敗) |
| 成功(success) | 本 tab 無直接寫入;其他 tab 動作完成後(建立處置、狀態變更等),切回本 tab 即見新增事件,最新事件置於清單尾 |

---

### 6.3 異常分析(Investigation)

對應元件 `src/components/case-detail/investigation-tab.tsx`。集中管理異常分析(架構 §11),由「分析紀錄」與「Root Cause｜根本原因」兩張卡片組成:

```
(寬度 ~1280px)
== 分析紀錄 ==
[FACT｜已確認事實] 張三 · 2026/08/03
> 供應商製程記錄顯示該批烘烤溫度超出上限
[📎 2 份附件]

== 新增紀錄 ==
* 必填 新增紀錄: [記錄已確認事實、推論、假設或待確認事項...]
證據分類:       [請選擇證據分類 v]
(新增紀錄)

== Root Cause｜根本原因 ==
Root Cause 說明: [根本原因是什麼？]
狀態:           [尚未開始 v]
驗證方式:       [如 5-Why、Fishbone、8D D4]
驗證證據:       [支持 Root Cause 的證據]
結論說明:       [信心程度、待確認事項、建議後續驗證]
無法確認原因說明: [Root Cause 狀態為「無法確認」時必填]
(儲存 Root Cause)
```

**分析紀錄**(NotesSection,:28-108)。筆記列表為 append-only,每筆以卡片呈現;下方為新增紀錄表單:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 新增紀錄 | `content` | 必填 | required Textarea,placeholder「記錄已確認事實、推論、假設或待確認事項...」(:83-89) |
| 證據分類 | `evidence_type` | 選填 | FormSelect,選項 NOTE_EVIDENCE_TYPES(FACT / INFERENCE / ASSUMPTION / UNKNOWN),placeholder「請選擇證據分類」(:92-93) |
| (顯示)證據分類 | `evidence_type` | 選填 | badge 顯示 lookupLabel 結果:FACT｜已確認事實 / INFERENCE｜推論 / ASSUMPTION｜假設 / UNKNOWN｜待確認(labels.ts:104-112);無分類不顯示 badge(:65) |
| (顯示)作者 | `author_id` | 系統 | author.name;null 顯示「未知」(:67) |
| (顯示)日期 | `created_at` | 系統 | formatDate(:67) |
| (顯示)附件數 | 聚合值(relatedNoteId) | 系統 | 該筆紀錄關聯的附件數,> 0 時顯示 badge「📎 {n} 份附件」(:71-75) |

**Root Cause｜根本原因**(RootCauseSection,:110-201)。單一表單維護案件 1:1 的 Root Cause;狀態下拉可切換五種狀態(架構 §12,避免把「推測原因」直接當作已驗證 Root Cause):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| Root Cause 說明 | `statement` | 依狀態 | Textarea,placeholder「根本原因是什麼？」;架構 §26.7:狀態為 Verified / Not Established 時必填(§31)(:137-143) |
| 狀態 | `status` | 必填 | FormSelect,選項 ROOT_CAUSE_STATUSES(Not Started／Under Investigation／Proposed／Verified／Not Established),預設 "Not Started"(:146-151) |
| 驗證方式 | `validation_method` | 選填 | placeholder「如 5-Why、Fishbone、8D D4」(:154-160) |
| 驗證證據 | `validation_evidence` | 選填 | placeholder「支持 Root Cause 的證據」(:163-169) |
| 結論說明 | `conclusion_note` | 選填 | placeholder「信心程度、待確認事項、建議後續驗證」(:172-178) |
| 無法確認原因說明 | `not_established_reason` | Not Established 時必填 | placeholder 明示「Root Cause 狀態為『無法確認』時必填」;元件未標 required,送出前依狀態把關(:181-187) |

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 分析紀錄:「尚無異常分析紀錄。」(:57);Root Cause 表單以空值與預設狀態「Not Started」呈現 |
| 載入中(loading) | 表單送出中按鈕 disabled;載入中依 第 3 章 3.5 顯示指示 |
| 錯誤(error) | 新增紀錄或儲存 Root Cause 失敗:Alert「錯誤」+ 錯誤說明(:96-99,189-193) |
| 成功(success) | 新增紀錄成功後表單重置(key=notes.length 重掛載)、列表即時新增;儲存 Root Cause 成功後表單維持現值,badge 立即反映新狀態 |

---

### 6.4 Supplier 8D

對應元件 `src/components/case-detail/eight-d-tab.tsx`。MVP 不做線上 8D,只管理供應商提供的檔案(架構 §15)。由「審查紀錄」與「新增審查」兩張卡片組成:

```
(寬度 ~960px)
== 審查紀錄 ==
Rev A [退回修正]
> 缺少 D4 根本原因分析與驗證資料
> 2026/08/10 · 8D_Rev_A.pdf
Rev B [接受]
> 已補齊 D4,同意接受
> 2026/08/15 · 8D_Rev_B.pdf
> 空狀態:尚未上傳 Supplier 8D。

== 新增審查 ==
* 必填 版本:   [如 Rev A]
審查結果:  [請選擇審查結果 v]
審查意見:  [給供應商的意見]
附件:      [選擇附件（選填） v]
(記錄審查)
```

**審查紀錄列表**(eight-d-tab.tsx:34-71)。每筆為一列審查紀錄,依版本堆疊:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 版本 | `revision` | 必填 | 顯示「Rev {revision}」(:46) |
| 審查結果 | `review_status` | 必填 | EightDReviewStatusBadge:接受／退回修正／需補充證據(:47) |
| 審查意見 | `review_comment` | 選填 | 有值才顯示,保留換行(:49-51) |
| 日期 | `review_date` | 系統 | formatDate(:53) |
| 附件 | `attachment_id` | 選填 | 有附件時顯示檔名連結,指向 `/api/attachments/{id}`(:54-64) |

**多版本不覆蓋規則**(架構 §15、§26.11):保留每一次 Supplier 8D Revision,每版一列,不得以新版覆蓋舊版而失去 Review History。新增一筆即新增一列,不修改既有紀錄。

**新增審查表單**(eight-d-tab.tsx:73-118):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 版本 | `revision` | 必填 | required Input,placeholder「如 Rev A」(:80-81) |
| 審查結果 | `review_status` | 選填 | FormSelect,選項 EIGHT_D_REVIEW_STATUSES(Accepted／Return for Revision／Need More Evidence),placeholder「請選擇審查結果」;架構 §26.11 語意為必填,元件端未標 required(:84-89) |
| 審查意見 | `review_comment` | 選填 | Textarea,placeholder「給供應商的意見」(:92-97) |
| 附件 | `attachment_id` | 選填 | FormSelect 列出本案件附件檔名,placeholder「選擇附件（選填）」(:100-105) |

送出鈕「記錄審查」(:113-115)。

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 「尚未上傳 Supplier 8D。」(:40) |
| 載入中(loading) | 表單送出中按鈕 disabled;載入中依 第 3 章 3.5 顯示指示 |
| 錯誤(error) | 記錄審查失敗:Alert「錯誤」+ 錯誤說明(:107-111) |
| 成功(success) | 記錄審查成功後審查紀錄列表即時新增一列,表單重置;badge 立即反映審查結果 |

---

### 6.5 改善措施(Corrective Actions)

對應元件 `src/components/case-detail/corrective-actions-tab.tsx`。矯正措施(Corrective Action)為獨立紀錄,一案可有多筆(架構 §13)。由「建立矯正措施」表單與 CA 卡片清單組成:

```
(寬度 ~1280px)
== 建立矯正措施 ==
* 必填 措施內容:   [將採取什麼矯正措施？]
負責單位／人員: [人員或職位]
預計完成日:     [2026/08/30]
[x] 需進行有效性驗證
備註:           [其他說明]
(建立矯正措施)

== 矯正措施 ==
[更換烘烤治具並重新驗證製程參數] [📎 1 份附件] [執行中]
> 負責人：王五 · 預計完成：2026/08/30 · 需驗證
> 備註：已向設備商取得新治具
> 執行證據：新治具安裝照片與參數設定紀錄
> 完成日期：2026/09/01
== Effectiveness Verification｜有效性驗證 ==
[待驗證]
驗證方式:      30 天監控
接受標準:      NG 率 < 0.5%
驗證期間／樣本: 3 批
(記錄驗證結果)
狀態: [執行中 v] (更新狀態) (完成)
> 空狀態:尚未建立矯正措施。
```

**建立矯正措施表單**(corrective-actions-tab.tsx:62-112):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 措施內容 | `description` | 必填 | required Textarea,placeholder「將採取什麼矯正措施？」(:70-76) |
| 負責單位／人員 | `responsible_party` | 選填 | placeholder「人員或職位」(:79-80) |
| 預計完成日 | `target_date` | 選填 | date 輸入(:83-84) |
| 需進行有效性驗證 | `effectiveness_verification_required` | 必填(預設 false) | checkbox(:86-95) |
| 備註 | `notes` | 選填 | Textarea,placeholder「其他說明」(:97-98) |

送出鈕「建立矯正措施」(:106-108)。

**CA 卡片**(CaCard,:147-189)。每筆矯正措施一張卡片:

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 措施內容 | `description` | 必填 | 卡片標題(:155) |
| 附件數 | 聚合值(relatedCaId) | 系統 | > 0 時顯示 badge「📎 {n} 份附件」(:157-159) |
| 狀態 | `status` | 必填 | CaStatusBadge:已規劃／執行中／已實施／待有效性驗證／有效／無效／已取消(:160) |
| 負責人／預計完成／需驗證 | `responsible_party` / `target_date` / `effectiveness_verification_required` | 選填／選填／必填 | 一行呈現「負責人：{值} · 預計完成：{日期}」;需驗證時附加「 · 需驗證」(:163-166) |
| 備註 | `notes` | 選填 | 有值才顯示(:169) |
| 執行證據 | `implementation_evidence` | Implemented 時建議 | 有值時以「執行證據：{值}」顯示(:170-175) |
| 完成日期 | `completion_date` | 完成時 | 有值時以「完成日期：{日期}」顯示(:176-180) |
| 狀態更新 | `status` | 必填 | FormSelect(CA_STATUSES)+「更新狀態」按鈕;失敗時按鈕旁顯示紅色錯誤文字(:191-211) |
| 完成按鈕 | `completion_date` | — | 僅狀態為 Planned／In Progress／Implemented 時顯示(:149,184) |

**完成矯正措施 dialog**(CompleteCaDialog,:213-246):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 實際完成日 | `completion_date` | 完成時必填 | required date(:233-235) |
| 執行證據 | `implementation_evidence` | 選填 | Textarea,placeholder「已實施的佐證資料」(:237-243) |

dialog 行為:需進行有效性驗證的措施,完成後狀態變更為「待有效性驗證」;否則標記為「已實施」(:218-222)。送出鈕「完成措施」。

**有效性驗證面板**(VerificationPanel,:256-301)。掛在每張 CA 卡片內;「已實施」不等於「有效」,只有完成有效性驗證且結果符合接受標準才可標記 Effective(架構 §14):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 驗證方式 | `method` | 選填 | 「驗證方式：{值}」;無值「—」(:264-266) |
| 接受標準 | `acceptance_criteria` | 選填 | 「接受標準：{值}」;無值「—」(:268-270) |
| 驗證期間／樣本 | `period_sample` | 選填 | 「驗證期間／樣本：{值}」;無值「—」(:272-274) |
| 驗證證據 | `evidence` | 選填 | 有值才顯示(:275-280) |
| 驗證結論 | `conclusion` | 選填 | 有值才顯示(:281-286) |
| 驗證日期 | `verified_date` | 系統 | 有值才顯示(:287-292) |
| 驗證結果 | `result` | 必填 | VerificationResultBadge:待驗證／有效／無效／無法判定;無驗證紀錄不顯示(:259) |

無驗證紀錄時顯示「尚未建立有效性驗證。」(:295)。

**記錄驗證結果 dialog**(VerificationDialog,:304-382)。送出鈕「儲存驗證結果」;dialog 標題「Effectiveness Verification｜有效性驗證」,說明文字明示「已實施不等於有效——記錄驗證結果與佐證。」(:314-315):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 驗證方式 | `method` | 選填 | placeholder「如 30 天監控、重新檢驗」(:329-335) |
| 接受標準 | `acceptance_criteria` | 選填 | placeholder「何條件成立此措施方為有效？」(:338-344) |
| 驗證期間／樣本 | `period_sample` | 選填 | placeholder「如 3 批、30 天」(:347-353) |
| 驗證結果 | `result` | 必填 | FormSelect,選項 VERIFICATION_RESULTS(Pending／Effective／Ineffective／Inconclusive),預設 "Pending"(:356-361) |
| 驗證證據 | `evidence` | 選填 | placeholder「支持驗證結果的證據」(:364-370) |
| 驗證結論 | `conclusion` | 選填 | placeholder「整體結論」(:373-379) |

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 無任何矯正措施:「尚未建立矯正措施。」(:129);CA 無驗證紀錄:「尚未建立有效性驗證。」(:295) |
| 載入中(loading) | 表單送出中按鈕 disabled;載入中依 第 3 章 3.5 顯示指示 |
| 錯誤(error) | 建立矯正措施失敗:Alert「錯誤」(:100-104);狀態更新失敗:按鈕旁紅色錯誤文字(:208);dialog 送出失敗:Alert「錯誤」 |
| 成功(success) | 建立後卡片即時出現;完成後狀態 badge 更新(需驗證者轉「待有效性驗證」);儲存驗證結果後面板更新並顯示結果 badge |

---

### 6.6 附件(Attachments)

對應元件 `src/components/case-detail/attachments-tab.tsx`。附件必須分類(架構 §16);由「上傳附件」表單與附件列表組成:

```
(寬度 ~1280px)
== 上傳附件 ==
* 必填 檔案:   [選擇檔案……]
附件分類:   [其他 v]
說明:       [此附件用途？]
版本:       [如 Rev A]
關聯分析紀錄: [(不關聯) v]
關聯矯正措施: [(不關聯) v]
(上傳)

== 附件 ==
8D_Rev_A.pdf  → /api/attachments/{id}
> Supplier 8D · Rev A · 2.3 MB · 2026/08/10
> 供應商 8D 報告第一版
> [📎 關聯分析紀錄:烘烤溫度記錄…] [📎 關聯矯正措施:更換治具…]
(刪除)
> 空狀態:尚未上傳附件。
```

**上傳附件表單**(attachments-tab.tsx:47-102):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 檔案 | `file` | 必填 | type="file",required(:54-61) |
| 附件分類 | `category` | 必填 | FormSelect,選項 ATTACHMENT_CATEGORIES 九類,預設 "Other"(:64-65) |
| 說明 | `description` | 選填 | placeholder「此附件用途？」(:68-73) |
| 版本 | `revision` | 選填 | placeholder「如 Rev A」(:76-77) |
| 關聯分析紀錄 | `related_note_id` | 選填 | 僅當案件有分析紀錄時顯示;選項預覽格式「{證據分類} — {內容前 30 字}」(:79-84) |
| 關聯矯正措施 | `related_ca_id` | 選填 | 僅當案件有矯正措施時顯示;選項預覽格式「{內容前 30 字} — {狀態}」(:85-90) |

附件分類九類(labels.ts:89-102,以 attachmentCategoryLabel 為準):

| value | zh-TW |
| --- | --- |
| Evidence | 證據 |
| NG Photo | 不良照片 |
| FA Report | FA 報告 |
| Supplier 8D | Supplier 8D |
| Corrective Action Evidence | 矯正措施證據 |
| Effectiveness Evidence | 有效性驗證證據 |
| Specification / Reference | 規格／參考文件 |
| Supplier Audit Evidence | 供應商稽核證據 |
| Other | 其他 |

送出鈕「上傳」(:97-99)。

**附件列表**(attachments-tab.tsx:104-158):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 檔名連結 | `file_name` | 必填 | 連結至 `/api/attachments/{id}` 下載(:122-127) |
| 分類 | `category` | 必填 | attachmentCategoryLabel(:129) |
| 版本 | `revision` | 選填 | 有值時顯示「 · Rev {revision}」(:130) |
| 大小 | `file_size` | 系統 | formatBytes(:131) |
| 上傳日期 | `uploaded_at` | 系統 | formatDate(:131) |
| 說明 | `description` | 選填 | 有值才顯示(:133-135) |
| 關聯分析紀錄 | `related_note_id` | 選填 | badge「📎 關聯分析紀錄：{內容前 20 字}」,tooltip 顯示全文(:139-142) |
| 關聯矯正措施 | `related_ca_id` | 選填 | badge「📎 關聯矯正措施：{內容前 20 字}」,tooltip 顯示全文(:144-147) |
| 刪除 | `id` | 系統 | 開啟「刪除附件」dialog,每列右側(:151) |

**刪除附件 dialog**(DeleteAttachmentDialog,:163-173):標題「刪除附件」,確認文字「確定要刪除『{檔名}』嗎？此操作可能無法復原。」,送出鈕「刪除」,destructive 樣式。

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 「尚未上傳附件。」(:110) |
| 載入中(loading) | 上傳中按鈕 disabled;載入中依 第 3 章 3.5 顯示指示 |
| 錯誤(error) | 上傳失敗:Alert「錯誤」+ 錯誤說明(:91-95) |
| 成功(success) | 上傳成功後列表即時新增該附件;刪除成功後該列移除 |

---

### 6.7 變更紀錄(History)

對應元件 `src/components/case-detail/history-tab.tsx`。Audit Log 為稽核追溯用,與處理歷程(Timeline)互補(架構 §17-§18);五欄表格:

```
(寬度 ~960px)
== 變更紀錄 ==
動作            變更前         變更後           操作者  日期
STATUS_CHANGED  調查中         待供應商回覆     張三    2026/08/05
ACTION_CREATED  —             要求 FA 報告…    李四    2026/08/06
ATTACHMENT...   (長內容截斷,   (長內容截斷,    ...
                tooltip 顯示)  tooltip 顯示)
> 空狀態:尚無變更紀錄。
```

**表格欄位**(history-tab.tsx:27-48):

| 欄位(中文) | 英文 key | 必填級別 | 說明 |
| --- | --- | --- | --- |
| 動作 | `action` | 必填 | 顯示 log.action,粗體(:40) |
| 變更前 | `before_value` | 選填 | null 顯示「—」;長內容截斷並以 tooltip 顯示全文(:41) |
| 變更後 | `after_value` | 選填 | null 顯示「—」;長內容截斷並以 tooltip 顯示全文(:42) |
| 操作者 | `user_id` | 系統 | user.name;null 顯示「未知」(:43) |
| 日期 | `created_at` | 系統 | formatDate(:44) |

**Audit Log 不可刪除規則**(架構 §18):Audit History 不得讓使用者直接刪除;本 tab 為唯讀表格,無任何寫入或刪除操作。架構 §26.12 的 `entity_type`、`entity_id` 欄位屬系統內部,UI 未顯示(web-truth.md §⑤ 26.12 VERIFY)。

**互動狀態**:

| 狀態 | 呈現 |
| --- | --- |
| 空狀態(empty) | 「尚無變更紀錄。」(:25) |
| 載入中(loading) | 表格唯讀;載入完成前依 第 3 章 3.5 顯示明確 loading 指示 |
| 錯誤(error) | 資料取得失敗時顯示錯誤指示並附修正建議(依 第 3 章 3.5,不靜默失敗) |
| 成功(success) | 本 tab 無直接寫入;其他 tab 動作(狀態變更、處置完成等)後,切回本 tab 即見最新一列紀錄 |

## 第 7 章 SQE DailyWork 整合映射

> 本章把 Web 端(第 4-6 章)與 SQE DailyWork 桌面程式對齊:先給兩套用語的術語對照表,再按五個面向(Shell 契約、Token 與常數、對話框慣例、表格模式、Sidebar IA)逐項映射,最後是「取其優點」清單。
> 本章是**映射與建議**,不是 DailyWork 改造規格:不繪 DailyWork wireframe、不提重構方案、不列排期。
> 行號主張以 2026-08-18 實際讀檔為準;本章所有 DailyWork 檔案路徑皆相對於 `C:\Users\user\Documents\SQE DailyWork\`;「契約」指 `docs/ui-layout-theme-contract.md`。
> 已知契約與實作不一致之處(9 處 font-weight 600、群組間距 14 vs 10、分頁 12 vs 13),依事實記入第 8 章 A-2 VERIFY 清單,不臆測何者正確。

### 7.1 術語對照表

第 4-6 章使用 Web 端用語(正本 = `sqe-incident-manager/src/lib/labels.ts` 與元件實際字串);本章兩套用語並陳。下表為 Web 用語 ↔ DailyWork 用語的對照:

| # | Web 用語 | DailyWork 用語 | 說明 |
| --- | --- | --- | --- |
| 1 | 案件(case) | 事件(event)/異常(anomaly) | Web 以「案件」為核心主體;DailyWork 以事件 scope(單獨異常/訪廠發現異常/訪廠紀錄/已結案)組織,出處 `defect_list_widget.py:70-75` |
| 2 | 改善措施(CA) | 改善內容 | Web 矯正措施(Corrective Action);DailyWork 結案對話框欄位「改善內容」,出處 `close_anomaly_dialog.py:167` |
| 3 | 附件 | 現場照片與改善佐證附件 | DailyWork 結案對話框的附件標籤文字,出處 `close_anomaly_dialog.py:174` |
| 4 | 狀態徽章(status badge) | 狀態項目(status item) | Web badge 系列(第 3 章 3.1);DailyWork `create_status_item` 以 tone palette 前景/背景渲染,出處 `common_widgets.py:358-365` |
| 5 | 側欄導覽(nav rail) | 側欄(SidebarNav) | Web 扁平側欄(第 2 章);DailyWork 四群組 `_NAV_GROUPS`（供應商事件四列含作業佇列 chips 宿主）,出處 `sidebar_nav.py` |
| 6 | 待辦清單(to-do list) | 待辦(backlog) | Web 儀表板營運佇列脈絡;DailyWork **作業佇列** chips（逾期案件／根因待查／處置項目／案件總覽）,出處 `ui-layout-theme-contract.md` |
| 7 | 主檔(master data) | 基礎資料 | DailyWork 側欄「系統」群組下的「基礎資料」,出處 `sidebar_nav.py:80` |
| 8 | 分頁元件(pagination) | 分頁列(PaginationBar) | 出處 `pagination_bar.py:25` |
| 9 | 事件檢視切換(tabs/scope) | 事件 scope(一等側欄列) | Web 用 tab 或 filter 切換檢視;DailyWork 以側欄一等項目切換 scope,無頁內 tab bar,出處 `sidebar_nav.py:66-69`、契約 :158-160 |
| 10 | 表單欄位群組(form row) | 併排表單列(paired form row) | 並排欄位的共用排版元件,出處 `common_widgets.py:554-580`、契約 :74-82 |

### 7.2 Shell 契約映射

Web 端三類頁面(建立案件、異常案件查詢、儀表板)與 DailyWork 三種 workflow shell 一一對應;模態對話框另有固定 footer 契約。

| Web 元素 | DailyWork 對應契約特性 | 整合方式 |
| --- | --- | --- |
| 建立案件(`/cases/new`,第 4 章) | CreateWorkflowShell:單一捲動 owner + 頂部命令列 + inline feedback,頁尾不重複操作(common_widgets.py:133-205;命令列 :154、feedback :167-172、捲動 body :175-181、命令列右對齊 :183、:187-192;契約 :62-65) | 建立頁沿用「頂部動作列 + 單一捲動表單體」結構,動作集中於頂部,頁尾不重複儲存/取消 |
| 異常案件查詢(`/cases`,第 5 章) | QueryWorkflowShell:扁平操作面,零業務狀態(common_widgets.py:110-121;契約 :66-67「carries no filters, query state or data semantics」) | 查詢頁維持「操作面與清單內容分離」,shell 本身不攜帶篩選/查詢狀態 |
| 儀表板(`/dashboard`) | AnalyticsWorkflowShell:統計控制面,「重新整理」恆在「匯出 Excel」左側(common_widgets.py:124-130;契約 :68-70) | 儀表板工具列維持固定動作排序,避免控制項位置隨版本漂移 |
| 模態對話框(結案/重開/處置等,第 6 章) | 固定 `QDialogButtonBox` footer,模態表單不得用 CreateWorkflowShell(契約 :71-72) | 模態表單一律保留固定 footer,不套用全頁建立 shell |

### 7.3 Token 與常數映射

| Web 元素 | DailyWork 對應契約特性 | 整合方式 |
| --- | --- | --- |
| 語意 token 層(tailwind/shadcn 的 color/spacing/radius) | TOKENS 全語意命名,status 六 tone 各含 fg/bg/border/chart 四件組(theme_tokens.py:40-159、status :79-102、圓角 radius_sm/md/lg :106-108) | 新頁面的色彩與圓角沿用語意 token 層,不寫死 hex |
| 字級 scale | TYPOGRAPHY 字級(base 13 / brand_title 22 / page_title 24 / section_title 16 / caption 11 / body 12-13 / label_strong 14 / mono 11,theme_tokens.py:161-177) | 標題與內文字級沿用同一 scale,不逐元件自訂大小 |
| font-family stack | CJK 字型 chain 單一真相來源:PREFERRED_CJK_FONT_FAMILIES 15 個 family,微軟正黑 UI 優先(theme_tokens.py:14-30)、CJK_FONT_FAMILY_CSS(:34-36) | 全站 font-family 維持單一集中定義,不逐元件重設 |
| layout constraints / breakpoints | layout_constants.py:視窗 1024×680 min / 1360×860 default / 1920×1200 max(:9-16)、FORM_MAX_WIDTH=960(:6)、SIDEBAR_WIDTH=220(:52)、EVENT_LIST_FULL_COLUMNS_MIN_WIDTH=1024(:188) | 版面數值維持單一常數來源,含最小/偏好/最大三層尺寸 |

### 7.4 對話框慣例映射

| Web 元素 | DailyWork 對應契約特性 | 整合方式 |
| --- | --- | --- |
| dialog footer 動作列(第 3 章 3.4) | 固定 footer 儲存左/取消右:QDialogButtonBox(Cancel \| Save)+ apply_dialog_layout 統一排版(close_anomaly_dialog.py:179-189;契約 :72;對齊 Institution 06 §2) | 模態對話框維持固定按鈕排序與統一排版函式 |
| 未儲存變更守衛(dirty tracking) | DirtyTrackingMixin:_init_dirty_tracking 訂閱 signals(:447-450)、closeEvent 守衛(:464-468)、「未儲存變更」確認(:455-462);契約 :308 事件建立/訪廠/結案對話框共用 | 所有編輯對話框共用同一 dirty 守衛,不逐框重寫 |
| 對話框螢幕適配 | fit_dialog_to_available_screen,shrink_minimum_to_screen=True 允許縮小 min size 以留在螢幕內(window_sizing.py:114-153;契約 :35) | 對話框超出螢幕時縮小最小尺寸,確保完整可見 |
| 必填標記(第 3 章 3.3) | RequiredFieldLabel 紅色 `*` 以 TOKENS danger 渲染(common_widgets.py:368-386) | 必填欄位統一視覺標記,不混用多種標法 |
| 欄位層級驗證(第 3 章 3.3) | set_field_invalid 以 `[invalid]` property + repolish 切換 danger 邊框(common_widgets.py:401-406、:389-398);錯誤提示 make_inline_error_label(:409-420) | 驗證錯誤在欄位層級即時呈現,附如何修正的提示 |

### 7.5 表格模式映射

| Web 元素 | DailyWork 對應契約特性 | 整合方式 |
| --- | --- | --- |
| 表格(查詢/變更紀錄/附件列表) | style_table 統一交替底色、格線、隱藏垂直表頭、整列選取(common_widgets.py:329-346) | 表格視覺樣式維持單一函式套用,不逐表重設 |
| 狀態徽章欄(第 3 章 3.1) | create_status_item 以 tone palette 前景/背景 + 置中渲染(status_colors.py:16-53 六 tone 四件組;common_widgets.py:358-365) | 狀態欄以 tone 前景/背景 + 文字並陳,不只靠顏色 |
| 響應式欄位切換 | 重點/完整欄位模式:寬度 < 1024 判準(defect_list_widget.py:436-439、layout_constants.py:188);可隱藏欄 (1,2,5,6,8,11)(defect_list_widget.py:89);_sync_table_column_profile(:445-485)含「重點欄位檢視」notice(:468-473)與切換按鈕(:476-485);純顯示模式(契約 :49-50) | 窄視窗隱藏次要欄、可切換還原,欄位隱藏不影響資料與匯出 |
| 分頁(第 5 章) | PaginationBar:預設 page size 13、選項 (10,13,20,50,100)(pagination_bar.py:31-32)、最多 7 個頁碼(:33)、「共 N 筆」與跳頁 input(:142-150)、DPI 末字護欄 _LABEL_CLIP_GUARD_PX=4(:22)與 _guard_label_width(:170-172) | 分頁元件含 CJK 標籤不裁切護欄,防分數倍率裁切 |
| 長 CJK 省略(第 3 章 3.2) | text_table_item elide 時 tooltip 顯示全文(common_widgets.py:423-434;對應 Institution 06 §6) | 長文字省略並以 tooltip 顯示全文,不靜默截斷 |
| 型別感知排序 | SortableTableWidgetItem 數值/日期/佔位符「—」排後(common_widgets.py:248-299);preserve_table_sorting 保護排序(context manager,:302-317) | 表格排序依型別處理,佔位符統一排後 |


### 7.6 Sidebar IA 映射

| Web 元素 | DailyWork 對應契約特性 | 整合方式 |
| --- | --- | --- |
| 扁平 5 項側欄(第 2 章 2.1) | Workflow-first 四群組(`sidebar_nav.py` `_NAV_GROUPS`):供應商事件(新增異常/事件查詢含 badge/作業佇列/異常事件統計;佇列 chips 切換逾期案件/根因待查/處置項目/案件總覽)、倉庫不合格品(建立不合格品/待處理委外加工含 badge/待處理原物料含 badge/歷史紀錄/不合格品統計分析)、資料庫設定(供應商總覽/主檔並排導覽)、系統(顯示設定);事件查詢頁內 chips 切換單獨異常/訪廠發現異常/訪廠紀錄/已結案。首頁 hub 與訪廠建立入口已退休 | 案件相關入口依作業類型分群,群組內以作業流程排序 |
| 路由與導覽元件解耦 | sidebar 只發 nav_activated(action) signal(sidebar_nav.py:209、:322-325);MainWindow 以 `_PAGE_KEY_TO_INDEX`(:104-118)轉換、`_on_nav_activated`(:527-562)路由 page/scope/command 三種 action(scope 走 set_event_scope :556-559) | 導覽元件不直接操作堆疊,路由集中於主視窗 |
| 未處理數 badge | badge 對稱性:單獨異常 badge = 未結案異常數、兩個倉庫 badge 各綁 processing_line 計數(`_refresh_sidebar_badge`,main_window.py:704-722;契約 :172-176) | badge 一律綁真實計數來源,同一計數不對稱顯示 |
| 導覽項幾何 | 導覽項高度 38px 來自 SIDEBAR_NAV_ITEM_HEIGHT(layout_constants.py:56);群組標題為靜態 QLabel(sidebar_nav.py:301-306);無 quick-create footer(契約 :177-179) | 側欄幾何與群組標題維持單一常數來源 |

兩者的資訊架構(IA)策略不同:Web 以**功能頁**分項(儀表板/異常案件/建立案件/供應商/搜尋),層級淺、好掃描,適合頁面少、以瀏覽為主的系統;DailyWork 以**作業類型**分群(供應商事件/倉庫不合格品/系統)並在側欄第一層掛未處理計數 badge,把「今天要做的事」推到最前面,適合工作流明確、以執行為主的桌面工具。適用情境:頁面數量少且彼此獨立時,扁平功能導覽即可;當頁面依作業流程有明確上下游(如 訪廠 → 發現異常 → 結案)且有大量待辦計數時,workflow-first 分群 + badge 更能引導日常工作。兩者都維持「導覽元件與路由解耦」的同一原則。

### 7.7 「取其優點」清單

每條 = 優點名稱 + DailyWork 契約特性(附檔案:行號)+ 對應 Web 元素 + 套用建議一句話。以下 15 條為候選上限。

1. **語意設計 token 系統(不寫死 hex)**
   - DailyWork 契約特性:TOKENS 全語意命名,status 六 tone 各含 fg/bg/border/chart 四件組(theme_tokens.py:40-159、:79-102);版面數值單一來源於 layout_constants.py
   - 對應 Web 元素:CSS custom properties 語意 token 層(color/spacing/radius/font-weight)
   - 套用建議:DailyWork 新增案件管理模組時,沿用既有 TOKENS 語意命名與六 tone 四件組,不新增外觀命名或寫死 hex。

2. **CJK 字型 fallback chain 單一真相來源**
   - DailyWork 契約特性:PREFERRED_CJK_FONT_FAMILIES 15 個 family,微軟正黑 UI 優先(theme_tokens.py:14-30);CJK_FONT_FAMILY_CSS 集中組成(:34-36);apply_app_theme 統一套用(theme.py:341-366)
   - 對應 Web 元素:font-family stack 集中定義於單一 CSS token,全站共用
   - 套用建議:案件模組的文字渲染維持同一 font-family 來源,不逐元件重設字型。

3. **三種 workflow shell 分工(查詢面 / 分析面 / 建立面)**
   - DailyWork 契約特性:QueryWorkflowShell 零業務狀態(common_widgets.py:110-121)、AnalyticsWorkflowShell 統計控制面(:124-130)、CreateWorkflowShell 全頁建立(:133-205);分工規定於契約 :60-72
   - 對應 Web 元素:頁面版型元件分離(filter bar / analytics toolbar / create page layout)
   - 套用建議:新增頁面時先判斷頁面類型(查詢/分析/建立)再套用對應 shell,不混用。

4. **CreateWorkflowShell:單一捲動 owner + 頂部命令列,頁尾不重複操作**
   - DailyWork 契約特性:一個命令列(:154)+ 一個 inline feedback(:167-172)+ 一個垂直捲動 body(:175-181);命令列右對齊(:183、:187-192);禁止頁尾重複儲存/取消(契約 :62-65)
   - 對應 Web 元素:create 頁 sticky top action bar + 表單單一捲動容器
   - 套用建議:於 DailyWork 新增案件管理模組時,建立頁採用 CreateWorkflowShell 結構,動作集中在頂部。

5. **DirtyTrackingMixin:統一未儲存變更守衛**
   - DailyWork 契約特性:_init_dirty_tracking 訂閱 signals(common_widgets.py:447-450)、closeEvent 守衛(:464-468)、「未儲存變更」確認(:455-462);契約 :308 事件/訪廠/結案對話框共用
   - 對應 Web 元素:beforeunload / route-leave guard(dirty form)
   - 套用建議:案件編輯對話框沿用 DirtyTrackingMixin,不逐框重寫 dirty 守衛。

6. **必填標記 + 欄位層級即時驗證**
   - DailyWork 契約特性:RequiredFieldLabel 紅色 `*` 以 TOKENS danger 渲染(common_widgets.py:368-386);set_field_invalid 以 `[invalid]` property + repolish 切換 danger 邊框(:401-406、:389-398)
   - 對應 Web 元素:required 標記元件 + field-level error state(CSS class 切換)
   - 套用建議:案件表單的必填欄位維持統一紅色 `*` 與欄位層級即時驗證,錯誤提示附如何修正。

7. **EmptyStateWidget:四態齊備中的空狀態**
   - DailyWork 契約特性:title + hint 兩層、role="emptyState"(common_widgets.py:471-502);對應 Institution 06 §2 空/載入/錯誤/成功四態準則
   - 對應 Web 元素:empty-state 共用元件
   - 套用建議:案件清單與明細各資料區塊沿用空狀態元件,附提示與建議動作,不留空白。

8. **並排表單欄位白名單 + 共用 paired row 元件**
   - DailyWork 契約特性:契約 :74-82 並排僅限低風險組並列白名單;make_paired_form_row 共用併排列,右欄無標籤時跨兩欄(common_widgets.py:554-580、:573-577)
   - 對應 Web 元素:form grid 規則與 responsive 欄位並排策略
   - 套用建議:案件表單的並排欄位維持白名單管制,大欄位(如不良描述)維持單欄。

9. **版面常數單一來源 + 最小/偏好/最大三層尺寸契約**
   - DailyWork 契約特性:layout_constants.py:視窗 1024×680 min / 1360×860 default / 1920×1200 max(:9-16)、FORM_MAX_WIDTH=960(:6)、對話框尺寸與螢幕比例(:19-22);契約 :14、:33-34
   - 對應 Web 元素:breakpoint 常數 + layout constraints 集中管理
   - 套用建議:案件模組的版面尺寸沿用 layout_constants 單一來源與三層尺寸契約,不散落寫死。

10. **重點/完整欄位響應式表格模式(純顯示,不動資料)**
    - DailyWork 契約特性:_compact_column_profile_active 寬度 < 1024 判準(defect_list_widget.py:436-439、layout_constants.py:188);可隱藏欄 (1,2,5,6,8,11)(defect_list_widget.py:89);_sync_table_column_profile(:445-485)含「重點欄位檢視」notice(:468-473)與切換按鈕(:476-485);純顯示模式(契約 :49-50)
    - 對應 Web 元素:響應式表格欄位切換(窄視窗隱藏次要欄,可切換還原)
    - 套用建議:案件清單表格在窄視窗沿用「重點欄位」模式,欄位隱藏不影響資料與匯出。

11. **六 tone 狀態色系統(字串→tone→palette)**
    - DailyWork 契約特性:六 tone StatusPalette 四件組(status_colors.py:16-53);字串→tone 對應表(「逾期未結」→danger :57-79、:76);create_status_item 前景/背景渲染(common_widgets.py:358-365)
    - 對應 Web 元素:status badge 色系統(semantic tone,不只顏色也含文字)
    - 套用建議:案件狀態徽章沿用字串→tone→palette 三層對應,狀態不只靠顏色區分。

12. **PaginationBar:完整分頁 + DPI 護欄**
    - DailyWork 契約特性:預設 page size 13、選項 (10,13,20,50,100)(pagination_bar.py:31-32)、最多 7 個頁碼(:33)、「共 N 筆」與跳頁 input(:142-150);DPI 末字護欄 _LABEL_CLIP_GUARD_PX=4(:22)與 _guard_label_width(:170-172)
    - 對應 Web 元素:分頁元件(頁碼 + 每頁筆數 + 跳頁),含 CJK 標籤不裁切處理
    - 套用建議:案件清單分頁沿用 PaginationBar,含 CJK 標籤的 DPI 護欄。

13. **對話框固定 footer + 按鈕排序(確認左/取消右)**
    - DailyWork 契約特性:QDialogButtonBox(Cancel | Save)+ apply_dialog_layout 統一排版(close_anomaly_dialog.py:179-189);契約 :71-72 模態保留固定 footer;對齊 Institution 06 §2
    - 對應 Web 元素:dialog footer action bar 慣例
    - 套用建議:案件模態對話框維持固定 footer 與確認左/取消右排序,不改用全頁 shell。

14. **螢幕適配 helper(視窗/對話框兩套,可縮 min size 保在螢幕內)**
    - DailyWork 契約特性:fit_widget_to_available_screen(window_sizing.py:57-111)、fit_dialog_to_available_screen(shrink_minimum_to_screen=True :114-153)、restore_or_fit_window_geometry(:156);契約 :32-35
    - 對應 Web 元素:viewport clamp / 小型裝置上的 dialog 縮放策略
    - 套用建議:案件對話框超出螢幕時沿用 shrink-min-size 適配,確保完整可見。

15. **Workflow-first sidebar IA + 導覽與路由解耦 + badge 對稱**
    - DailyWork 契約特性（2026-08-31）:`_NAV_GROUPS` 四群組（供應商事件 / 倉庫不合格品 / 資料庫設定 / 系統）;供應商事件側欄四列 + 作業佇列頁 chips（逾期案件 / 根因待查 / 處置項目 / 案件總覽）;sidebar 只發 `nav_activated` signal;`MainWindow._PAGE_KEY_TO_INDEX` 路由;`事件查詢` badge 為未結案異常總數,佇列 chip `(N)` 用 `get_supplier_event_queue_counts`
    - 對應 Web 元素:nav rail IA、router 與導覽元件解耦、未處理數 badge
    - 套用建議:DailyWork 新增案件管理時,案件相關入口以作業類型分群並掛計數 badge,維持導覽與路由解耦。

> 以上為映射建議,實際改造由 DailyWork 專案另行決定。


---

## 第 8 章 附錄

### 8.1 A-1 §26 欄位對照表

> 基準:`docs/SQE_Incident_Management_Web_Architecture_Draft_v0.1.md` §26(行號為該文件實際行號)。全文件 ✓ 總數 120 = §26 表格列 ✓ **119** + §26 圖例行(行 1030「✓ = 2026-08-18 程式碼已存在」)**1**。下表逐列給落點;無落點或與元件衝突者填「VERIFY」並在 A-2 清單編號。
> 落點章節:「第 4 章」= 建立案件、「第 5 章」= 異常案件查詢、「第 6 章(…)」= 案件詳情對應 tab;「系統內部」= 無直接 UI,由 URL/關聯/API 使用。zh-TW 照抄 labels.ts / 元件實際字串;無 UI 標籤者以「—」標示。

| 欄位 key | zh-TW | 必填 | §26 行號 | 落點章節/VERIFY |
| --- | --- | --- | --- | --- |
| id | — | 系統 | 1034 | 系統內部(URL 使用) |
| case_number | 案件編號 | 必填 | 1035 | 第 6 章(案件概況);第 5 章;詳情頁 header |
| case_type | 案件類型 | 必填 | 1036 | 第 4 章;第 5 章(filter);第 6 章(案件概況) |
| source | 異常來源 | 必填 | 1037 | 第 4 章;第 5 章(filter);第 6 章(案件概況) |
| supplier_id | 供應商 | 必填 | 1038 | 第 4 章;第 5 章(filter);第 6 章(案件概況) |
| title | 異常摘要 | 必填 | 1039 | 第 4 章;第 5 章;第 6 章(案件概況) |
| defect_description | 不良描述 | 選填 | 1040 | 第 4 章;第 6 章(案件概況) |
| failure_mode | 不良模式 | 選填 | 1041 | 第 4 章;第 5 章(filter);第 6 章(案件概況) |
| part_number | 料號 | 選填 | 1042 | 第 4 章;第 5 章(filter);第 6 章(案件概況) |
| part_name | 品名 | 選填 | 1043 | 第 4 章;第 6 章(案件概況) |
| lot_no | 批號 Lot No. | 選填 | 1044 | 第 4 章(詳情頁無顯示) |
| po_no | PO | 選填 | 1045 | 第 4 章(詳情頁無顯示) |
| wo_no | 工單 WO | 選填 | 1046 | 第 4 章(詳情頁無顯示) |
| product_model | 產品／機種 | 選填 | 1047 | 第 4 章(詳情頁無顯示) |
| qty_received | 收料數量 | 選填 | 1057 | 第 4 章(詳情頁無顯示) |
| qty_inspected | 檢驗數量 | 選填 | 1058 | 第 4 章(詳情頁無顯示) |
| qty_ng | 不良數量 | 選填 | 1059 | 第 4 章(詳情頁無顯示) |
| defect_rate | 不良率 | 選填 | 1060 | 第 6 章(案件概況,計算值顯示) |
| severity | 嚴重程度 | 選填 | 1075 | 第 4 章;第 6 章(案件概況);詳情頁 header ⚠️ VERIFY(見 A-2 V-4) |
| detection_location | 發現位置 | 選填 | 1076 | 第 4 章(詳情頁無顯示) |
| sqe_owner_id | SQE 負責人 | 選填 | 1079 | 第 6 章(案件概況);詳情頁 header;第 5 章(filter) |
| status | 狀態 | 必填 | 1080 | 第 6 章(案件概況,含變更狀態);第 5 章(filter) |
| detected_at | 發現日期 | 必填 | 1081 | 第 4 章;第 5 章(查詢表格/篩選/sort) |
| opened_at | 建立時間 | 系統 | 1082 | 第 6 章(案件概況) |
| closed_at | 關案時間 | 系統 | 1083 | 第 6 章(案件概況) |
| closure_note | 結案說明 | 結案時必填 | 1084 | 第 6 章(案件概況,結案 dialog) |
| reopened_at | 重開時間 | 系統 | 1085 | 第 6 章(案件概況) |
| reopened_reason | 重開原因 | 重開時必填 | 1086 | 第 6 章(案件概況,重新開啟 dialog) |
| created_at / updated_at | 最後更新 | 系統 | 1087 | 第 6 章(案件概況);第 5 章 |
| created_by / updated_by | — | 系統 | 1088 | 間接顯示:第 6 章(處理歷程 actor / 變更紀錄操作者) |
| id | — | 系統 | 1096 | 系統內部 |
| name | —(顯示於多處) | 必填 | 1097 | 第 6 章(案件概況 SQE 負責人、處理歷程、異常分析、變更紀錄);第 5 章(filter 全部負責人) |
| email | — | 必填 | 1098 | VERIFY(見 A-2 V-5) |
| created_at / updated_at | — | 系統 | 1103 | VERIFY(見 A-2 V-6) |
| id | — | 系統 | 1109 | 系統內部(filter/表單值) |
| code | —(與名稱併顯) | 必填 | 1110 | 第 5 章(filter);第 4 章(選項 `{code} — {name}`) |
| name | 供應商 | 必填 | 1111 | 第 6 章(案件概況);第 5 章;第 4 章(選項) |
| created_at / updated_at | — | 系統 | 1125 | VERIFY(見 A-2 V-7) |
| id | — | 系統 | 1145 | 系統內部 |
| case_id | — | 必填 | 1146 | 系統內部(關聯) |
| description | 處置內容 | 必填 | 1147 | 第 6 章(案件概況:建立下一步處置 dialog / 目前處置);第 5 章(下一步處置欄) |
| owner | 負責人 | 選填 | 1148 | 第 6 章(案件概況,建立下一步處置 dialog) |
| due_date | 到期日 | 必填 | 1149 | 第 6 章(案件概況 dialog);第 5 章(sort dueDate) |
| status | 狀態 | 必填 | 1150 | 第 6 章(案件概況,ActionStatusBadge) |
| created_at | — | 系統 | 1151 | 系統內部 |
| completed_at | — | 系統 | 1152 | 第 6 章(案件概況,完成處置 dialog) |
| completion_note | 完成說明 | 完成時必填 | 1153 | 第 6 章(案件概況,完成處置 dialog) |
| cancelled_at | — | 系統 | 1154 | 第 6 章(案件概況,取消處置 dialog) |
| cancel_note | 取消原因 | 取消時必填 | 1155 | 第 6 章(案件概況,取消處置 dialog) |
| id | — | 系統 | 1165 | 系統內部 |
| case_id | — | 必填 | 1166 | 系統內部 |
| event_type | —(顯示原始 enum) | 必填 | 1167 | 第 6 章(處理歷程)(原始 enum 直接顯示,無 zh-TW 對照) |
| description | —(事件描述) | 必填 | 1168 | 第 6 章(處理歷程) |
| actor_id | —(actor 名稱) | 選填 | 1169 | 第 6 章(處理歷程) |
| created_at | —(日期) | 系統 | 1170 | 第 6 章(處理歷程) |
| id | — | 系統 | 1178 | 系統內部 |
| case_id | — | 必填 | 1179 | 系統內部 |
| content | 分析紀錄 | 必填 | 1180 | 第 6 章(異常分析,新增紀錄 + 列表顯示) |
| evidence_type | 證據分類 | 選填 | 1181 | 第 6 章(異常分析) |
| author_id | —(作者) | 系統 | 1183 | 第 6 章(異常分析) |
| created_at | —(日期) | 系統 | 1184 | 第 6 章(異常分析) |
| id | — | 系統 | 1190 | 系統內部 |
| case_id | — | 必填 | 1191 | 系統內部(1:1) |
| statement | Root Cause 說明 | 依狀態 | 1192 | 第 6 章(異常分析) |
| status | 狀態 | 必填 | 1193 | 第 6 章(異常分析);第 6 章(案件概況,RootCauseStatusBadge) |
| validation_method | 驗證方式 | 選填 | 1194 | 第 6 章(異常分析) |
| validation_evidence | 驗證證據 | 選填 | 1195 | 第 6 章(異常分析) |
| conclusion_note | 結論說明 | 選填 | 1196 | 第 6 章(異常分析) |
| not_established_reason | 無法確認原因說明 | Not Established 時必填 | 1197 | 第 6 章(異常分析) |
| updated_at | — | 系統 | 1199 | 系統內部(表單 key 用 rc.updatedAt) |
| updated_by | — | 系統 | 1200 | VERIFY(見 A-2 V-8) |
| id | — | 系統 | 1212 | 系統內部 |
| case_id | — | 必填 | 1213 | 系統內部 |
| description | 措施內容 | 必填 | 1214 | 第 6 章(改善措施,建立表單 + CA 卡片) |
| responsible_party | 負責單位／人員 | 選填 | 1215 | 第 6 章(改善措施) |
| target_date | 預計完成日 | 選填 | 1216 | 第 6 章(改善措施) |
| completion_date | 實際完成日 | 完成時 | 1217 | 第 6 章(改善措施,完成 dialog) |
| status | 狀態 | 必填 | 1218 | 第 6 章(改善措施,CaStatusBadge + 狀態更新);第 6 章(案件概況) |
| implementation_evidence | 執行證據 | Implemented 時建議 | 1219 | 第 6 章(改善措施,完成 dialog + 卡片顯示) |
| effectiveness_verification_required | 需進行有效性驗證 | 必填(預設 false) | 1220 | 第 6 章(改善措施,checkbox) |
| notes | 備註 | 選填 | 1221 | 第 6 章(改善措施) |
| created_at / updated_at | — | 系統 | 1224 | 系統內部 |
| id | — | 系統 | 1230 | 系統內部 |
| corrective_action_id | — | 必填 | 1231 | 系統內部 |
| method | 驗證方式 | 選填 | 1232 | 第 6 章(改善措施,記錄驗證結果 dialog + 顯示) |
| acceptance_criteria | 接受標準 | 選填 | 1233 | 第 6 章(改善措施) |
| period_sample | 驗證期間／樣本 | 選填 | 1234 | 第 6 章(改善措施) |
| result | 驗證結果 | 必填 | 1235 | 第 6 章(改善措施,VerificationResultBadge);第 6 章(案件概況) |
| evidence | 驗證證據 | 選填 | 1236 | 第 6 章(改善措施) |
| conclusion | 驗證結論 | 選填 | 1237 | 第 6 章(改善措施) |
| verified_by | — | 系統 | 1238 | VERIFY(見 A-2 V-9) |
| verified_date | 驗證日期 | 系統 | 1239 | 第 6 章(改善措施,VerificationPanel) |
| created_at / updated_at | — | 系統 | 1240 | 系統內部 |
| id | — | 系統 | 1249 | 系統內部(下載 URL /api/attachments/{id}) |
| case_id | — | 必填 | 1250 | 系統內部 |
| file_name | 檔案名稱 | 必填 | 1251 | 第 6 章(附件,檔名連結);第 6 章(Supplier 8D,審查紀錄附件連結) |
| stored_name | — | 系統 | 1252 | VERIFY(見 A-2 V-10) |
| category | 附件分類 | 必填 | 1253 | 第 6 章(附件,上傳 dialog + 列表) |
| description | 說明 | 選填 | 1254 | 第 6 章(附件) |
| file_size | 檔案大小 | 系統 | 1255 | 第 6 章(附件,formatBytes) |
| file_type | — | 系統 | 1256 | VERIFY(見 A-2 V-11) |
| revision | 版本 | 選填 | 1258 | 第 6 章(附件,「Rev {revision}」) |
| uploaded_by | — | 系統 | 1259 | VERIFY(見 A-2 V-12) |
| uploaded_at | 上傳時間 | 系統 | 1260 | 第 6 章(附件,formatDate) |
| id | — | 系統 | 1270 | 系統內部 |
| case_id | — | 必填 | 1271 | 系統內部 |
| attachment_id | 附件 | 選填 | 1272 | 第 6 章(Supplier 8D,新增審查 dialog + 審查紀錄連結) |
| revision | 版本 | 必填 | 1273 | 第 6 章(Supplier 8D) |
| review_status | 審查結果 | 必填 | 1274 | 第 6 章(Supplier 8D,EightDReviewStatusBadge) |
| review_comment | 審查意見 | 選填 | 1275 | 第 6 章(Supplier 8D) |
| reviewer_id | — | 系統 | 1276 | VERIFY(見 A-2 V-13) |
| review_date | 審查日期 | 系統 | 1277 | 第 6 章(Supplier 8D,formatDate) |
| id | — | 系統 | 1287 | 系統內部 |
| entity_type | — | 必填 | 1288 | VERIFY(見 A-2 V-14) |
| entity_id | — | 必填 | 1289 | VERIFY(見 A-2 V-15) |
| action | 動作 | 必填 | 1290 | 第 6 章(變更紀錄) |
| before_value / after_value | 變更前 / 變更後 | 選填 | 1291 | 第 6 章(變更紀錄) |
| user_id | —(操作者) | 系統 | 1292 | 第 6 章(變更紀錄,user.name) |
| created_at | 日期 | 系統 | 1293 | 第 6 章(變更紀錄) |

> 註:§26.3 SUPPLIER CONTACT、§26.13-15(CASE COST / CASE LINK / ESCALATION)為 Phase 2,無 ✓ 旗標,不列入對照表。


### 8.2 A-2 VERIFY 清單

> 每項含「證據命令 / 觀測值 / 權威值 / 檔案路徑」四件套。只記錄事實,不臆測何者正確;由文件維護者(或對應 repo 負責人)裁決。
> V-1 至 V-3 為 DailyWork 契約 vs 實作不一致(來源 T2);V-4 為架構 §26 與 Web 元件衝突(來源 T1);V-5 至 V-15 為 §26 標記 ✓ 但 UI 未顯示的欄位(來源 T1)。DailyWork 路徑相對於 `C:\Users\user\Documents\SQE DailyWork\`;Web 路徑相對於 `C:\Users\user\Documents\SQE Website\sqe-incident-manager\`。

**V-1 font-weight 600 殘留(9 處,契約宣稱僅 400/700)**

**裁決(2026-08-19)**: 依語意對照表收斂(非強調→400、強調→700)。(commit dc0dae0)

- 證據命令:`Select-String -Path src\ui\_qss_controls.py,src\ui\_qss_data_widgets.py -Pattern "font-weight:\s*600"`(PowerShell 等價 grep)
- 觀測值:9 處命中:`_qss_controls.py:107`、`:137`、`:168`、`:186`、`:250`、`:275`、`:314`、`:330`(8 處);`_qss_data_widgets.py:65`(1 處);`font-weight: 500` 0 命中
- 權威值:`docs/ui-layout-theme-contract.md:254-255` 宣稱「Live Qt QSS now uses only `font-weight` 400/700 (no 500/600)」
- 檔案路徑:`C:\Users\user\Documents\SQE DailyWork\src\ui\_qss_controls.py:107` 等(細節見 dailywork-advantages.md §4)

**V-2 側欄群組間距雙重定義(實作用 14,契約宣稱 10 由 layout_constants 管理)**

**裁決(2026-08-19)**: 改用 layout_constants.SIDEBAR_NAV_GROUP_GAP=10。(commit c9f7280)

- 證據命令:`Select-String -Path src\ui\sidebar_nav.py,src\ui\layout_constants.py -Pattern "NAV_GROUP_GAP"`
- 觀測值:`sidebar_nav.py:32` 本地 `_NAV_GROUP_GAP = 14`,使用於 `:246`(addSpacing);`layout_constants.py:57` `SIDEBAR_NAV_GROUP_GAP = 10` 已定義但 sidebar_nav.py import 清單(:20-28)未含此常數
- 權威值:`docs/ui-layout-theme-contract.md:163-164` 宣稱「導覽項目高度為 38px,群組間距為 10px;數值均由 `layout_constants.py` 管理」
- 檔案路徑:`C:\Users\user\Documents\SQE DailyWork\src\ui\sidebar_nav.py:32、:246`;`C:\Users\user\Documents\SQE DailyWork\src\ui\layout_constants.py:57`

**V-3 事件清單初始 page size 12 vs PaginationBar 預設 13**

**裁決(2026-08-19)**: 新增中性常數 EVENT_LIST_ITEMS_PER_PAGE=12。(commit aec411c)

- 證據命令:`Select-String -Path src\ui\widgets\defect_list_widget.py -Pattern "_page_size = ";Select-String -Path src\ui\widgets\pagination_bar.py -Pattern "default_page_size"`
- 觀測值:`defect_list_widget.py:101` `self._page_size = 12`;`pagination_bar.py:31` `default_page_size: int = 13`、`:32` `page_size_options = (10, 13, 20, 50, 100)`;`layout_constants.py:228` `NCR_ITEMS_PER_PAGE = 12`
- 權威值:契約未明文宣稱分頁預設值須一致;兩處定義(12 vs 13)不一致,事件清單實際生效值需查呼叫端是否覆寫
- 檔案路徑:`C:\Users\user\Documents\SQE DailyWork\src\ui\widgets\defect_list_widget.py:101`;`C:\Users\user\Documents\SQE DailyWork\src\ui\widgets\pagination_bar.py:31-32`

**V-4 severity 值域衝突:§26「Critical/Major/Minor」vs 元件「Low/Medium/High/Critical」**

- 證據命令:`Select-String -Path docs\SQE_Incident_Management_Web_Architecture_Draft_v0.1.md -Pattern "severity";Select-String -Path src\components\cases\new-case-form.tsx -Pattern "Critical|Major|Minor"`
- 觀測值:架構 §26 主表 `severity` 說明為「品質影響程度(Critical/Major/Minor)」(:1075);元件選項為 Low/Medium/High/Critical(new-case-form.tsx:34、:246-262);SeverityBadge 樣式表同為 Low/Medium/High/Critical(status-badges.tsx:249-254);labels.ts:6 註明 severity 不翻譯
- 權威值:`docs/SQE_Incident_Management_Web_Architecture_Draft_v0.1.md:1075`(severity 欄說明)為架構方宣稱;實際元件以 Low/Medium/High/Critical 為準,架構 §26 說明需更新
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\cases\new-case-form.tsx:34`;`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\status-badges.tsx:249-254`;`C:\Users\user\Documents\SQE Website\docs\SQE_Incident_Management_Web_Architecture_Draft_v0.1.md:1075`

**V-5 USER.email 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components,src\lib -Pattern "email"`(於 sqe-incident-manager)
- 觀測值:`email` 僅命中 `lib/current-user.ts:10、:19、:21`(種子使用者,非 UI 顯示);無 UI 元件顯示使用者電子郵件
- 權威值:架構 §26.1 `:1098` `email` String unique 必填 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\lib\current-user.ts:10` 等

**V-6 USER created_at / updated_at 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components -Pattern "user.createdAt|user.updatedAt"`(於 sqe-incident-manager)
- 觀測值:無元件顯示 User 實體時間戳;各元件僅顯示 case/action/note 層級時間
- 權威值:架構 §26.1 `:1103` `created_at / updated_at` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\overview-tab.tsx:79-88`(顯示的是案件層級時間,非 User 實體)

**V-7 SUPPLIER created_at / updated_at 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components -Pattern "supplier.createdAt|supplier.updatedAt"`(於 sqe-incident-manager)
- 觀測值:無元件顯示 Supplier 實體時間戳;供應商相關 UI 僅用 id/code/name
- 權威值:架構 §26.2 `:1125` `created_at / updated_at` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\cases\case-filter-bar.tsx:170-173`(僅 id/code/name)

**V-8 ROOT CAUSE updated_by 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components\case-detail\investigation-tab.tsx -Pattern "updatedBy"`
- 觀測值:元件無顯示 RootCause updated_by;表單 key 僅用 `rc.updatedAt`(investigation-tab.tsx:133)
- 權威值:架構 §26.7 `:1200` `updated_by` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\investigation-tab.tsx:133`

**V-9 EFFECTIVENESS VERIFICATION verified_by 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components\case-detail\corrective-actions-tab.tsx -Pattern "verifiedBy"`
- 觀測值:元件無顯示 verified_by 名稱;VerificationPanel 僅顯示驗證日期(verifyDate)
- 權威值:架構 §26.9 `:1238` `verified_by` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\corrective-actions-tab.tsx:287-291`(僅驗證日期)

**V-10 ATTACHMENT stored_name 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src -Pattern "storedName"`
- 觀測值:`storedName` 僅命中 `lib/actions/attachments.ts:53、:61、:124`、`lib/storage/storage.ts:22、:29`、`app/api/attachments/[id]/route.ts:38`,全部為 storage/actions/API,無 UI 顯示
- 權威值:架構 §26.10 `:1252` `stored_name` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\lib\actions\attachments.ts:53` 等

**V-11 ATTACHMENT file_type 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src -Pattern "fileType"`
- 觀測值:`fileType` 僅命中 `lib/actions/attachments.ts:65`、`app/api/attachments/[id]/route.ts:43`(上傳/API content-type 使用),無 UI 顯示
- 權威值:架構 §26.10 `:1256` `file_type` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\lib\actions\attachments.ts:65`;`C:\Users\user\Documents\SQE Website\sqe-incident-manager\app\api\attachments\[id]\route.ts:43`

**V-12 ATTACHMENT uploaded_by 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components\case-detail\attachments-tab.tsx -Pattern "uploadedBy"`
- 觀測值:元件無顯示上傳者名稱;附件列表僅顯示檔名/分類/版本/大小/上傳時間(attachments-tab.tsx:104-158)
- 權威值:架構 §26.10 `:1259` `uploaded_by` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\attachments-tab.tsx:104-158`

**V-13 SUPPLIER 8D REVIEW reviewer_id 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components\case-detail\eight-d-tab.tsx -Pattern "reviewer"`
- 觀測值:元件無顯示 reviewer 名稱;審查紀錄列表僅顯示版本/狀態/意見/日期/附件連結(eight-d-tab.tsx:34-71)
- 權威值:架構 §26.11 `:1276` `reviewer_id` 系統 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\eight-d-tab.tsx:34-71`

**V-14 AUDIT LOG entity_type 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components\case-detail\history-tab.tsx -Pattern "entityType"`
- 觀測值:history 表格無此欄;表頭僅 動作/變更前/變更後/操作者/日期(history-tab.tsx:30-34)
- 權威值:架構 §26.12 `:1288` `entity_type` 必填 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\history-tab.tsx:30-34`

**V-15 AUDIT LOG entity_id 已實作 ✓ 但 UI 未顯示**

- 證據命令:`Select-String -Path src\components\case-detail\history-tab.tsx -Pattern "entityId"`
- 觀測值:history 表格無此欄;表頭僅 動作/變更前/變更後/操作者/日期(history-tab.tsx:30-34)
- 權威值:架構 §26.12 `:1289` `entity_id` 必填 MVP ✓「已實作」
- 檔案路徑:`C:\Users\user\Documents\SQE Website\sqe-incident-manager\src\components\case-detail\history-tab.tsx:30-34`


## 維護註記 (Maintenance Notes)

**裁決日期**: 2026-08-19

本文件中 A-2 節的三項契約不一致(V-1/V-2/V-3)已於 SQE DailyWork 專案中裁決並修正：

- **V-1 字重 600 收斂**：`_qss_controls.py` 8 處 + `_qss_data_widgets.py` 1 處已依語意對照表收斂為 400(非強調)或 700(強調)。Commit: `dc0dae0`
- **V-2 側欄群組間距**：`sidebar_nav.py` 改為 import `layout_constants.SIDEBAR_NAV_GROUP_GAP`(10px)，刪除本地 `_NAV_GROUP_GAP=14`。Commit: `c9f7280`
- **V-3 事件清單分頁**：`layout_constants.py` 新增中性常數 `EVENT_LIST_ITEMS_PER_PAGE=12`，`defect_list_widget.py` 引用。Commit: `aec411c`

**未裁決項目**: V-4~V-15 屬 SQE Website 專案，不在本專案處理。

**其他說明**:
- `.omo/notepads/ui-design-framework/` 參照在本 repo 不存在，視為歷史紀錄。
- 絕對路徑(如 `C:\Users\user\...`)為機器特定，僅供參考。
