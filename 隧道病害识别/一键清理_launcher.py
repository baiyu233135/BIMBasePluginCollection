# -*- coding: utf-8 -*-
"""一键清理 — 面板入口（BIMBase 兼容版）。

清理插件运行中产生的临时文件：调试日志、__pycache__、环境配置临时文件；
病害标记记录 / 人工标注结果 / 数字孪生生成文件属于用户数据，默认不勾，
需用户显式勾选后才会删除。

只依赖标准库 + PyQt5（BIMBase 自带），不 import 任何插件业务模块。
"""
import sys
import os
import traceback
import io

os.environ["PYTHONIOENCODING"] = "utf-8"
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
            f.write(f"[{ts}] [CLEAN] {msg}\n")
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
_log("CLEANUP STARTED")
_log(f"exe={sys.executable}")

# ---- Qt 环境引导（与 环境配置_launcher.py 一致）----
try:
    if not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        import importlib.util
        spec = importlib.util.find_spec("PyQt5")
        pyqt5_root = os.path.dirname(spec.origin) if (spec and spec.origin) else None
        paths_to_try = []
        if pyqt5_root:
            paths_to_try += [os.path.join(pyqt5_root, "Qt5", "plugins"),
                             os.path.join(pyqt5_root, "Qt", "plugins")]
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
        bp = os.path.join(os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"], "bin")
        if os.path.isdir(bp) and bp not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bp + os.pathsep + os.environ.get("PATH", "")
except Exception as e:
    _log(f"Qt env bootstrap warning: {e}")


# ---------------- 清理目标定义 ----------------

class CleanTarget:
    """一项可清理内容。
    kind: 'files' 删除列出的文件；'dirs' 整个目录删除；
          'dir_contents' 清空目录内容但保留目录本身。
    """
    def __init__(self, key, label, kind, paths, default=True, warning=""):
        self.key = key
        self.label = label
        self.kind = kind
        self.paths = paths
        self.default = default
        self.warning = warning


def _find_pycache_dirs(root):
    found = []
    for dirpath, dirnames, _filenames in os.walk(root):
        for d in list(dirnames):
            if d == "__pycache__":
                found.append(os.path.join(dirpath, d))
                dirnames.remove(d)  # 不再深入
    return found


def _build_targets():
    p = _current_dir
    logs = [os.path.join(p, n) for n in os.listdir(p)
            if n.endswith("_debug.log") and os.path.isfile(os.path.join(p, n))]
    env_tmp = [os.path.join(p, n) for n in ("_get_pip.py", "_env_setup.lock")
               if os.path.isfile(os.path.join(p, n))]
    return [
        CleanTarget("logs", "调试日志（*_debug.log）", "files", logs,
                    default=True),
        CleanTarget("pycache", "Python 缓存（__pycache__）", "dirs",
                    _find_pycache_dirs(p), default=True),
        CleanTarget("env_tmp", "环境配置临时文件（_get_pip.py / 锁文件）",
                    "files", env_tmp, default=True),
        CleanTarget("records", "病害标记记录（tunnel_disease_records.json）",
                    "files", [os.path.join(p, "tunnel_disease_records.json")],
                    default=False,
                    warning="删除后病害标记列表将清空，不可恢复"),
        CleanTarget("manual", "人工标注结果（人工标好/images、labels 内容）",
                    "dir_contents",
                    [os.path.join(p, "人工标好", "images"),
                     os.path.join(p, "人工标好", "labels")],
                    default=False, warning="删除后已标注的图片和标签将丢失"),
        CleanTarget("twin", "数字孪生生成文件（隧道数字孪生.html）",
                    "files", [os.path.join(p, "数字孪生", "隧道数字孪生.html")],
                    default=False, warning="删除后需重新生成数字孪生页面"),
    ]


def _target_size(target):
    """计算目标当前占用的字节数。"""
    total = 0
    if target.kind == "files":
        for f in target.paths:
            if os.path.isfile(f):
                try:
                    total += os.path.getsize(f)
                except OSError:
                    pass
    else:
        for d in target.paths:
            if not os.path.isdir(d):
                continue
            for dirpath, _dirnames, filenames in os.walk(d):
                for n in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, n))
                    except OSError:
                        pass
    return total


def _fmt_size(n):
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1024.0 / 1024.0)
    if n >= 1024:
        return "%.1f KB" % (n / 1024.0)
    return "%d B" % n


