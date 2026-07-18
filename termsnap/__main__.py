"""入口：python -m termsnap（或安装后运行 termsnap）。"""

import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .app import TermsnapApp


def main() -> int:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("TermSnap")
    qt_app.setQuitOnLastWindowClosed(False)  # 常驻托盘

    guard = QSharedMemory("termsnap_singleton")  # 单实例，避免热键重复注册
    if not guard.create(1):
        QMessageBox.warning(None, "TermSnap", "TermSnap 已在运行中。")
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "TermSnap", "系统托盘不可用。")
        return 1

    app = TermsnapApp(qt_app)  # noqa: F841  保持引用
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
