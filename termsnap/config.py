"""配置读写：保存在用户目录下的 JSON 文件。"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "termsnap"


def config_dir() -> Path:
    """返回配置目录（Windows: %APPDATA%/termsnap）。"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / APP_NAME


def config_file() -> Path:
    return config_dir() / "config.json"


def default_save_dir() -> Path:
    return Path.home() / "Pictures" / APP_NAME


@dataclass
class Config:
    """应用设置。save_dir 即用户设置的截图保存地址。"""

    save_dir: str = field(default_factory=lambda: str(default_save_dir()))
    hotkey: str = "ctrl+alt+shift+a"
    filename_pattern: str = "termsnap_{timestamp}"
    show_notification: bool = True

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        path = config_file()
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return cfg  # 配置损坏时回退默认值
            if isinstance(data, dict):
                known = asdict(cfg)
                for key, value in data.items():
                    if key in known:
                        setattr(cfg, key, value)
        return cfg

    def save(self) -> None:
        path = config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