def _do_cleanup(targets):
    """执行清理。返回 (释放字节数, 删除条数, [错误描述...])。"""
    import shutil
    freed = 0
    count = 0
    errors = []
    for t in targets:
        if t.kind == "files":
            for f in t.paths:
                if not os.path.isfile(f):
                    continue
                try:
                    sz = os.path.getsize(f)
                    os.remove(f)
                    freed += sz
                    count += 1
                except Exception as e:
                    errors.append("%s: %s" % (os.path.basename(f), e))
        elif t.kind == "dirs":
            for d in t.paths:
                if not os.path.isdir(d):
                    continue
                try:
                    sz = _target_size(CleanTarget("", "", "dir_contents", [d]))
                    shutil.rmtree(d)
                    freed += sz
                    count += 1
                except Exception as e:
                    errors.append("%s: %s" % (os.path.basename(d), e))
        else:  # dir_contents：清空内容但保留目录
            for d in t.paths:
                if not os.path.isdir(d):
                    continue
                for name in os.listdir(d):
                    sub = os.path.join(d, name)
                    try:
                        if os.path.isdir(sub):
                            sz = _target_size(CleanTarget("", "", "dir_contents", [sub]))
                            shutil.rmtree(sub)
                        else:
                            sz = os.path.getsize(sub)
                            os.remove(sub)
                        freed += sz
                        count += 1
                    except Exception as e:
                        errors.append("%s: %s" % (name, e))
    return freed, count, errors


# ---------------- Qt 界面 ----------------

def _run_with_qt():
    from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QCheckBox,
                                 QLabel, QDialogButtonBox, QMessageBox)
    app = QApplication.instance() or QApplication(sys.argv)

    targets = _build_targets()

    dlg = QDialog(None)
    dlg.setWindowTitle("一键清理")
    dlg.setMinimumWidth(560)
    layout = QVBoxLayout(dlg)

    layout.addWidget(QLabel("勾选要清理的内容（用户数据默认不勾，删除后不可恢复）："))

    checks = []
    for t in targets:
        sz = _target_size(t)
        text = "%s — 当前 %s" % (t.label, _fmt_size(sz))
        if t.warning:
            text += "\n    ⚠ " + t.warning
        cb = QCheckBox(text)
        cb.setChecked(t.default)
        if t.warning:
            cb.setStyleSheet("QCheckBox { color: #b03030; }")
        layout.addWidget(cb)
        checks.append((cb, t))

    hint = QLabel("说明：日志和缓存删除后不影响任何功能；"
                  "带 ⚠ 的是用户数据，请确认后再勾。")
    hint.setStyleSheet("QLabel { color: #777; }")
    hint.setWordWrap(True)
    layout.addWidget(hint)

    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.button(QDialogButtonBox.Ok).setText("开始清理")
    btns.button(QDialogButtonBox.Cancel).setText("取消")
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)

    if dlg.exec_() != QDialog.Accepted:
        _log("用户取消清理")
        return

    selected = [t for cb, t in checks if cb.isChecked()]
    if not selected:
        QMessageBox.information(None, "一键清理", "未勾选任何内容。")
        return

    # 勾选了用户数据时二次确认
    risky = [t for t in selected if t.warning]
    if risky:
        names = "\n".join("  • " + t.label for t in risky)
        r = QMessageBox.warning(
            None, "确认删除用户数据",
            "以下内容删除后不可恢复：\n%s\n\n确定继续吗？" % names,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            _log("用户在二次确认中取消")
            return

    freed, count, errors = _do_cleanup(selected)
    _log("清理完成: 删除 %d 项, 释放 %s, 错误 %d 个"
         % (count, _fmt_size(freed), len(errors)))

    msg = "清理完成。\n\n删除 %d 项，释放空间 %s。" % (count, _fmt_size(freed))
    if errors:
        msg += "\n\n以下 %d 项删除失败（可能正在使用）：\n" % len(errors)
        msg += "\n".join(errors[:8])
    QMessageBox.information(None, "一键清理", msg)


def _run_headless():
    """Qt 不可用时的兜底：只清安全项（绝不碰用户数据）"""
    r = ctypes_msgbox_yn(
        "一键清理",
        "Qt 不可用，将以简单模式清理日志和缓存（不会动标记记录等用户数据）。\n\n"
        "是否继续？")
    if not r:
        return
    targets = [t for t in _build_targets() if t.default]
    freed, count, errors = _do_cleanup(targets)
    _log("headless 清理完成: 删除 %d 项, 释放 %s" % (count, _fmt_size(freed)))
    msg = "清理完成：删除 %d 项，释放 %s。" % (count, _fmt_size(freed))
    if errors:
        msg += "\n%d 项失败（文件可能被占用）。" % len(errors)
    _winmsg("一键清理", msg)


def ctypes_msgbox_yn(title, text):
    try:
        import ctypes
        return ctypes.windll.user32.MessageBoxW(0, text, title, 0x4 | 0x20) == 6
    except Exception:
        return False


if __name__ == "__main__":
    try:
        _run_with_qt()
    except Exception as e:
        if isinstance(e, ModuleNotFoundError) and getattr(e, "name", None) == "PyQt5":
            _log("PyQt5 不可用，使用简单模式清理")
        else:
            _log(f"Qt path failed: {e}\n{traceback.format_exc()}")
        try:
            _run_headless()
        except Exception as e2:
            _log(f"headless path failed: {e2}\n{traceback.format_exc()}")
            _winmsg("一键清理 - 错误", f"清理失败: {e2}", icon=0x10)
    _log("CLEANUP ENDED")
