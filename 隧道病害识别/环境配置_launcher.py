# -*- coding: utf-8 -*-
"""自动环境配置 — 面板入口（BIMBase 兼容版）。

设计目标：在新电脑上（BIMBase 内置 Python 缺 torch/ultralytics 等依赖、
甚至「隧道病害识别」对话框因缺库打不开）也能独立运行——本脚本只依赖
标准库 + PyQt5（BIMBase 自带）+ 同目录 env_setup.py，绝不 import 重病害模块。

点击后：检查依赖 → 补 pip → 修 _pth → 安装（torch CPU / ultralytics 8.0.145 /
opencv / Pillow / numpy，清华镜像）→ 子进程验证 → 报告。
"""
import sys
import os
import traceback
import io

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["LC_ALL"] = "en_US.UTF-8"
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleCP(65001)
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass
if sys.stdout is None:
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
if sys.stderr is None:
    sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")

_current_dir = os.path.dirname(os.path.abspath(__file__))
_log_file = os.path.join(_current_dir, "tunnel_disease_debug.log")


def _log(msg):
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [ENV] {msg}\n")
    except Exception:
        pass


def _winmsg(title, text, icon=0x40):
    """Windows API 弹窗（不依赖 Qt，最后兜底）"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x0 | icon)
    except Exception:
        pass


_log("=" * 60)
_log("ENV SETUP STARTED")
_log(f"exe={sys.executable}")

if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# ---- Qt 环境引导（与主入口一致；PyQt5 由 BIMBase 自带）----
try:
    if not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        import importlib.util
        spec = importlib.util.find_spec("PyQt5")
        pyqt5_root = os.path.dirname(spec.origin) if (spec and spec.origin) else None
        paths_to_try = []
        if pyqt5_root:
            paths_to_try += [os.path.join(pyqt5_root, "Qt5", "plugins"),
                             os.path.join(pyqt5_root, "Qt", "plugins")]
        paths_to_try.append(r"D:\BIMBASE\BIMBase建模软件 2025\PythonScript\python-3.7.9-embed-amd64\Lib\site-packages\PyQt5\Qt5\plugins")
        paths_to_try.append(r"D:\BIMBASE\BIMBase建模软件 2025\PLATFORM\QTBoot")
        for sp in sys.path:
            if os.path.isdir(sp):
                for sub in ("PyQt5", "PyQt6"):
                    for qv in ("Qt5", "Qt"):
                        p = os.path.join(sp, sub, qv, "plugins")
                        if p not in paths_to_try:
                            paths_to_try.append(p)
        for p in paths_to_try:
            if os.path.exists(os.path.join(p, "platforms", "qwindows.dll")):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = p
                break
    if "QT_QPA_PLATFORM_PLUGIN_PATH" in os.environ:
        for sub in ("bin",):
            bp = os.path.join(os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"], sub)
            if os.path.isdir(bp) and bp not in os.environ.get("PATH", ""):
                os.environ["PATH"] = bp + os.pathsep + os.environ.get("PATH", "")
except Exception as e:
    _log(f"Qt env bootstrap warning: {e}")


def _run_setup_with_qt():
    from PyQt5.QtWidgets import (QApplication, QProgressDialog, QMessageBox)
    app = QApplication.instance() or QApplication(sys.argv)

    import env_setup

    reply = QMessageBox.question(
        None, "自动配置环境",
        "将检查并自动安装病害识别所需依赖：\n"
        "  torch(CPU) / ultralytics 8.0.145 / opencv / Pillow / numpy 等\n\n"
        "  • 首次安装约需 10~30 分钟，期间请保持联网\n"
        "  • 装好后重新点击「隧道病害识别」即可打开\n\n"
        "是否继续？")
    if reply != QMessageBox.Yes:
        return

    prog = QProgressDialog("正在检查环境...", None, 0, 0, None)
    prog.setWindowTitle("自动配置环境")
    prog.setMinimumDuration(0)
    prog.setMinimumWidth(520)
    prog.setValue(0)
    prog.show()

    report_lines = []

    def _log_cb(msg):
        report_lines.append(msg)
        prog.setLabelText(msg if len(msg) <= 90 else "..." + msg[-87:])
        prog.setValue(prog.value() + 1)
        app.processEvents()

    try:
        ok, report = env_setup.auto_setup(log_cb=_log_cb)
    except Exception as e:
        ok, report = False, f"配置过程异常: {e}\n{traceback.format_exc()}"
    finally:
        prog.close()

    _log(report)
    if ok:
        QMessageBox.information(
            None, "环境配置完成",
            "✓ 依赖已就绪。\n\n现在可以点击「隧道病害识别」正常使用了。\n"
            "（若仍提示缺库，请重启 BIMBase 后再试）\n\n"
            "详细日志: tunnel_disease_debug.log")
    else:
        QMessageBox.warning(
            None, "环境配置未完成",
            "部分依赖安装失败，联网后可重试本按钮。\n\n"
            "详细日志: tunnel_disease_debug.log\n\n"
            "----- 报告尾部 -----\n" + "\n".join(report_lines[-12:]))


def _run_setup_headless():
    """Qt 不可用时的兜底：优先用 python.exe 弹控制台窗口实时显示安装进度，
    找不到 python.exe 才退回静默安装；装完后检测 PyQt5 并给出对应提示"""
    import subprocess
    py_console = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                              "python.exe")

    if os.path.isfile(py_console):
        _winmsg("自动配置环境",
                "当前环境缺少 PyQt5，无法显示图形进度窗口。\n\n"
                "点击确定后会弹出一个黑色控制台窗口，实时滚动显示下载/安装进度。\n"
                "首次安装约需 10~30 分钟，请保持联网，且不要关闭该窗口。")
        runner = (
            "import sys; sys.path.insert(0, {d!r});"
            "import env_setup;"
            "ok, _r = env_setup.auto_setup();"
            "print(); print('=' * 50);"
            "print('配置结果: ' + ('成功' if ok else '失败（联网后可重新点击本按钮重试）'));"
            "input('按回车键关闭本窗口 ...');"
            "sys.exit(0 if ok else 1)"
        ).format(d=_current_dir)
        proc = subprocess.Popen(
            [py_console, "-u", "-c", runner],
            cwd=_current_dir,
            creationflags=0x00000010,  # CREATE_NEW_CONSOLE
        )
        ok = proc.wait() == 0
    else:
        _winmsg("自动配置环境",
                "当前环境缺少 PyQt5，无法显示进度窗口。\n\n"
                "将以静默方式先安装所需依赖，首次安装约需 10~30 分钟，请保持联网。\n"
                "安装完成后会自动检测 PyQt5 是否恢复。")
        import env_setup
        ok, report = env_setup.auto_setup(log_cb=_log)
        _log(report)

    if ok:
        try:
            import PyQt5
            has_pyqt5 = True
        except Exception:
            has_pyqt5 = False
        if has_pyqt5:
            _winmsg("环境配置完成",
                    "依赖已就绪，PyQt5 已恢复可用。\n"
                    "请重新点击「隧道病害识别」打开主界面。\n"
                    "详细日志: tunnel_disease_debug.log")
        else:
            _winmsg("环境配置完成",
                    "依赖已安装完成，但 PyQt5 仍不可用。\n"
                    "请重启 BIMBase 后再点击「隧道病害识别」。\n"
                    "详细日志: tunnel_disease_debug.log")
    else:
        _winmsg("环境配置未完成",
                "部分依赖安装失败，联网后重试。\n"
                "详细日志: tunnel_disease_debug.log", icon=0x10)


def _acquire_lock():
    """防止重复点击导致多个配置进程并发安装（pip 并发会互相破坏）。
    锁文件 40 分钟未更新视为上次异常中断，允许重新运行。"""
    import time
    lock = os.path.join(_current_dir, "_env_setup.lock")
    try:
        if os.path.isfile(lock):
            age = time.time() - os.path.getmtime(lock)
            if age < 40 * 60:
                _winmsg("自动配置环境",
                        "环境配置正在进行中，请勿重复点击。\n\n"
                        "若上次配置异常中断，请删除以下文件后重试：\n" + lock,
                        icon=0x30)
                return None
        with open(lock, "w") as f:
            f.write(str(os.getpid()))
        return lock
    except Exception:
        return os.path.join(_current_dir, "_env_setup.lock")  # 出错则不阻塞


def _release_lock(lock):
    try:
        if lock and os.path.isfile(lock):
            os.remove(lock)
    except Exception:
        pass


if __name__ == "__main__":
    _lock = _acquire_lock()
    if _lock is None:
        _log("已有配置进程在运行，本次退出")
    else:
        try:
            try:
                _run_setup_with_qt()
            except Exception as e:
                if isinstance(e, ModuleNotFoundError) and getattr(e, "name", None) == "PyQt5":
                    _log("PyQt5 暂不可用，将以无界面模式安装依赖；安装完成后会再次检测 PyQt5。")
                else:
                    _log(f"Qt 环境启动异常: {e}\n{traceback.format_exc()}")
                try:
                    _run_setup_headless()
                except Exception as e2:
                    _log(f"headless path failed: {e2}\n{traceback.format_exc()}")
                    _winmsg("自动配置环境 - 错误",
                            f"配置失败: {e2}\n\n日志: {_log_file}", icon=0x10)
        finally:
            _release_lock(_lock)
    _log("ENV SETUP ENDED")
