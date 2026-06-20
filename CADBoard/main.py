# -*- coding: utf-8 -*-
"""
CAD画板插件 - 主入口文件

BIMBase Python插件入口。
当用户点击插件按钮时，BIMBase通过exec方式执行此脚本。
"""

import sys
import os
import traceback

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# 在导入任何会触发 pyp3d/_Core 初始化的模块之前，先确保 sys.argv[1]
# 指向 BIMBase 进程 PID。否则 CADBoard 窗口成为前台窗口时，pyp3d 的
# Port 可能连接到错误进程，导致 'NoneType' object has no attribute 'send'。
from utils.bimbase_pid import ensure_bimbase_pid_argv
ensure_bimbase_pid_argv()

# 将 bimbase_sync 中的组件类导入到 main 模块命名空间，
# 使 BIMBase 在解析 representation='main.SweepBoxComponent' 等时能正确找到类
from bimbase_sync import *

_LOG_FILE = os.path.join(_current_dir, "CADBoard_error.log")


def _write_log(message):
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _setup_qt_plugins():
    if os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        return
    try:
        import importlib.util
        spec = importlib.util.find_spec("PyQt5")
        if spec and spec.origin:
            pyqt5_root = os.path.dirname(spec.origin)
        else:
            pyqt5_root = os.path.join(_current_dir, "PyQt5")
        possible_plugin_paths = [
            os.path.join(pyqt5_root, "Qt5", "plugins"),
            os.path.join(pyqt5_root, "Qt", "plugins"),
            os.path.join(pyqt5_root, "plugins"),
        ]
        for site_pkg in sys.path:
            if not os.path.isdir(site_pkg):
                continue
            for sub in ["PyQt5", "PyQt6"]:
                for qt_ver in ["Qt5", "Qt"]:
                    candidate = os.path.join(site_pkg, sub, qt_ver, "plugins")
                    if candidate not in possible_plugin_paths:
                        possible_plugin_paths.append(candidate)
        for plugin_path in possible_plugin_paths:
            platforms_dir = os.path.join(plugin_path, "platforms")
            if os.path.exists(platforms_dir):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path
                _write_log(f"Qt plugins path set: {plugin_path}")
                return
        _write_log("Warning: Qt plugins path not found")
    except Exception as e:
        _write_log(f"Warning: failed to setup Qt plugins path: {e}")


def get_qapplication():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        _setup_qt_plugins()
        _write_log("Creating new QApplication")
        app = QApplication(sys.argv)
    else:
        _write_log("Reusing existing QApplication")
    return app


def _store_window_ref(win):
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setProperty("_CADBoard_window", win)
    except Exception:
        pass
    sys._CADBoard_window = win


def _get_window_ref():
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            win = app.property("_CADBoard_window")
            if win is not None:
                return win
    except Exception:
        pass
    return getattr(sys, "_CADBoard_window", None)


def _clear_window_ref():
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setProperty("_CADBoard_window", None)
    except Exception:
        pass
    if hasattr(sys, "_CADBoard_window"):
        del sys._CADBoard_window


def run():
    _write_log("=" * 50)
    _write_log("CADBoard run() started")
    try:
        _write_log("Importing board module...")
        from board import CADBoardWindow
        _write_log("Board module imported OK")
        app = get_qapplication()
        existing = _get_window_ref()
        if existing is not None:
            try:
                _write_log("Closing existing window")
                existing.close()
            except Exception as e:
                _write_log(f"Warning: failed to close old window: {e}")
            _clear_window_ref()
        _write_log("Creating CADBoardWindow...")
        window = CADBoardWindow()
        _store_window_ref(window)
        window.show()
        window.raise_()
        window.activateWindow()
        _write_log("Window shown successfully, starting event loop...")
        try:
            sys.exit(app.exec_())
        except SystemExit:
            pass
    except Exception as e:
        error_detail = traceback.format_exc()
        _write_log(f"ERROR in run(): {e}\n{error_detail}")
        raise


if __name__ == '__main__':
    _write_log("main.py loaded, calling run()...")
    try:
        run()
    except Exception as e:
        _write_log(f"run() FAILED: {e}")
        try:
            crash_file = os.path.join(_current_dir, "CADBoard_CRASH.txt")
            with open(crash_file, "w", encoding="utf-8") as f:
                f.write("CADBoard 插件启动失败！\n")
                f.write("=" * 50 + "\n")
                f.write(f"错误: {e}\n\n")
                f.write("详细错误信息:\n")
                f.write(traceback.format_exc())
                f.write("\n\n排查建议:\n")
                f.write("1. 检查 PyQt5 是否已安装\n")
                f.write("2. 检查 CADBoard_error.log 获取完整日志\n")
                f.write("3. 尝试点击'自动配置环境'按钮安装依赖\n")
        except Exception:
            pass
