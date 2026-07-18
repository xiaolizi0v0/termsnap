"""PyInstaller 打包入口。

直接以脚本方式运行 termsnap/__main__.py 会破坏包内相对导入，
所以用这个小包装脚本作为 PyInstaller 的入口：

    pyinstaller --noconfirm --onefile --windowed --name termsnap run.py
"""

import sys

from termsnap.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
