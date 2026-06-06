import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# 確保能從 src/ 導入專案套件，同時保留 repo root 作為 scripts/runtime 脈絡。
_repo_root = Path(__file__).resolve().parent
for _path in (_repo_root / "src", _repo_root):
    _path_text = str(_path)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

from database.connection import initialize_database
from ui.main_window import MainWindow
from ui.theme import apply_app_theme

def main() -> int:
    # 1. 啟動鏈：初始化資料庫
    try:
        initialize_database()
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")
        return 1

    # 2. 啟動主 GUI
    app = QApplication(sys.argv)

    # 設定全域樣式 (可選)
    app.setStyle("Fusion")
    apply_app_theme(app)

    window = MainWindow()
    window.show()

    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
