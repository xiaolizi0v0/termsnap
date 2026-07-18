"""设置对话框：保存目录、截图快捷键、通知开关。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import __url__
from .config import Config
from .hotkey import to_pynput_hotkey


class SettingsDialog(QDialog):
    """修改并校验设置；Accepted 后从 result_* 属性读取结果。"""

    def __init__(self, config: Config, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("TermSnap 设置")
        self.setMinimumWidth(420)

        self._dir_edit = QLineEdit(config.save_dir)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse)

        self._hotkey_edit = QKeySequenceEdit(QKeySequence(config.hotkey))
        self._notify_box = QCheckBox("截图完成后显示通知")
        self._notify_box.setChecked(config.show_notification)

        form = QFormLayout()
        form.addRow("保存目录", dir_row)
        form.addRow("截图快捷键", self._hotkey_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        link = QLabel(f'GitHub 仓库：<a href="{__url__}">{__url__}</a>')
        link.setOpenExternalLinks(True)  # 点击直接用浏览器打开
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._notify_box)
        layout.addWidget(link)
        layout.addWidget(buttons)

        self.result_save_dir = config.save_dir
        self.result_hotkey = config.hotkey
        self.result_notify = config.show_notification

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择截图保存目录", self._dir_edit.text()
        )
        if directory:
            self._dir_edit.setText(directory)

    def accept(self):
        save_dir = self._dir_edit.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "目录无效", "请选择截图保存目录。")
            return
        try:
            Path(save_dir).expanduser().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "目录不可用", str(exc))
            return

        hotkey = self._hotkey_edit.keySequence().toString().strip().lower()
        if not hotkey:
            QMessageBox.warning(self, "快捷键无效", "请按下要使用的组合键。")
            return
        try:
            to_pynput_hotkey(hotkey)
        except ValueError as exc:
            QMessageBox.warning(self, "快捷键无效", str(exc))
            return

        self.result_save_dir = save_dir
        self.result_hotkey = hotkey
        self.result_notify = self._notify_box.isChecked()
        super().accept()
