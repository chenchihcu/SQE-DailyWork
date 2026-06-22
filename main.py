import logging
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSharedMemory, qInstallMessageHandler, QtMsgType
from PySide6.QtWidgets import QApplication, QMessageBox

# 確保能從 src/ 導入專案套件，同時保留 repo root 作為 scripts/runtime 脈絡。
_repo_root = Path(__file__).resolve().parent
for _path in (_repo_root / "src", _repo_root):
    _path_text = str(_path)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

from database.connection import initialize_database
from ui.main_window import MainWindow
from ui.theme import apply_app_theme

# 載入 .env 環境變數 (若存在)
try:
    from dotenv import load_dotenv
    env_path = _repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# 可透過環境變數覆蓋資料庫路徑
_env_db_path = os.environ.get("SQE_DB_PATH", "").strip()
if _env_db_path:
    import database.connection as _conn_mod
    _conn_mod.DB_PATH = Path(_env_db_path).resolve()

# 可透過環境變數設定日誌層級
_log_level = os.environ.get("SQE_LOG_LEVEL", "INFO").strip().upper()

_logs_dir = _repo_root / "logs" / "app.log"
_logs_dir.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(_logs_dir), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
_logger = logging.getLogger("SQE")


def _qt_message_handler(msg_type: QtMsgType, context, message: str) -> None:
    """Qt 訊息處理 — 只記錄警告層級以上訊息。"""
    if msg_type >= QtMsgType.Warning or "Unknown property" not in message:
        level = {
            QtMsgType.Debug: logging.DEBUG,
            QtMsgType.Warning: logging.WARNING,
            QtMsgType.Critical: logging.ERROR,
            QtMsgType.Fatal: logging.CRITICAL,
        }.get(msg_type, logging.INFO)
        _logger.log(level, "Qt: %s", message)


def _global_excepthook(exc_type, exc_value, exc_tb) -> None:
    """擷取未處理例外並顯示錯誤對話框。"""
    _logger.critical(
        "未處理例外: %s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )
    try:
        app = QApplication.instance()
        if app is not None:
            msg = "".join(
                traceback.format_exception_only(exc_type, exc_value)
            ).strip()
            QMessageBox.critical(
                None,
                "系統錯誤",
                f"應用程式發生未預期錯誤：\n\n{msg}\n\n請查看 logs/app.log 取得詳細資訊。",
            )
    except Exception:
        logger.exception("Global excepthook UI also failed")


def main() -> int:
    # 1. 安裝全域例外處理
    sys.excepthook = _global_excepthook
    qInstallMessageHandler(_qt_message_handler)

    # 2. 啟動鏈：初始化資料庫
    try:
        initialize_database()
    except Exception as e:
        _logger.critical("資料庫初始化失敗", exc_info=True)
        print(f"資料庫初始化失敗: {e}")
        _db_error_app = QApplication(sys.argv)
        _db_error_app.setStyle("Fusion")
        QMessageBox.critical(
            None,
            "資料庫錯誤",
            f"資料庫初始化失敗：\n\n{e}\n\n"
            "請檢查 data/sqe_v2.db 是否損毀或可讀取。\n"
            "詳細資訊請查看 logs/app.log。",
        )
        return 1

    # 3. 啟動主 GUI
    # 高 DPI 支援 (PySide6 >= 6.6 預設啟用, 不再需要手動設定)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_app_theme(app)

    # 單一實例保護：禁止同時執行兩個實例
    _instance_lock = QSharedMemory("SQE_DailyWork_Instance")
    if not _instance_lock.create(1):
        QMessageBox.warning(
            None,
            "應用程式已執行",
            "SQE DailyWork 已經在執行中。\n"
            "每個工作階段只能啟動一個實例。",
        )
        return 0

    window = MainWindow()
    window.show()

    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
