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

    # 清除可能已被污染的同名模块缓存（AI_Modeling 的组件类模块已改名为 aim_bimbase_sync，
    # 与 CADBoard 的 bimbase_sync 不再冲突，切勿再清理 bimbase_sync）
    for key in list(sys.modules.keys()):
        if key == 'aim_bimbase_sync' or key.startswith('ai_modeling'):
            _log(f"_load_ai_main: clearing cached module {key}")
            del sys.modules[key]

    spec = importlib.util.spec_from_file_location("ai_modeling_main", ai_main_path)
    ai_main = importlib.util.module_from_spec(spec)
    sys.modules['ai_modeling_main'] = ai_main
    spec.loader.exec_module(ai_main)
    return ai_main


# 建模动作 → AIModelingWindow 本地执行方法 的映射
_ACTION_METHODS = {
    'create': '_execute_local_create',
    'copy': '_execute_local_copy',
    'modify': '_execute_local_modify',
    'delete': '_execute_local_delete',
    'move': '_execute_local_move',
}


def execute_modeling_action(parsed, original_text=""):
    """
    在 AI_Modeling 窗口的上下文中执行结构化建模命令（通用版）。
    支持 create / copy / modify / delete / move 五种本地动作，
    每次都新建一个临时 AI 窗口、执行、关闭，以获得确定性的返回结果，
    避免与已有的 AI 窗口引用冲突。

    parsed 格式与 AIModelingWindow._execute_local_* 一致，例如：
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

    _log(f"execute_modeling_action: parsed={parsed}")

    action = (parsed or {}).get('action')
    method_name = _ACTION_METHODS.get(action)
    if not method_name:
        return False, f"不支持的建模动作: {action}"

    try:
        # 快照模块环境：AI_Modeling 与 CADBoard 存在同名模块（bimbase_sync 等），
        # _load_ai_main 会重排 sys.path 并清缓存，执行后必须恢复，
        # 否则画板同步等链路会把组件类解析到 AI_Modeling 的同名模块而失败
        _saved_path = list(sys.path)
        _saved_mods = {k: sys.modules.get(k) for k in ('bimbase_sync', 'component_registry')}
        ai_main = _load_ai_main()
        try:
            from ai_modeling.ai_window import AIModelingWindow
        except Exception as e:
            _log(f"execute_modeling_action: cannot import AIModelingWindow: {e}")
            return False, f"无法导入 AIModelingWindow: {e}"
        window = AIModelingWindow()
        # 隐藏执行：移到屏幕外再 show，不抢占用户焦点
        # （pyp3d 的 place_to/_PlaceToDirect 需要窗口进入事件循环，但不能完全不用窗口）
        window.move(-32000, -32000)
        window.show()

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
                _log(f"execute_modeling_action[{action}]: entity count before={before}")
                getattr(window, method_name)(parsed, original_text)
                after = _count_entities()
                _log(f"execute_modeling_action[{action}]: entity count after={after}")
                if action == 'create':
                    # before < 0：实体计数不可用（pyp3d 计数接口失败），
                    # 执行无异常即视为成功（否则放置成功也会误报"未检测到新实体"）
                    if before < 0:
                        result[0] = True
                        result[1] = "AI_Modeling 执行完成（实体计数不可用，按无异常判定）"
                    elif after > before:
                        result[0] = True
                        result[1] = f"AI_Modeling 执行完成，新增 {after - before} 个实体"
                    else:
                        result[0] = False
                        result[1] = "AI_Modeling 执行后未检测到新实体"
                elif action == 'copy':
                    if before < 0 or after > before:
                        result[0] = True
                        result[1] = "AI_Modeling 复制执行完成"
                    else:
                        result[0] = False
                        result[1] = "AI_Modeling 复制后未检测到新实体"
                elif action == 'delete':
                    # 实体计数对删除不可靠（BIMBase 代理实体可能延迟回收），
                    # 删除只要执行无异常、实体数未增加即视为成功
                    if before < 0 or after <= before:
                        result[0] = True
                        result[1] = "AI_Modeling 删除执行完成"
                    else:
                        result[0] = False
                        result[1] = "AI_Modeling 删除后实体数量异常增加"
                else:  # modify/move：不引起实体数变化，无异常即视为成功
                    result[0] = True
                    if action == 'move':
                        result[1] = "AI_Modeling 移动执行完成"
                    else:
                        result[1] = "AI_Modeling 修改执行完成"
            except Exception as e:
                result[0] = False
                result[1] = f"AI_Modeling 执行失败: {e}"
                _log(f"execute_modeling_action _do_exec error: {e}\n{traceback.format_exc()}")
            finally:
                try:
                    window.accept()
                except Exception:
                    pass

        QTimer.singleShot(0, _do_exec)
        _log(f"execute_modeling_action[{action}]: entering AI window exec_()")
        window.exec_()
        _log(f"execute_modeling_action[{action}]: exec_() returned, result={result}")
        return result[0], result[1]
    except Exception as e:
        tb = traceback.format_exc()
        _log(f"execute_modeling_action error: {e}\n{tb}")
        return False, f"AI_Modeling 代理执行失败: {e}"
    finally:
        # 恢复 CADBoard 的模块环境，避免 AI_Modeling 的同名模块污染画板同步链路
        sys.path[:] = _saved_path
        for _k, _v in _saved_mods.items():
            if _v is None:
                sys.modules.pop(_k, None)
            else:
                sys.modules[_k] = _v


def execute_parsed_command(parsed, original_text=""):
    """兼容入口：创建命令，委托给 execute_modeling_action。"""
    return execute_modeling_action(parsed, original_text)


def execute_text_command(text):
    """
    在 AI_Modeling 窗口的上下文中执行自然语言命令。
    支持 create / copy / modify / delete / move 五种本地动作。
    返回: (success: bool, message: str)
    """
    try:
        _load_ai_main()  # 确保 AI_Modeling 目录在 sys.path 且模块缓存干净
        from ai_modeling.command_parser import ModelingCommandParser
        parsed = ModelingCommandParser.parse(text)
        if parsed and parsed.get('action') in _ACTION_METHODS:
            return execute_modeling_action(parsed, text)
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
        # 快照模块环境（同 execute_modeling_action），执行后恢复，避免污染画板同步链路
        _saved_path = list(sys.path)
        _saved_mods = {k: sys.modules.get(k) for k in ('bimbase_sync', 'component_registry')}
        ai_main = _load_ai_main()
        try:
            from ai_modeling.ai_window import AIModelingWindow
        except Exception as e:
            _log(f"execute_callback_in_ai_window: cannot import AIModelingWindow: {e}")
            return False, f"无法导入 AIModelingWindow: {e}"
        window = AIModelingWindow()
        # 隐藏执行：移到屏幕外再 show，不抢占用户焦点
        # （pyp3d 的 place_to/_PlaceToDirect 需要窗口进入事件循环，但不能完全不用窗口）
        window.move(-32000, -32000)
        window.show()

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
    finally:
        # 恢复 CADBoard 的模块环境，避免 AI_Modeling 的同名模块污染画板同步链路
        sys.path[:] = _saved_path
        for _k, _v in _saved_mods.items():
            if _v is None:
                sys.modules.pop(_k, None)
            else:
                sys.modules[_k] = _v


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
