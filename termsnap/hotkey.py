"""全局热键监听（基于 pynput，在后台线程运行）。"""

from __future__ import annotations

from typing import Callable, Optional

from pynput import keyboard

# 常见按键写法 → pynput 格式。配置里统一用小写 "ctrl+alt+a" 风格存储。
_KEY_ALIASES = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
    "meta": "<cmd>",
    "win": "<cmd>",
    "cmd": "<cmd>",
    "return": "<enter>",
    "enter": "<enter>",
    "esc": "<escape>",
    "escape": "<escape>",
    "del": "<delete>",
    "delete": "<delete>",
    "ins": "<insert>",
    "insert": "<insert>",
    "print": "<print_screen>",
    "printscreen": "<print_screen>",
    "print_screen": "<print_screen>",
    "space": "<space>",
    "spacebar": "<space>",
    "backspace": "<backspace>",
    "tab": "<tab>",
    "home": "<home>",
    "end": "<end>",
    "pgup": "<page_up>",
    "page_up": "<page_up>",
    "pgdn": "<page_down>",
    "page_down": "<page_down>",
    "up": "<up>",
    "down": "<down>",
    "left": "<left>",
    "right": "<right>",
    "caps_lock": "<caps_lock>",
    "num_lock": "<num_lock>",
    "scroll_lock": "<scroll_lock>",
}


def to_pynput_hotkey(hotkey: str) -> str:
    """把 "ctrl+alt+a" / "printscreen" 这类写法转换为 pynput 的 "<ctrl>+<alt>+a" 格式。

    无法识别时抛出 ValueError。
    """
    parts = [seg for seg in (p.strip().lower() for p in hotkey.split("+")) if seg]
    if not parts:
        raise ValueError(f"无效的快捷键: {hotkey!r}")
    out = []
    for part in parts:
        if part in _KEY_ALIASES:
            out.append(_KEY_ALIASES[part])
        elif len(part) == 1:
            out.append(part)
        elif part.startswith("f") and part[1:].isdigit():
            out.append(f"<{part}>")
        else:
            raise ValueError(f"无法识别的按键: {part!r}")
    return "+".join(out)


class HotkeyListener:
    """监听全局热键，按下时调用回调。

    注意：回调运行在 pynput 的监听线程，不要直接操作 GUI，
    请在回调里发射 Qt 信号转交主线程。
    """

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self._callback = callback
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._hotkey = to_pynput_hotkey(hotkey)

    def set_hotkey(self, hotkey: str) -> None:
        """修改热键；若正在监听则立即生效。"""
        self._hotkey = to_pynput_hotkey(hotkey)
        if self._listener is not None:
            self.stop()
            self.start()

    def start(self) -> None:
        self.stop()
        self._listener = keyboard.GlobalHotKeys({self._hotkey: self._callback})
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
