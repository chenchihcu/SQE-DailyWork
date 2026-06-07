"""
Genspark AI 集成 - PySide6 UI 元件
在 QApplication 中使用 Genspark API
"""

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QComboBox
)
from PySide6.QtCore import QThread, Signal

# 確保能導入 genspark_client
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from genspark_client import GensparkClient


class GensparkWorker(QThread):
    """背景執行緒 - 處理 Genspark API 請求。

    注意：自訂訊號命名為 result_ready，避免覆寫 QThread 內建的 finished
    訊號（內建 finished 仍可用於 deleteLater 等生命週期清理）。
    """

    result_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, client: GensparkClient, query_type: str, query_text: str):
        super().__init__()
        self.client = client
        self.query_type = query_type
        self.query_text = query_text

    def run(self):
        try:
            if self.query_type == "search":
                result = self.client.query_with_cli(self.query_text)
            elif self.query_type == "chat":
                result = self.client.query_ai_model(self.query_text)
            else:
                result = {"success": False, "error": "未知的查詢類型"}

            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class GensparkWidget(QWidget):
    """Genspark AI 整合 UI 元件"""
    
    def __init__(self, api_key: str = None):
        super().__init__()
        
        try:
            self.client = GensparkClient(api_key)
        except ValueError as e:
            self.client = None
            self.error_message = str(e)
        
        self.worker = None
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        
        # 標題
        title = QLabel("🤖 Genspark AI 助手")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # 查詢類型選擇
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("查詢類型:"))
        self.query_type = QComboBox()
        self.query_type.addItems(["搜尋 (Search)", "聊天 (Chat)"])
        type_layout.addWidget(self.query_type)
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # 輸入框
        input_label = QLabel("輸入查詢:")
        layout.addWidget(input_label)
        
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("輸入你的查詢或問題...")
        self.input_text.returnPressed.connect(self.execute_query)
        layout.addWidget(self.input_text)
        
        # 按鈕區域
        button_layout = QHBoxLayout()
        
        self.submit_btn = QPushButton("執行查詢")
        self.submit_btn.clicked.connect(self.execute_query)
        self.submit_btn.setEnabled(self.client is not None)
        button_layout.addWidget(self.submit_btn)
        
        self.clear_btn = QPushButton("清除")
        self.clear_btn.clicked.connect(self.clear_output)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        # 輸出區域
        output_label = QLabel("結果:")
        layout.addWidget(output_label)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)
        layout.addWidget(self.output_text)
        
        # 狀態標籤
        self.status_label = QLabel()
        self.update_status()
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def execute_query(self):
        """執行查詢"""
        if self.client is None:
            self.output_text.setText(f"❌ 錯誤: {self.error_message}")
            return

        # 防重入：上一筆查詢仍在執行時忽略（避免覆蓋仍在執行的 worker 參照而 crash）。
        if self.worker is not None and self.worker.isRunning():
            return

        query_text = self.input_text.text().strip()
        if not query_text:
            self.output_text.setText("請輸入查詢內容")
            return
        
        # 禁用按鈕，顯示處理中
        self.submit_btn.setEnabled(False)
        self.output_text.setText("⏳ 處理中...")
        
        # 確定查詢類型
        query_type = "search" if self.query_type.currentIndex() == 0 else "chat"
        
        # 在背景執行緒中執行查詢
        self.worker = GensparkWorker(self.client, query_type, query_text)
        self.worker.result_ready.connect(self.on_result)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
    
    def on_result(self, result: dict):
        """處理查詢結果"""
        self.submit_btn.setEnabled(True)
        
        if result.get("success", False):
            output = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            output = f"❌ 查詢失敗\n\n錯誤: {result.get('error', '未知錯誤')}\n訊息: {result.get('message', '')}"
        
        self.output_text.setText(output)
        self.update_status("✅ 完成")
    
    def on_error(self, error: str):
        """處理錯誤"""
        self.submit_btn.setEnabled(True)
        self.output_text.setText(f"❌ 錯誤: {error}")
        self.update_status("❌ 失敗")

    def _on_worker_finished(self):
        """執行緒結束後排程釋放 worker 並清空參照，避免重入時覆蓋仍在執行的執行緒。"""
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
    
    def clear_output(self):
        """清除輸出"""
        self.input_text.clear()
        self.output_text.clear()
        self.update_status()
    
    def update_status(self, status: str = None):
        """更新狀態"""
        if self.client is None:
            self.status_label.setText("⚠️ API 金鑰未設置")
            self.status_label.setStyleSheet("color: red;")
        elif status:
            self.status_label.setText(status)
        else:
            self.status_label.setText("✅ 就緒")
            self.status_label.setStyleSheet("color: green;")


# 使用範例
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Genspark AI 整合示例")
    window.setGeometry(100, 100, 800, 600)
    
    # 建立 Genspark Widget
    widget = GensparkWidget()
    window.setCentralWidget(widget)
    
    window.show()
    sys.exit(app.exec())
