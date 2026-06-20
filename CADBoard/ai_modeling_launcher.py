# -*- coding: utf-8 -*-
"""
AI智能建模助手启动器 / CADBoard 代理执行入口

- 被 BIMPyPlugin.xml 调用时：直接打开 AI_Modeling 窗口。
- 被 CADBoard 调用时：把结构化命令转发到 AI_Modeling 窗口执行，复用其已验证的放置上下文。
"""
import sys
import os
import traceback
import importlib.util

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# AI_Modeling 入口同样依赖 pyp3d _Core，提前确保 PID 正确
from utils.bimbase_pid import ensure_bimbase_pid_argv
ensure_bimbase_pid_argv()

_log_file = os.path.join(_current_dir, "ai_modeling_launcher.log")


def _log(msg):
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _get_ai_main_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'AI_Modeling', 'main.py'
    )


def _load_ai_main():
    """加载 AI_Modeling/main.py，返回模块对象。
    加载前清除 bimbase_sync / ai_modeling 缓存，避免 CADBoard 的同名模块被复用。"""
    ai_main_path = _get_ai_main_path()
    if not os.path.exists(ai_main_path):
        raise FileNotFoundError(f"找不到 {ai_main_path}")

    ai_dir = os.path.dirname(ai_main_path)
    # 确保 AI_Modeling 目录在 sys.path 最前面
    if ai_dir in sys.path:
        sys.path.remove(ai_dir)
    sys.path.insert(0, ai_dir)

    # 清除可能已被 CADBoard 污染的同名模块缓存
    for key in list(sys.modules.keys()):
        if key == 'bimbase_sync' or key.startswith('ai_modeling'):
            _log(f"_load_ai_main: clearing cached module {key}")
            del sys.modules[key]

    spec = importlib.util.spec_from_file_location("ai_modeling_main", ai_main_path)
    ai_main = importlib.util.module_from_spec(spec)
    sys.modules['ai_modeling_main'] = ai_main
    spec.loader.exec_module(ai_main)
    return ai_main


def execute_parsed_command(parsed, original_text=""):
    """
    在 AI_Modeling 窗口的上下文中执行结构化创建命令。
    每次都新建一个临时 AI 窗口、执行、关闭，以获得确定性的返回结果，
    避免与已有的 AI 窗口引用冲突。

    parsed 格式与 AIModelingWindow._execute_local_create 一致，例如：
      {
        'action': 'create',
        'component_type': 'cylinder',
        'params': {'radius': 2.0, 'height': 5.0},
        'position': {'mode': 'absolute', 'x': 0, 'y': 0, 'z': 0},
        'array': {'mode': 'linear', 'axis': 'x', 'spacing': 10.0, 'count': 5},
        'route': None,
      }

    返回: (success: bool, message: str)
    """
    try:
        from PyQt5.QtCore import QTimer
    except ImportError:
        from PyQt6.QtCore import QTimer

    _log(f"execute_parsed_command: parsed={parsed}")

    try:
        ai_main = _load_ai_main()
        try:
            from ai_modeling.ai_window import AIModelingWindow
        except Exception as e:
            _log(f"execute_parsed_command: cannot import AIModelingWindow: {e}")
            return False, f"无法导入 AIModelingWindow: {e}"
        window = AIModelingWindow()
        window.show()
        window.raise_()
        window.activateWindow()

        result = [False, ""]

        def _count_entities():
            try:
                from pyp3d import get_all_instancekey, get_all_entityid
                keys = get_all_instancekey()
                if keys is not None:
                    return len(keys)
                ids = get_all_entityid()
                if ids is not None:
                    return len(ids)
            except Exception as e:
                _log(f"_count_entities failed: {e}")
            return -1

        def _do_exec():
            try:
                before = _count_entities()
                _log(f"execute_parsed_command: entity count before={before}")
                window._execute_local_create(parsed, original_text)
                after = _count_entities()
                _log(f"execute_parsed_command: entity count after={after}")
                if after > before:
                    result[0] = True
                    result[1] = f"AI_Modeling 执行完成，新增 {after - before} 个实体"
                else:
                    result[0] = False
                    result[1] = "AI_Modeling 执行后未检测到新实体"
            except Exception as e:
                result[0] = False
                result[1] = f"AI_Modeling 执行失败: {e}"
                _log(f"execute_parsed_command _do_exec error: {e}\n{traceback.format_exc()}")
            finally:
                try:
                    window.accept()
                except Exception:
                    pass

        QTimer.singleShot(0, _do_exec)
        _log("execute_parsed_command: entering AI window exec_()")
        window.exec_()
        _log(f"execute_parsed_command: exec_() returned, result={result}")
        return result[0], result[1]
    except Exception as e:
        tb = traceback.format_exc()
        _log(f"execute_parsed_command error: {e}\n{tb}")
        return False, f"AI_Modeling 代理执行失败: {e}"


