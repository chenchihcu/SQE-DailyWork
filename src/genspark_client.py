"""
Genspark AI Integration Module
透過 Genspark API 調用 AI 模型的 Python 包裝器
"""

import os
import json
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path


class GensparkClient:
    """Genspark API 客戶端"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Genspark 客戶端
        
        Args:
            api_key: Genspark API 金鑰（可從環境變數 GENSPARK_API_KEY 取得）
        """
        self.api_key = api_key or os.getenv("GENSPARK_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API Key 未設定。請設置 GENSPARK_API_KEY 環境變數或在初始化時提供"
            )
    
    def query_with_cli(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        使用 Genspark CLI 進行查詢
        
        Args:
            query: 查詢文本
            **kwargs: 其他選項
            
        Returns:
            API 回應
        """
        try:
            # 使用 Genspark CLI 進行查詢
            cmd = ["genspark", "search", query]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GENSPARK_API_KEY": self.api_key}
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr,
                    "message": f"Genspark CLI 錯誤: {result.stderr}"
                }
            
            # 解析 CLI 輸出
            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError:
                response = {"success": True, "data": result.stdout}
            
            return response
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "查詢超時",
                "message": "Genspark API 請求超時"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"查詢失敗: {str(e)}"
            }
    
    def query_ai_model(self, prompt: str, model: str = "auto") -> Dict[str, Any]:
        """
        查詢 Genspark AI 模型
        
        Args:
            prompt: 提示文本
            model: 模型名稱 (預設: auto)
            
        Returns:
            AI 回應
        """
        try:
            cmd = [
                "genspark",
                "chat",
                "--prompt", prompt,
                "--model", model
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "GENSPARK_API_KEY": self.api_key}
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr
                }
            
            return {
                "success": True,
                "response": result.stdout
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# 使用範例
if __name__ == "__main__":
    import sys
    
    # 初始化客戶端
    try:
        client = GensparkClient()
    except ValueError as e:
        print(f"錯誤: {e}")
        print("請先設置 GENSPARK_API_KEY 環境變數")
        sys.exit(1)
    
    # 搜尋範例
    print("=" * 50)
    print("Genspark 搜尋測試")
    print("=" * 50)
    
    query = "什麼是人工智慧"
    print(f"\n查詢: {query}")
    result = client.query_with_cli(query)
    print(f"結果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
    # AI 模型查詢範例
    print("\n" + "=" * 50)
    print("Genspark AI 模型測試")
    print("=" * 50)
    
    prompt = "請簡要解釋什麼是機器學習"
    print(f"\n提示: {prompt}")
    result = client.query_ai_model(prompt)
    print(f"結果: {json.dumps(result, ensure_ascii=False, indent=2)}")
