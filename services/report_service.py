from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class ReportWorker(QThread):
    """背景執行週報產生，完成後發出訊號。"""

    finished = Signal(str)   # 成功：帶檔案路徑
    failed   = Signal(str)   # 失敗：帶錯誤訊息

    def run(self):
        try:
            from generate_weekly_report import generate_report
            out_path = generate_report()
            self.finished.emit(str(out_path))
        except Exception as exc:
            self.failed.emit(str(exc))
