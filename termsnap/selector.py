"""选区覆盖层：每个屏幕一个无边框半透明窗口。

流程：拖拽框选 → 进入标注模式（工具栏：矩形/椭圆/箭头/画笔/文字/马赛克、
颜色、撤销、完成/取消）→ 完成后把带标注的图像发回。

Esc 取消，Enter 完成，Ctrl+Z 撤销；标注模式下在选区外按下可重新框选。
选区不可跨屏幕（按框选起点所在屏幕处理）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QScreen,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QWidget,
)

from .capture import crop

_DIM = QColor(0, 0, 0, 110)
_BORDER = QPen(QColor("#3b82f6"), 2)
_CROSS = QPen(QColor(255, 255, 255, 70), 1)
_LABEL_BG = QColor(0, 0, 0, 180)
_MIN_SIZE = 3          # 小于 3px 的框选视为误触
_PEN_WIDTH = 3         # 画笔/图形线宽（逻辑像素）
_ARROW_MIN = 8         # 箭头最小长度
_MOSAIC = 12           # 马赛克取样边长（逻辑像素）
_FONT_SIZE = 18        # 文字标注字号（逻辑像素）

PALETTE = ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#222222"]
TOOLS = [
    ("rect", "矩形"),
    ("ellipse", "椭圆"),
    ("arrow", "箭头"),
    ("pen", "画笔"),
    ("text", "文字"),
    ("mosaic", "马赛克"),
]


@dataclass
class Annotation:
    """一条标注。rect 用于矩形/椭圆，points 用于箭头(两点)/画笔/马赛克，text+pos 用于文字。"""

    kind: str
    color: QColor
    rect: QRect = field(default_factory=QRect)
    points: List[QPoint] = field(default_factory=list)
    text: str = ""
    pos: QPoint = field(default_factory=QPoint)


def _draw_mosaic_block(p: QPainter, source: QImage, dpr: float, center: QPoint):
    """以 center 为中心取样一块区域，像素化后画回原位置。坐标均为逻辑坐标。"""
    half = _MOSAIC // 2
    logical = QRect(center.x() - half, center.y() - half, _MOSAIC, _MOSAIC)
    dev = QRect(
        round(logical.x() * dpr),
        round(logical.y() * dpr),
        round(logical.width() * dpr),
        round(logical.height() * dpr),
    )
    if dev.width() < 2 or dev.height() < 2:
        return
    patch = source.copy(dev)
    factor = 6
    small = patch.scaled(
        max(1, dev.width() // factor),
        max(1, dev.height() // factor),
        Qt.IgnoreAspectRatio,
        Qt.SmoothTransformation,
    )
    pixelated = small.scaled(dev.size(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
    p.drawImage(logical, pixelated)


def paint_annotation(p: QPainter, ann: Annotation, source: QImage, dpr: float):
    """把一条标注画到 painter 上（painter 的坐标系为窗口逻辑坐标）。

    source 是整屏图像（设备像素），仅供马赛克取样。
    """
    if ann.kind == "mosaic":
        for pt in ann.points:
            _draw_mosaic_block(p, source, dpr, pt)
        return

    color = QColor(ann.color)
    if ann.kind == "text":
        font = p.font()
        font.setPixelSize(_FONT_SIZE)
        font.setBold(True)
        p.setFont(font)
        p.setPen(color)
        ascent = QFontMetrics(font).ascent()
        p.drawText(ann.pos + QPoint(0, ascent), ann.text)
        return

    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(color, _PEN_WIDTH))
    p.setBrush(Qt.NoBrush)

    if ann.kind == "rect":
        p.drawRect(ann.rect)
    elif ann.kind == "ellipse":
        p.drawEllipse(ann.rect)
    elif ann.kind == "pen":
        if len(ann.points) > 1:
            p.drawPolyline(QPolygonF([QPointF(q) for q in ann.points]))
    elif ann.kind == "arrow" and len(ann.points) >= 2:
        start, end = ann.points[0], ann.points[-1]
        p.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        head = 14
        p1 = QPointF(end) - QPointF(math.cos(angle + math.pi / 6), math.sin(angle + math.pi / 6)) * head
        p2 = QPointF(end) - QPointF(math.cos(angle - math.pi / 6), math.sin(angle - math.pi / 6)) * head
        p.setBrush(color)
        p.drawPolygon(QPolygonF([QPointF(end), p1, p2]))


class _SnipWindow(QWidget):
    """单个屏幕上的选区+标注窗口，坐标均为该屏幕内的逻辑坐标。"""

    finished = Signal(QImage)
    canceled = Signal()
    locked = Signal()  # 进入标注模式时发出，用于冻结其他屏幕的窗口

    def __init__(self, screen: QScreen, pixmap: QPixmap, index: int, parent=None):
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self._pixmap = pixmap
        self._image = pixmap.toImage()  # 马赛克取样用，避免重复转换
        self._index = index
        self._origin = QPoint()
        self._sel = QRect()
        self._cursor = QPoint(-1, -1)
        self._dragging = False
        self._mode = "select"  # select | annotate
        self._inactive = False  # 其他屏幕已进入标注模式时置 True
        self._annotations: List[Annotation] = []
        self._current: Optional[Annotation] = None
        self._tool = "rect"
        self._color = QColor(PALETTE[0])
        self._text_editor: Optional[QLineEdit] = None
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setGeometry(screen.geometry())
        self._toolbar = self._build_toolbar()
        self._toolbar.hide()

    # --- 工具栏 ---
    def _build_toolbar(self) -> QWidget:
        bar = QWidget(self)
        bar.setFocusPolicy(Qt.NoFocus)
        bar.setStyleSheet(
            "QWidget#toolbar { background: rgba(28,28,30,235); border-radius: 6px; }"
            "QToolButton { color: white; background: transparent; border: none;"
            "  padding: 4px 7px; font-size: 13px; }"
            "QToolButton:hover { background: rgba(255,255,255,45); }"
            "QToolButton:checked { background: #3b82f6; border-radius: 4px; }"
        )
        bar.setObjectName("toolbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)

        self._tool_group = QButtonGroup(bar)
        self._tool_group.setExclusive(True)
        self._tool_buttons = {}
        for i, (kind, label) in enumerate(TOOLS):
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda checked=False, k=kind: self._set_tool(k))
            self._tool_group.addButton(btn, i)
            lay.addWidget(btn)
            self._tool_buttons[kind] = btn
        self._tool_buttons[self._tool].setChecked(True)

        lay.addSpacing(8)
        self._color_group = QButtonGroup(bar)
        self._color_group.setExclusive(True)
        for i, c in enumerate(PALETTE):
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setFixedSize(20, 20)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(
                f"QToolButton {{ background: {c}; border: 1px solid #999; }}"
                "QToolButton:checked { border: 2px solid white; }"
            )
            btn.clicked.connect(lambda checked=False, col=c: self._set_color(col))
            self._color_group.addButton(btn, i)
            lay.addWidget(btn)
        self._color_group.button(0).setChecked(True)

        lay.addSpacing(8)
        undo = QToolButton()
        undo.setText("撤销")
        undo.setFocusPolicy(Qt.NoFocus)
        undo.clicked.connect(self._undo)
        lay.addWidget(undo)

        lay.addSpacing(8)
        ok = QToolButton()
        ok.setText("完成")
        ok.setFocusPolicy(Qt.NoFocus)
        ok.setStyleSheet(
            "QToolButton { background: #2e7d32; border-radius: 4px; }"
            "QToolButton:hover { background: #388e3c; }"
        )
        ok.clicked.connect(self._confirm)
        lay.addWidget(ok)

        cancel = QToolButton()
        cancel.setText("取消")
        cancel.setFocusPolicy(Qt.NoFocus)
        cancel.clicked.connect(self.canceled.emit)
        lay.addWidget(cancel)
        return bar

    def _set_tool(self, kind: str):
        self._tool = kind

    def _set_color(self, color: str):
        self._color = QColor(color)
        if self._text_editor is not None:
            self._text_editor.setStyleSheet(self._editor_style())

    def _place_toolbar(self):
        bar = self._toolbar
        bar.adjustSize()
        w, h = bar.width(), bar.height()
        x = min(max(self._sel.left(), 4), max(4, self.width() - w - 4))
        y = self._sel.bottom() + 8
        if y + h > self.height() - 4:  # 下方放不下就放到选区上方/内部
            y = self._sel.top() - h - 8
        if y < 4:
            y = max(4, self._sel.bottom() - h - 8)
        bar.move(x, y)

    # --- 事件 ---
    def showEvent(self, event):
        self.grabKeyboard()  # 确保 Esc 一定能被收到
        super().showEvent(event)

    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)

    def set_inactive(self, inactive: bool):
        self._inactive = inactive
        self.setCursor(Qt.ArrowCursor if inactive else Qt.CrossCursor)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            if self._text_editor is not None:
                self._discard_text_editor()
            else:
                self.canceled.emit()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if self._mode == "annotate" and self._text_editor is None:
                self._confirm()
        elif event.matches(QKeySequence.Undo):
            self._undo()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if self._inactive:
            return
        if event.button() == Qt.RightButton:
            self.canceled.emit()
            return
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()

        if self._mode == "annotate" and self._sel.contains(pos):
            # 在选区内按下：开始画标注（文字工具则弹出输入框）
            if self._tool == "text":
                self._start_text_editor(pos)
                return
            self._origin = pos
            if self._tool in ("rect", "ellipse"):
                self._current = Annotation(self._tool, QColor(self._color), rect=QRect(pos, pos))
            else:  # arrow / pen / mosaic
                self._current = Annotation(self._tool, QColor(self._color), points=[pos])
            self.update()
            return

        # 其他情况：（重新）框选，清空已有标注
        self._discard_text_editor()
        self._annotations.clear()
        self._current = None
        self._mode = "select"
        self._toolbar.hide()
        self._origin = pos
        self._sel = QRect(pos, pos)
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event):
        self._cursor = event.position().toPoint()
        if self._dragging:
            self._sel = (
                QRect(self._origin, self._cursor).normalized().intersected(self.rect())
            )
        elif self._current is not None:
            cur = self._current
            if cur.kind in ("rect", "ellipse"):
                cur.rect = QRect(self._origin, self._cursor).normalized()
            elif cur.kind == "arrow":
                cur.points = [self._origin, self._cursor]
            elif cur.kind == "pen":
                cur.points.append(self._cursor)
            elif cur.kind == "mosaic":
                last = cur.points[-1]
                if (self._cursor - last).manhattanLength() >= _MOSAIC // 2:
                    cur.points.append(self._cursor)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._dragging:
            self._dragging = False
            if self._sel.width() >= _MIN_SIZE and self._sel.height() >= _MIN_SIZE:
                self._mode = "annotate"
                self._place_toolbar()
                self._toolbar.show()
                self.grabKeyboard()
                self.locked.emit()
            else:
                self._sel = QRect()
            self.update()
            return
        if self._current is not None:
            ann = self._current
            self._current = None
            if self._annotation_valid(ann):
                self._annotations.append(ann)
            self.update()

    @staticmethod
    def _annotation_valid(ann: Annotation) -> bool:
        if ann.kind in ("rect", "ellipse"):
            return ann.rect.width() >= _MIN_SIZE and ann.rect.height() >= _MIN_SIZE
        if ann.kind == "arrow":
            s, e = ann.points[0], ann.points[-1]
            return math.hypot(e.x() - s.x(), e.y() - s.y()) >= _ARROW_MIN
        return len(ann.points) >= 2

    # --- 文字标注 ---
    def _editor_style(self) -> str:
        c = self._color.name()
        return (
            f"background: rgba(0,0,0,140); color: {c};"
            f"border: 1px solid {c}; font: bold {_FONT_SIZE}px sans-serif; padding: 2px;"
        )

    def _start_text_editor(self, pos: QPoint):
        if self._text_editor is not None:
            self._commit_text_editor()
        editor = QLineEdit(self)
        editor.setStyleSheet(self._editor_style())
        editor.move(pos)
        editor.resize(240, _FONT_SIZE + 16)
        editor.editingFinished.connect(self._commit_text_editor)
        self._text_editor = editor
        editor.show()
        editor.setFocus()

    def _commit_text_editor(self):
        editor = self._text_editor
        if editor is None:
            return
        self._text_editor = None
        text = editor.text().strip()
        if text:
            self._annotations.append(
                Annotation("text", QColor(self._color), text=text, pos=editor.pos())
            )
        editor.hide()
        editor.deleteLater()
        self.setFocus()
        self.update()

    def _discard_text_editor(self):
        if self._text_editor is not None:
            editor, self._text_editor = self._text_editor, None
            editor.hide()
            editor.deleteLater()

    # --- 撤销 / 完成 ---
    def _undo(self):
        if self._text_editor is not None:
            self._discard_text_editor()
        elif self._annotations:
            self._annotations.pop()
            self.update()

    def _confirm(self):
        if self._mode != "annotate":
            return
        image = self._render_final()
        self.finished.emit(image)

    def _render_final(self) -> QImage:
        """裁剪选区并把标注绘制上去，返回实际像素尺寸的成品图像。"""
        dpr = self._pixmap.devicePixelRatio()
        image = crop(self._pixmap, self._sel)
        if self._annotations:
            p = QPainter(image)
            p.scale(dpr, dpr)
            p.translate(-self._sel.topLeft())
            for ann in self._annotations:
                paint_annotation(p, ann, self._image, dpr)
            p.end()
        return image

    # --- 绘制 ---
    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._pixmap)
        p.fillRect(self.rect(), _DIM)
        if not self._sel.isNull():
            # 选区内重绘原图（去掉暗化），源矩形需换算成设备像素
            dpr = self._pixmap.devicePixelRatio()
            src = self._image.copy(
                round(self._sel.x() * dpr),
                round(self._sel.y() * dpr),
                round(self._sel.width() * dpr),
                round(self._sel.height() * dpr),
            )
            p.drawImage(self._sel, src)
            p.setPen(_BORDER)
            p.drawRect(self._sel)
        for ann in self._annotations:
            paint_annotation(p, ann, self._image, self._pixmap.devicePixelRatio())
        if self._current is not None:
            paint_annotation(p, self._current, self._image, self._pixmap.devicePixelRatio())
        if self._mode == "select":
            if self._dragging and not self._sel.isNull():
                self._draw_size_label(p)
            elif self._cursor.x() >= 0 and not self._inactive:
                p.setPen(_CROSS)
                p.drawLine(0, self._cursor.y(), self.width(), self._cursor.y())
                p.drawLine(self._cursor.x(), 0, self._cursor.x(), self.height())
        p.end()

    def _draw_size_label(self, p: QPainter):
        text = f"{self._sel.width()} × {self._sel.height()}"
        rect = p.fontMetrics().boundingRect(text).adjusted(-8, -4, 8, 4)
        rect.moveTopLeft(self._sel.topLeft() + QPoint(0, -rect.height() - 6))
        if rect.top() < 0:
            rect.moveTopLeft(self._sel.topLeft() + QPoint(0, 6))
        p.fillRect(rect, _LABEL_BG)
        p.setPen(Qt.white)
        p.drawText(rect, Qt.AlignCenter, text)


class RegionSelector(QObject):
    """管理所有屏幕上的选区窗口。"""

    finished = Signal(QImage)  # 带标注的成品图像
    canceled = Signal()

    def __init__(self, grabs: List[Tuple[QScreen, QPixmap]], parent=None):
        super().__init__(parent)
        self._windows: List[_SnipWindow] = []
        for index, (screen, pixmap) in enumerate(grabs):
            w = _SnipWindow(screen, pixmap, index)
            w.finished.connect(self._on_finished)
            w.canceled.connect(self._on_canceled)
            w.locked.connect(lambda win=w: self._on_locked(win))
            self._windows.append(w)

    def show(self):
        for w in self._windows:
            w.show()

    def _on_locked(self, active: _SnipWindow):
        # 一个屏幕进入标注模式后，冻结其他屏幕的窗口
        for w in self._windows:
            if w is not active:
                w.set_inactive(True)

    def _on_finished(self, image: QImage):
        self._close_all()
        self.finished.emit(image)

    def _on_canceled(self):
        self._close_all()
        self.canceled.emit()

    def _close_all(self):
        windows, self._windows = self._windows, []
        for w in windows:
            w.blockSignals(True)
            w.close()