def execute_text_command(text):
    """
    在 AI_Modeling 窗口的上下文中执行自然语言命令。
    返回: (success: bool, message: str)
    """
    try:
        from ai_modeling.command_parser import ModelingCommandParser
        parsed = ModelingCommandParser.parse(text)
        if parsed and parsed.get('action') == 'create' and parsed.get('component_type'):
            return execute_parsed_command(parsed, text)
        return False, "无法解析为本地可执行命令"
    except Exception as e:
        return False, f"execute_text_command error: {e}"


def execute_callback_in_ai_window(callback, *args, **kwargs):
    """
    新建临时 AI_Modeling 窗口，在其事件循环中执行任意回调，然后关闭。
    用于 CADBoard 自己的非实体组件（Polygon 等）放置，借用 AI 窗口的 pyp3d 上下文。
    返回: callback 返回的 (success, message)
    """
    try:
        from PyQt5.QtCore import QTimer
    except ImportError:
        from PyQt6.QtCore import QTimer

    _log(f"execute_callback_in_ai_window: callback={callback}")

    try:
        ai_main = _load_ai_main()
        try:
            from ai_modeling.ai_window import AIModelingWindow
        except Exception as e:
            _log(f"execute_callback_in_ai_window: cannot import AIModelingWindow: {e}")
            return False, f"无法导入 AIModelingWindow: {e}"
        window = AIModelingWindow()
        window.show()
        window.raise_()
        window.activateWindow()

        result = [False, ""]

        def _count_entities():
            try:
                from pyp3d import get_all_instancekey, get_all_entityid
                keys = get_all_instancekey()
                if keys is not None:
                    return len(keys)
                ids = get_all_entityid()
                if ids is not None:
                    return len(ids)
            except Exception as e:
                _log(f"_count_entities failed: {e}")
            return -1

        def _do_exec():
            try:
                before = _count_entities()
                _log(f"execute_callback_in_ai_window: entity count before={before}")
                result[0], result[1] = callback(*args, **kwargs)
                after = _count_entities()
                _log(f"execute_callback_in_ai_window: entity count after={after}, callback ok={result[0]}")
                # 如果回调自称成功但实体数没增加，仍然视为失败
                if result[0] and after <= before and before >= 0:
                    result[0] = False
                    result[1] = f"{result[1]}（未检测到新实体）"
            except Exception as e:
                result[0] = False
                result[1] = f"callback error: {e}"
                _log(f"execute_callback_in_ai_window _do_exec error: {e}\n{traceback.format_exc()}")
            finally:
                try:
                    window.accept()
                except Exception:
                    pass

        QTimer.singleShot(0, _do_exec)
        _log("execute_callback_in_ai_window: entering AI window exec_()")
        window.exec_()
        _log(f"execute_callback_in_ai_window: exec_() returned, result={result}")
        return result[0], result[1]
    except Exception as e:
        tb = traceback.format_exc()
        _log(f"execute_callback_in_ai_window error: {e}\n{tb}")
        return False, f"AI_Modeling 回调执行失败: {e}"


def launch_ai_window():
    """BIMPyPlugin 按钮入口：直接打开 AI_Modeling 窗口"""
    _log("=" * 50)
    _log("ai_modeling_launcher.py started (button entry)")
    _log(f"cwd = {os.getcwd()}")
    _log(f"sys.path top 5 = {sys.path[:5]}")

    try:
        ai_main = _load_ai_main()
        _log("ai_main module loaded")

        if not hasattr(ai_main, 'run'):
            raise AttributeError("AI_Modeling/main.py 中没有 run() 函数")

        _log("Calling ai_main.run()...")
        ai_main.run()
        _log("ai_main.run() completed")

    except Exception as e:
        tb = traceback.format_exc()
        _log(f"ERROR: {e}\n{tb}")
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "AI智能建模启动失败",
                f"错误: {e}\n\n日志文件:\n{_log_file}")
        except Exception:
            pass


# BIMPyPlugin 调用入口
if __name__ == '__main__':
    launch_ai_window()
