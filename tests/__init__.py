import os
import sys
from pathlib import Path

# 確保 src 目錄在 sys.path 中，使直接執行 python -m unittest 能正確引用模組
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# 全域確保單元測試以 offscreen 模式執行，避免彈出 GUI 視窗或 Windows Message Loop 阻塞進程
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SQE_TESTING", "1")

try:
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    _app.setStyle("Fusion")
except Exception:
    pass
