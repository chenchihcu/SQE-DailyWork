# SQE DailyWork — 視覺證據政策(Visual Evidence Policy,單一真相來源)

> 本檔是本專案「什麼算/不算視覺證據」與 CJK 字重政策的唯一正本。
> 消費端(`sqe-dailywork-change-router`、`sqe-dailywork-visual-qa`、`sqe-dailywork-qt-visual-reviewer`)以指標引用本檔,不重述政策文字。

## 1. 視覺證據(Visual Evidence)

1. **Playwright 與任何瀏覽器/web 工具都不是本 PySide6 桌面應用的視覺證據。**
   視覺/字體/CJK/截圖判斷一律用原生 Windows Qt:`scripts\qt_visual_probe.py`(自動強制 `QT_QPA_PLATFORM=windows`)。
2. **`QT_QPA_PLATFORM=offscreen` 只算結構性煙霧測試(structural smoke),永遠不是視覺證據**(可能漏掉 Windows CJK 字型、渲染方框)。
3. 視覺宣稱的操作細節(probe targets、多 DPI、JSON 自檢欄位、11 維檢查表)見 `.claude/skills/sqe-dailywork-visual-qa/SKILL.md` —— 該檔負責「怎麼驗」,本檔負責「什麼算證據」。

## 2. CJK 字重(Font Weight)

- **Live Qt QSS 只用 `font-weight` 400 與 700,不用 500/600**(Windows 對 CJK 中間字重渲染不一致)。
- **正本出處**:Institution 通用 UI/UX 規則 §6 —— `C:\Dropbox\AI_Coding_Agent_Governance\Institution\06-ui-ux-universal.md`
  (「CJK 字重優先用 `400` 與 `700`,避免 `500` / `600`(Windows 渲染不一致)」);本檔為其專案執行層。
- **機械防線**:`tests/test_font_source_single_truth.py` 與 `tests/test_theme_typography_consistency.py` 釘住本規則與單一字型來源(`src/ui/theme.py` 的 `PREFERRED_CJK_FONT_FAMILIES`)。

## 3. Hook 字面副本同步紀律

第 1 條政策在機械防線層有兩份**字面訊息字串**(hook 於觸發期無法讀 markdown):

- `.claude/hooks/sqe-dailywork-pre-tool-use.ps1`(Playwright+視覺關鍵詞 → block 訊息,內嵌字串)
- `.claude/hooks/sqe-dailywork-route-keywords.json` 的 `promptReminders[ui].message`(由 `sqe-dailywork-user-prompt-submit.ps1` 讀取)

**修改本檔第 1 條政策文字時,須同批更新上述兩處訊息字串**(對應檔內有註解)。
