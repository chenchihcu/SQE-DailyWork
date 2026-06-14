# 🤖 Genspark AI 整合指南

## 📦 安裝步驟

### 1. 安裝 Genspark CLI（全局）
```bash
npm install -g @genspark/cli
```

### 2. 驗證安裝
```bash
genspark --version
```

### 3. 安裝 Python 依賴
```bash
pip install -r requirements.txt
```

## 🔑 配置 API 金鑰

### 獲取 API 金鑰
1. 訪問 [Genspark 官網](https://www.genspark.ai/)
2. 註冊/登錄帳戶
3. 進入 API 設置頁面
4. 複製你的 API 金鑰

### 設置環境變數

#### 選項 A：使用 .env 文件（推薦）
```bash
# 複製範例檔案
cp .env.example .env

# 編輯 .env，填入你的 API 金鑰
GENSPARK_API_KEY=your_actual_api_key_here
```

#### 選項 B：直接設置系統環境變數

**Windows (PowerShell):**
```powershell
$env:GENSPARK_API_KEY = "your_api_key_here"
```

**Windows (命令提示字元):**
```cmd
set GENSPARK_API_KEY=your_api_key_here
```

**Linux/Mac:**
```bash
export GENSPARK_API_KEY="your_api_key_here"
```

## 🚀 使用方式

### 方法 1：Python 程式碼中使用

```python
from src.genspark_client import GensparkClient

# 初始化客戶端
client = GensparkClient()

# 搜尋查詢
search_result = client.query_with_cli("Python 教學")
print(search_result)

# AI 模型查詢
chat_result = client.query_ai_model("什麼是機器學習？")
print(chat_result)
```

### 方法 2：PySide6 UI 中使用

```python
from src.genspark_widget import GensparkWidget
from PySide6.QtWidgets import QApplication

app = QApplication([])
widget = GensparkWidget(api_key="your_api_key")  # 可選，會從環境變數讀取
# 在你的主視窗中添加此 widget
```

### 方法 3：直接使用 CLI

```bash
# 搜尋
genspark search "你的查詢"

# 聊天
genspark chat --prompt "你的問題" --model auto
```

## 📂 整合文件

### 新建檔案
- **`src/genspark_client.py`** - Genspark API Python 包裝器
- **`src/genspark_widget.py`** - PySide6 UI 元件
- **`package.json`** - Node.js 依賴配置
- **`.env.example`** - 環境變數範例

### 修改檔案
- **`requirements.txt`** - 新增 `requests` 和 `python-dotenv`

## 🎯 使用範例

### 簡單搜尋
```python
from src.genspark_client import GensparkClient

client = GensparkClient()
result = client.query_with_cli("最新的 AI 技術")
print(result)
```

**輸出:**
```json
{
  "success": true,
  "data": [
    {
      "title": "...",
      "url": "...",
      "snippet": "..."
    }
  ]
}
```

### AI 模型對話
```python
response = client.query_ai_model(
    prompt="請解釋什麼是深度學習",
    model="auto"
)
print(response['response'])
```

## ⚙️ 高級配置

### 自訂超時時間
所有 CLI 子程序都集中在 `src/genspark_client.py` 的 `_run_genspark()`
helper 執行；逾時由各查詢方法呼叫時帶入（搜尋 `query_with_cli` 為 30 秒、
AI 對話 `query_ai_model` 為 60 秒）。調整對應方法傳給 `_run_genspark(...)`
的 `timeout` 秒數即可：

```python
def _run_genspark(self, cmd, *, timeout):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,  # 秒，由各查詢方法帶入
        env={**os.environ, "GENSPARK_API_KEY": self.api_key},
    )
```

### 加入代理設置
子程序環境變數統一在 `_run_genspark()` 內組裝，於該處加入代理設定即可
套用到所有查詢：

```python
def _run_genspark(self, cmd, *, timeout):
    env = {
        **os.environ,
        "GENSPARK_API_KEY": self.api_key,
        "HTTP_PROXY": "http://proxy.example.com:8080",
        "HTTPS_PROXY": "http://proxy.example.com:8080",
    }
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, env=env
    )
```

## 🔧 故障排除

### 錯誤：API Key 未設置
```
ValueError: API Key 未設定
```
**解決方案：** 確保設置了 `GENSPARK_API_KEY` 環境變數

### 錯誤：Genspark CLI 不存在
```
FileNotFoundError: [Errno 2] No such file or directory: 'genspark'
```
**解決方案：** 重新安裝 CLI
```bash
npm install -g @genspark/cli
```

### 錯誤：連接超時
**解決方案：** 增加超時時間或檢查網絡連接

### 找不到 genspark_client 模組
**解決方案：** 確保運行位置在專案根目錄，或檢查 Python 路徑

## 📚 API 文檔

### GensparkClient 方法

#### `query_with_cli(query: str) -> Dict`
執行搜尋查詢

**參數：**
- `query` (str): 搜尋文本

**返回值：** 成功時固定回傳 `success=True` 與 `data`；`data` 為 CLI 輸出
解析後的 JSON,無法解析時則為原始輸出字串。

```python
# 成功
{
    "success": True,
    "data": list | dict | str,  # 解析後 JSON,否則為原始輸出字串
}

# 失敗（CLI 非零退出 / 逾時 / 例外）
{
    "success": False,
    "error": str,    # 錯誤摘要
    "message": str,  # 人類可讀說明
}
```

#### `query_ai_model(prompt: str, model: str) -> Dict`
查詢 AI 模型

**參數：**
- `prompt` (str): 提示文本
- `model` (str, 預設="auto"): 模型名稱

**返回值：**
```python
# 成功
{
    "success": True,
    "response": str,  # AI 回應（CLI 原始輸出）
}

# 失敗
{
    "success": False,
    "error": str,    # 錯誤摘要
    "message": str,  # 逾時等情況附帶的人類可讀說明（非必有）
}
```

## 🔐 安全建議

1. **不要在代碼中硬編碼 API 金鑰**
   - 使用環境變數或 `.env` 文件
   - 不要提交 `.env` 到版本控制

2. **定期輪換 API 金鑰**
   - 在 Genspark 設置頁面定期更新

3. **限制 API 使用**
   - 在 Genspark 儀表板設置使用限制

## 📝 更多資源

- [Genspark 官方網站](https://www.genspark.ai/)
- [Genspark CLI NPM 套件](https://www.npmjs.com/package/@genspark/cli)
- [Genspark API 文檔](https://docs.genspark.ai/)

---

**最後更新：** 2026-06-07
