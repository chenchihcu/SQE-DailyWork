"""Service layer for integrating with Windows LINE Desktop client.

Strategy: Render the brief report as an image (QImage) and place it on the
system clipboard using Qt's clipboard API (which provides CF_DIB format).
LINE PC supports Ctrl+V paste for images in the chat input area.

NOTE: LINE PC does NOT support Ctrl+V paste for CF_HDROP (file drag-drop
format). File transfers in LINE must use drag-and-drop or the attachment
button. Therefore, we convert the report to an image for clipboard use.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PySide6.QtGui import QImage


def copy_image_to_clipboard(image: "QImage") -> bool:
    """將 QImage 放到系統剪貼簿（CF_DIB 格式），LINE 可直接 Ctrl+V 貼上。"""
    try:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.instance().clipboard()
        if clipboard is None:
            return False
        clipboard.setImage(image)
        return True
    except Exception:
        logger.exception("複製圖片到剪貼簿失敗")
        return False


def focus_line_window() -> bool:
    """嘗試尋找並將 LINE 電腦版視窗帶到最前景。"""
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "LINE")
        if hwnd:
            # SW_RESTORE = 9, SW_SHOW = 5
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)
            else:
                ctypes.windll.user32.ShowWindow(hwnd, 5)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return True
        return False
    except Exception:
        logger.exception("切換至 LINE 視窗失敗")
        return False


def launch_line_desktop() -> bool:
    """嘗試啟動 Windows 本機的 LINE 電腦版應用程式。"""
    try:
        user_profile = os.environ.get("USERPROFILE")
        if not user_profile:
            username = os.getlogin()
            user_profile = f"{os.environ.get('SystemDrive', 'C:')}/Users/{username}"

        possible_paths = [
            Path(user_profile) / "AppData/Local/LINE/bin/LINE.exe",
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "LINE/LINE.exe",
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "LINE/LINE.exe",
        ]

        for path in possible_paths:
            if path.exists():
                subprocess.Popen([str(path)])
                return True

        return False
    except Exception:
        logger.exception("啟動 LINE 桌面版失敗")
        return False


def send_brief_report_to_line(image: "QImage") -> tuple[bool, str]:
    """執行完整 LINE 傳送精簡報告流程：
    1. 將報告圖片放到剪貼簿
    2. 喚醒或啟動 LINE 電腦版
    3. 使用者在 LINE 聊天室 Ctrl+V 貼上圖片
    """
    if not copy_image_to_clipboard(image):
        return False, "無法將報告圖片放入剪貼簿"

    focused = focus_line_window()
    if not focused:
        launched = launch_line_desktop()
        if launched:
            return True, "已將精簡報告圖片複製至剪貼簿。LINE 正在啟動，請在聊天室按下 Ctrl+V 貼上傳送。"
        else:
            return True, "已將精簡報告圖片複製至剪貼簿。未偵測到 LINE 電腦版，請手動開啟 LINE 並在對話框按下 Ctrl+V 傳送。"

    return True, "已將精簡報告圖片複製至剪貼簿。已為您喚起 LINE 電腦版，請在聊天室按下 Ctrl+V 貼上傳送。"
