# -*- coding: utf-8 -*-
"""
桥梁病害识别 — 入口脚本（BIMBase兼容版）

问题背景：BIMBase通过exec()在新pythonw.exe进程中执行此脚本。
- 旧版：dialog.show() 不阻塞，脚本结束即闪退
- 新版：dialog.exec_() 模态阻塞，保持对话框直到用户关闭
"""

import sys
import os
import traceback
import io

# ★ 关键修复：BIMBase的pythonw.exe默认locale不是UTF-8，强制设置
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["LC_ALL"] = "en_US.UTF-8"
# 强制Windows进程代码页为UTF-8
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleCP(65001)
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass
# 确保stdout/stderr有编码（pythonw.exe中它们可能是None）
if sys.stdout is None:
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
if sys.stderr is None:
    sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")

_current_dir = os.path.dirname(os.path.abspath(__file__))
_log_file = os.path.join(_current_dir, "bridge_disease_debug.log")


def _log(msg):
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _winmsg(title, text, icon=0x40):
    """Windows API弹窗（不依赖Qt）"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x0 | icon)
    except Exception:
        pass


_log("=" * 60)
_log("STARTED")
_log(f"exe={sys.executable}")
_log(f"cwd={os.getcwd()}")

# Step 1: 路径
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# Step 2: 设置Qt环境（platform plugin路径）
if not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
    import importlib.util
    spec = importlib.util.find_spec("PyQt5")
    pyqt5_root = os.path.dirname(spec.origin) if (spec and spec.origin) else os.path.join(_current_dir, "PyQt5")

    paths_to_try = [
        os.path.join(pyqt5_root, "Qt5", "plugins"),
        os.path.join(pyqt5_root, "Qt", "plugins"),
        r"D:\BIMBASE\BIMBase建模软件 2025\PythonScript\python-3.7.9-embed-amd64\Lib\site-packages\PyQt5\Qt5\plugins",
        r"D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\QTBoot",
    ]
    for sp in sys.path:
        if os.path.isdir(sp):
            for sub in ["PyQt5", "PyQt6"]:
                for qv in ["Qt5", "Qt"]:
                    p = os.path.join(sp, sub, qv, "plugins")
                    if p not in paths_to_try:
                        paths_to_try.append(p)

    for p in paths_to_try:
        plat = os.path.join(p, "platforms")
        if os.path.exists(os.path.join(plat, "qwindows.dll")):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = p
            _log(f"SET plugin_path={p}")
            break
        if os.path.exists(os.path.join(p, "qwindows.dll")):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.dirname(p)
            _log(f"SET plugin_path={os.path.dirname(p)}")
            break
    else:
        _log("WARNING: plugin path not found")

# 添加bin到PATH（qwindows.dll依赖Qt5Core.dll等）
bin_paths = [
    os.path.join(pyqt5_root, "Qt5", "bin"),
    os.path.join(pyqt5_root, "Qt", "bin"),
    r"D:\BIMBASE\BIMBase建模软件 2025\PythonScript\python-3.7.9-embed-amd64\Lib\site-packages\PyQt5\Qt5\bin",
]
for bp in bin_paths:
    if os.path.exists(bp) and bp not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bp + os.pathsep + os.environ.get("PATH", "")
        _log(f"ADD PATH={bp}")

def run_disease_recognition():
    """启动桥梁病害识别对话框"""
    # Step 3: 导入并运行对话框
    try:
        from PyQt5.QtWidgets import QApplication
        _log("PyQt5 imported OK")

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            _log("QApplication created")
        else:
            _log("QApplication reused")

        from disease_dialog import DiseaseDialog
        _log("DiseaseDialog imported OK")

        dialog = DiseaseDialog()
        _log("DiseaseDialog created")

        # ★ 关键修复：使用exec_()模态阻塞，保持对话框直到用户关闭
        # 这样BIMBase的pythonw.exe进程不会立即退出
        dialog.exec_()
        _log("DiseaseDialog closed by user")

    except Exception as e:
        _log(f"FAILED: {e}")
        _log(traceback.format_exc())
        _winmsg("桥梁病害识别 - 错误", f"启动失败:\n{e}\n\n请查看日志:\n{_log_file}", icon=0x10)
        raise

    _log("COMPLETED")


if __name__ == "__main__":
    run_disease_recognition()
