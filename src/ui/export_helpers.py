"""Helper utilities for handling file export paths and completion actions."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from services.appearance_preferences_service import load_application_preferences
from ui.popup_i18n import localize_popup_message

logger = logging.getLogger(__name__)


def get_default_export_filepath(filename: str) -> str:
    """Return default export file path based on user preferences."""
    prefs = load_application_preferences()
    if prefs.default_export_dir and os.path.isdir(prefs.default_export_dir):
        return os.path.join(prefs.default_export_dir, filename)
    return filename


def handle_export_completion(
    file_path: str,
    success_message: str,
    parent: QWidget | None = None,
) -> None:
    """Execute post-export action (open file, open folder, or notify) according to preferences."""
    prefs = load_application_preferences()

    if prefs.export_completion_action == "open_file" and os.path.exists(file_path):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(file_path)))
        except Exception:
            logger.exception("無法自動開啟已匯出檔案：%s", file_path)
    elif prefs.export_completion_action == "open_folder" and os.path.exists(file_path):
        try:
            folder_path = os.path.dirname(os.path.abspath(file_path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
        except Exception:
            logger.exception("無法自動開啟已匯出目錄：%s", file_path)

    if parent is not None:
        QMessageBox.information(parent, "成功", localize_popup_message(success_message))
