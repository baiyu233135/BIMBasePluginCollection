# -*- coding: utf-8 -*-
"""
BIMBase AI智能建模助手 - 独立插件入口
"""
import sys
import os
import traceback

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# 把插件根目录写入环境变量，供 config.py 等定位本地配置文件
os.environ['AI_MODELING_PLUGIN_DIR'] = _current_dir

_LOG_FILE = os.path.join(_current_dir, "ai_modeling.log")


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
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            _setup_qt_plugins()
            _write_log("Creating new QApplication")
            app = QApplication(sys.argv)
        else:
            _write_log("Reusing existing QApplication")
        return app
    except ImportError:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            _setup_qt_plugins()
            app = QApplication(sys.argv)
        return app


def _store_window_ref(win):
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setProperty("_AIModeling_window", win)
    except Exception:
        pass
    sys._AIModeling_window = win


def _get_window_ref():
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            win = app.property("_AIModeling_window")
            if win is not None:
                return win
    except Exception:
        pass
    return getattr(sys, "_AIModeling_window", None)


def _clear_window_ref():
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setProperty("_AIModeling_window", None)
    except Exception:
        pass
    if hasattr(sys, "_AIModeling_window"):
        del sys._AIModeling_window


def run():
    _write_log("=" * 50)
    _write_log("AI Modeling run() started")
    try:
        from ai_modeling.ai_window import AIModelingWindow
        _write_log("AIModelingWindow imported OK")
        app = get_qapplication()
        existing = _get_window_ref()
        if existing is not None:
            try:
                _write_log("Raising existing window")
                existing.show()
                existing.raise_()
                existing.activateWindow()
                return
            except Exception as e:
                _write_log(f"Warning: failed to raise old window: {e}")
                _clear_window_ref()
        _write_log("Creating AIModelingWindow...")
        window = AIModelingWindow()
        _store_window_ref(window)
        window.show()
        window.raise_()
        window.activateWindow()
        _write_log("Window shown, entering exec_()...")
        # 使用 exec_() 进入模态事件循环，确保窗口稳定存在直到关闭
        window.exec_()
        _write_log("exec_() returned, window closed")
    except Exception as e:
        error_detail = traceback.format_exc()
        _write_log(f"ERROR in run(): {e}\n{error_detail}")
        raise


if __name__ == '__main__':
    _write_log("main.py loaded, calling run()...")
    run()
