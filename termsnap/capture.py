"""屏幕抓取与图片保存。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtGui import QScreen

_INVALID_CHARS = '\\/:*?"<>|'
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def human_size(num: float) -> str:
    """把字节数格式化为可读的存储大小。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def dir_image_stats(save_dir: str) -> Tuple[int, int]:
    """统计保存目录下的图片数量和总字节数（不递归子目录）。"""
    directory = Path(save_dir).expanduser()
    count, total = 0, 0
    try:
        for f in directory.iterdir():
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                count += 1
                total += f.stat().st_size
    except OSError:
        pass
    return count, total


def clear_images(save_dir: str) -> Tuple[int, int, List[str]]:
    """删除保存目录下的全部图片（不递归子目录）。

    返回 (删除数量, 释放字节数, 失败信息列表)。
    """
    directory = Path(save_dir).expanduser()
    deleted, freed, errors = 0, 0, []
    for f in directory.iterdir():
        if not (f.is_file() and f.suffix.lower() in IMAGE_EXTS):
            continue
        try:
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            freed += size
        except OSError as exc:
            errors.append(f"{f.name}: {exc}")
    return deleted, freed, errors


def grab_all_screens() -> List[Tuple[QScreen, QPixmap]]:
    """抓取所有屏幕，返回 [(QScreen, QPixmap), ...]。

    必须在覆盖层显示之前调用，否则会把遮罩也截进去。
    """
    return [(screen, screen.grabWindow(0)) for screen in QGuiApplication.screens()]


def crop(pixmap: QPixmap, rect: QRect) -> QImage:
    """按逻辑坐标从屏幕截图中裁剪选区，返回实际像素尺寸的图像。"""
    dpr = pixmap.devicePixelRatio()
    device_rect = QRect(
        round(rect.x() * dpr),
        round(rect.y() * dpr),
        round(rect.width() * dpr),
        round(rect.height() * dpr),
    )
    image = pixmap.toImage().copy(device_rect)
    image.setDevicePixelRatio(1.0)
    return image


def build_filename(pattern: str) -> str:
    """按模式生成文件名（不含扩展名），支持 {timestamp}/{date}/{time} 占位符。"""
    now = datetime.now()
    name = pattern or "termsnap_{timestamp}"
    name = name.replace("{timestamp}", now.strftime("%Y%m%d_%H%M%S"))
    name = name.replace("{date}", now.strftime("%Y%m%d"))
    name = name.replace("{time}", now.strftime("%H%M%S"))
    name = "".join("_" if c in _INVALID_CHARS else c for c in name).strip()
    return name or "termsnap"


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """若文件已存在则追加 _1/_2…，避免覆盖旧截图。"""
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def save_image(image: QImage, save_dir: str, pattern: str) -> Path:
    """把图像保存为 PNG 到用户设置的目录，返回最终文件路径。"""
    directory = Path(save_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = unique_path(directory, build_filename(pattern), ".png")
    if not image.save(str(path), "PNG"):
        raise OSError(f"无法保存截图: {path}")
    return path
