"""应用主逻辑：托盘图标、热键联动、截图流程编排。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    Qt,
)
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .capture import (
    clear_images,
    dir_image_stats,
    grab_all_screens,
    human_size,
    save_image,
)
from .config import Config
from .hotkey import HotkeyListener
from .selector import RegionSelector
from .settings_dialog import SettingsDialog


LOGO_PATH = Path(__file__).resolve().parent.parent / "logo.png"


def load_icon() -> QIcon:
    """应用图标：优先用仓库根目录的 logo.png，缺失时用程序化兜底图标。"""
    if LOGO_PATH.is_file():
        icon = QIcon(str(LOGO_PATH))
        if not icon.isNull():
            return icon
    return make_icon()


def make_icon() -> QIcon:
    """程序化生成的兜底图标，避免附带资源文件。"""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3b82f6"))
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QPen(Qt.white, 4))
    # 四角裁切标记
    for x, y, dx, dy in (
        (16, 16, 10, 0), (16, 16, 0, 10),
        (48, 16, -10, 0), (48, 16, 0, 10),
        (16, 48, 10, 0), (16, 48, 0, -10),
        (48, 48, -10, 0), (48, 48, 0, -10),
    ):
        p.drawLine(x, y, x + dx, y + dy)
    p.end()
    return QIcon(pm)


class TermsnapApp(QObject):
    _hotkey_triggered = Signal()  # pynput 监听线程 → GUI 线程

    def __init__(self, qt_app: QApplication):
        super().__init__()
        self._qt_app = qt_app
        self.config = Config.load()
        self._selector: RegionSelector | None = None

        self._hotkey_triggered.connect(self.start_capture)

        self._tray = QSystemTrayIcon(load_icon(), parent=self)
        self._update_tooltip()
        menu = QMenu()
        act_capture = menu.addAction("立即截图")
        act_capture.triggered.connect(self.start_capture)
        act_settings = menu.addAction("设置…")
        act_settings.triggered.connect(self.open_settings)
        act_open_dir = menu.addAction("打开保存目录")
        act_open_dir.triggered.connect(self.open_save_dir)
        self._act_clear = menu.addAction("")
        self._act_clear.triggered.connect(self.clear_save_dir)
        menu.aboutToShow.connect(self._refresh_clear_action)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self.quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        self._hotkey = HotkeyListener(self.config.hotkey, self._hotkey_triggered.emit)
        self._hotkey.start()

    # --- 截图流程 ---
    def start_capture(self):
        """先抓取所有屏幕，再显示选区覆盖层（避免把遮罩截进去）。"""
        if self._selector is not None:
            return  # 已在截图中
        grabs = [(s, pm) for s, pm in grab_all_screens() if not pm.isNull()]
        if not grabs:
            QMessageBox.warning(None, "TermSnap", "无法抓取屏幕。")
            return
        self._selector = RegionSelector(grabs)
        self._selector.finished.connect(self.finish_capture)
        self._selector.canceled.connect(self._on_capture_canceled)
        self._selector.show()

    def finish_capture(self, image: QImage):
        """收到带标注的成品图像：保存并把路径写入剪贴板。"""
        selector, self._selector = self._selector, None
        selector.deleteLater()

        try:
            path = save_image(image, self.config.save_dir, self.config.filename_pattern)
        except OSError as exc:
            QMessageBox.warning(None, "TermSnap", str(exc))
            return

        # 把文件路径写入剪贴板，终端里 Ctrl+V / Ctrl+Shift+V 直接粘贴
        QGuiApplication.clipboard().setText(str(path))
        if self.config.show_notification and self._tray.supportsMessages():
            self._tray.showMessage(
                "截图已保存",
                f"{path}\n路径已复制到剪贴板",
                self._tray.icon(),
                4000,
            )

    def _on_capture_canceled(self):
        if self._selector is not None:
            self._selector.deleteLater()
            self._selector = None

    # --- 托盘动作 ---
    def open_settings(self):
        dlg = SettingsDialog(self.config)
        if dlg.exec() == SettingsDialog.Accepted:
            self.config.save_dir = dlg.result_save_dir
            self.config.hotkey = dlg.result_hotkey
            self.config.show_notification = dlg.result_notify
            self.config.save()
            self._hotkey.set_hotkey(self.config.hotkey)
            self._update_tooltip()

    def open_save_dir(self):
        path = Path(self.config.save_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def clear_save_dir(self):
        """一键清除：删除保存目录下的全部图片（带确认，不可恢复）。"""
        count, total = dir_image_stats(self.config.save_dir)
        if count == 0:
            return
        ret = QMessageBox.question(
            None,
            "TermSnap — 一键清除",
            f"确定删除保存目录下的全部 {count} 张图片"
            f"（共 {human_size(total)}）吗？\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        deleted, freed, errors = clear_images(self.config.save_dir)
        msg = f"已删除 {deleted} 张图片，释放 {human_size(freed)}。"
        if errors:
            msg += f"\n{len(errors)} 个文件删除失败：{errors[0]}"
        if self._tray.supportsMessages():
            self._tray.showMessage("一键清除", msg, self._tray.icon(), 4000)
        else:
            QMessageBox.information(None, "TermSnap — 一键清除", msg)

    def _refresh_clear_action(self):
        """每次弹出菜单时刷新图片占用大小，与“一键清除”同行显示。"""
        count, total = dir_image_stats(self.config.save_dir)
        self._act_clear.setText(f"一键清除（{count} 张图片，{human_size(total)}）")
        self._act_clear.setEnabled(count > 0)

    def quit(self):
        self._hotkey.stop()
        self._tray.hide()
        self._qt_app.quit()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.start_capture()

    def _update_tooltip(self):
        self._tray.setToolTip(f"TermSnap — 按 {self.config.hotkey} 截图")
