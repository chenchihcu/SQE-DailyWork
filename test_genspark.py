#!/usr/bin/env python3
"""
Genspark API 測試腳本
用來驗證 Genspark 整合是否正常運作
"""

import os
import sys
import json
from pathlib import Path

# 新增專案路徑
_repo_root = Path(__file__).resolve().parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.genspark_client import GensparkClient


def print_section(title):
    """印出分隔符"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_genspark_integration():
    """測試 Genspark 整合"""
    
    print_section("🧪 Genspark AI 整合測試")
    
    # 1. 檢查環境變數
    print("\n📝 步驟 1: 檢查環境變數...")
    api_key = os.getenv("GENSPARK_API_KEY")
    if api_key:
        print(f"✅ API Key 已設置: {api_key[:10]}...")
    else:
        print("❌ GENSPARK_API_KEY 環境變數未設置")
        print("   請執行: set GENSPARK_API_KEY=your_api_key")
        return False
    
    # 2. 檢查 Genspark CLI
    print("\n📝 步驟 2: 檢查 Genspark CLI...")
    import subprocess
    try:
        result = subprocess.run(
            ["genspark", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Genspark CLI 已安裝: 版本 {version}")
        else:
            print("❌ Genspark CLI 檢查失敗")
            print(f"   錯誤: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Genspark CLI 未找到")
        print("   請執行: npm install -g @genspark/cli")
        return False
    except Exception as e:
        print(f"❌ CLI 檢查出錯: {e}")
        return False
    
    # 3. 初始化客戶端
    print("\n📝 步驟 3: 初始化 Genspark 客戶端...")
    try:
        client = GensparkClient()
        print("✅ 客戶端初始化成功")
    except Exception as e:
        print(f"❌ 客戶端初始化失敗: {e}")
        return False
    
    # 4. 測試搜尋功能
    print("\n📝 步驟 4: 測試搜尋功能...")
    test_query = "Python 程式設計"
    print(f"   執行查詢: \"{test_query}\"")
    
    try:
        result = client.query_with_cli(test_query)
        if result.get("success", False):
            print("✅ 搜尋成功")
            print(f"   結果類型: {type(result.get('data', {}))}")
        else:
            print("⚠️  搜尋返回錯誤")
            print(f"   錯誤: {result.get('error', '未知')}")
            if "unknown command" in result.get("error", "").lower():
                print("   💡 提示: Genspark CLI 可能不支持此命令")
                print("   請檢查 CLI 版本或使用官方文檔")
    except Exception as e:
        print(f"❌ 搜尋失敗: {e}")
    
    # 5. 測試 AI 模型
    print("\n📝 步驟 5: 測試 AI 模型功能...")
    test_prompt = "AI 是什麼？"
    print(f"   執行提示: \"{test_prompt}\"")
    
    try:
        result = client.query_ai_model(test_prompt)
        if result.get("success", False):
            print("✅ AI 查詢成功")
            response = result.get('response', '')
            if response:
                print(f"   回應（前 200 字元）: {response[:200]}...")
            else:
                print("   ⚠️  收到空回應")
        else:
            print("⚠️  AI 查詢返回錯誤")
            print(f"   錯誤: {result.get('error', '未知')}")
    except Exception as e:
        print(f"❌ AI 查詢失敗: {e}")
    
    # 完成
    print_section("✨ 測試完成")
    print("\n💡 下一步:")
    print("   1. 使用 src/genspark_client.py 進行 Python 整合")
    print("   2. 在 PySide6 中使用 src/genspark_widget.py")
    print("   3. 參考 GENSPARK_INTEGRATION.md 了解更多")
    
    return True


if __name__ == "__main__":
    try:
        success = test_genspark_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ 測試被中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 意外錯誤: {e}")
        sys.exit(1)
