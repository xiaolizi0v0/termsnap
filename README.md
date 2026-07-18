<p align="center">
  <img src="logo.png" alt="TermSnap Logo" width="180">
</p>

<h1 align="center">TermSnap v0.1.0</h1>

---

<p align="center">
  <img src="https://img.shields.io/github/languages/code-size/xiaolizi0v0/termsnap" alt="code size">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.6%2B-green" alt="PySide6">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey" alt="platform">
  <img src="https://img.shields.io/github/last-commit/xiaolizi0v0/termsnap" alt="last commit">
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Created-26.07.18-blue" alt="Created">
  <img src="https://img.shields.io/badge/Author-xiaolizi0v0-orange" alt="Author">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

---

**TermSnap** — 为终端用户打造的快捷键选区截图工具：截图、标注、自动保存、一键粘贴文件路径。
*A hotkey-driven region screenshot tool for terminal users — capture, annotate, auto-save, and paste the file path instantly.*

按下全局快捷键 → 拖拽框选区域 → 用工具栏标注（矩形/椭圆/箭头/画笔/文字/马赛克）→
截图自动保存到你设置的目录 → 文件路径自动写入剪贴板，
回到终端直接 `Ctrl+V` / `Ctrl+Shift+V` 即可粘贴路径。

## 功能 Features

- 全局快捷键触发选区截图（默认 `Ctrl+Alt+Shift+A`，可在设置中修改）
- 选区覆盖层：拖拽框选、实时尺寸提示，`Esc`/右键取消；支持多显示器
- 标注工具栏：矩形 / 椭圆 / 箭头 / 画笔 / 文字 / 马赛克，6 色可选，支持撤销
- 截图自动保存为 PNG，文件名带时间戳，自动避免重名覆盖
- 文件路径自动复制到剪贴板
- 系统托盘常驻：左键托盘图标也可触发截图
- 托盘菜单「一键清除」：同行显示保存目录图片占用大小，确认后清空
- 设置界面：保存目录、快捷键、通知开关，附 GitHub 仓库链接

## 安装 Install

```bash
python -m venv .venv
# Windows (Git Bash)
./.venv/Scripts/python -m pip install -r requirements.txt
# Windows (CMD/PowerShell)
.venv\Scripts\python -m pip install -r requirements.txt
```

也可以直接以包形式安装：`pip install .`（提供 `termsnap` 命令）。

## 运行 Run

```bash
# Windows (Git Bash)
./.venv/Scripts/python -m termsnap
# Windows (CMD/PowerShell)
.venv\Scripts\python -m termsnap
```

启动后常驻系统托盘。按 `Ctrl+Alt+Shift+A`（或左键点击托盘图标）开始选区截图。
框选后弹出标注工具栏：选工具直接画，「文字」工具点击选区内任意位置输入；
`Enter`/「完成」保存并复制路径，`Esc`/「取消」放弃，`Ctrl+Z`/「撤销」回退一步，
在选区外按下鼠标可重新框选。右键托盘图标可打开「设置」修改保存目录与快捷键。

## 配置 Configuration

配置文件：Windows 下为 `%APPDATA%\termsnap\config.json`，示例：

```json
{
  "save_dir": "C:\\Users\\you\\Pictures\\termsnap",
  "hotkey": "ctrl+alt+shift+a",
  "filename_pattern": "termsnap_{timestamp}",
  "show_notification": true
}
```

- `save_dir`：截图保存地址（在托盘「设置…」里修改）
- `hotkey`：全局快捷键，小写加号分隔，如 `ctrl+alt+shift+a`、`printscreen`、`ctrl+shift+f5`
- `filename_pattern`：文件名模式，支持 `{timestamp}` / `{date}` / `{time}` 占位符
- `show_notification`：截图完成后是否弹出系统通知

## 平台说明 Notes

主要在 Windows 上开发测试。macOS / Linux（X11）理论上可用（依赖 PySide6 与 pynput），
但全局快捷键在 Wayland 下不可用；macOS 需授予终端「屏幕录制」与「辅助功能」权限。
