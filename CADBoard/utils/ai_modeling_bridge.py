# -*- coding: utf-8 -*-
"""
AI_Modeling 解析桥接层

把 AI_Modeling 的中文建模指令解析与执行能力接入 CADBoard 画板 AI 面板：
- parse_modeling_command: 只加载 AI_Modeling 的 command_parser.py
  （纯 Python + re，无 Qt/pyp3d 依赖），不触发 ai_modeling 包初始化，
  也不触碰 sys.modules 中的 bimbase_sync；
- is_modeling_action: 判断解析结果是否为可本地执行的建模动作，
  防止把闲聊/问句误判为建模指令；
- execute: 委托 ai_modeling_launcher.execute_modeling_action
  在临时 AI_Modeling 窗口上下文中执行（pyp3d 放置需要该上下文）。
"""
import os
import importlib.util

_PARSER_MODULE = None
_PARSER_LOAD_FAILED = False

# 可本地执行的建模动作
MODELING_ACTIONS = ('create', 'copy', 'modify', 'delete')


def _log(msg):
    try:
        import bimbase_sync
        bimbase_sync._log(f"[AI_BRIDGE] {msg}")
    except Exception:
        pass


def _parser_path():
    # .../pythonplugin/CADBoard/utils/ai_modeling_bridge.py
    #   → .../pythonplugin/AI_Modeling/ai_modeling/command_parser.py
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, 'AI_Modeling', 'ai_modeling', 'command_parser.py')


def _load_parser_module():
    """按文件路径加载 command_parser.py，缓存为模块级单例。"""
    global _PARSER_MODULE, _PARSER_LOAD_FAILED
    if _PARSER_MODULE is not None or _PARSER_LOAD_FAILED:
        return _PARSER_MODULE
    path = _parser_path()
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        spec = importlib.util.spec_from_file_location("ai_modeling_command_parser", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _PARSER_MODULE = mod
        _log(f"parser loaded from {path}")
    except Exception as e:
        _PARSER_LOAD_FAILED = True
        _log(f"parser load failed: {e}")
    return _PARSER_MODULE


def parse_modeling_command(text):
    """用 AI_Modeling 的解析器解析自然语言，返回 parsed dict 或 None。"""
    mod = _load_parser_module()
    if mod is None:
        return None
    try:
        return mod.ModelingCommandParser.parse(text)
    except Exception as e:
        _log(f"parse error for {text!r}: {e}")
        return None


def is_modeling_action(parsed):
    """判断解析结果是否为可本地执行的建模动作。"""
    if not isinstance(parsed, dict):
        return False
    if parsed.get('action') not in MODELING_ACTIONS:
        return False
    # create 必须有组件类型；copy/modify/delete 允许针对选中组件
    if parsed.get('action') == 'create' and not parsed.get('component_type'):
        return False
    return True


# AI JSON 颜色词 → 0~1 浮点 RGB（与 AI_Modeling 解析器的 _COLOR_MAP 对齐）
_AI_COLOR_MAP = {
    '粉红': (1.0, 0.75, 0.8), '粉': (1.0, 0.75, 0.8),
    '红': (1.0, 0.0, 0.0), '绿': (0.0, 0.8, 0.0), '蓝': (0.0, 0.0, 1.0),
    '黄': (1.0, 1.0, 0.0), '灰': (0.5, 0.5, 0.5), '白': (1.0, 1.0, 1.0),
    '黑': (0.0, 0.0, 0.0), '橙': (1.0, 0.65, 0.0), '紫': (0.5, 0.0, 0.5),
    '青': (0.0, 1.0, 1.0),
}


def _normalize_color_value(v):
    """把 AI 输出的颜色（中文词 / [r,g,b] / [r,g,b,a]，容忍 0~255 写法）归一化为 (r,g,b,a) 0~1 浮点"""
    if isinstance(v, str):
        for name, rgb in _AI_COLOR_MAP.items():
            if name in v:
                return (*rgb, 0.5 if '半透明' in v else 1.0)
        return None
    if isinstance(v, (list, tuple)) and len(v) in (3, 4):
        try:
            vals = [float(x) for x in v]
        except (TypeError, ValueError):
            return None
        if len(vals) == 3:
            vals.append(1.0)
        if any(x > 1 for x in vals[:3]):
            vals = [x / 255.0 for x in vals[:3]] + [vals[3]]
        return tuple(vals)
    return None


def execute(parsed, original_text=""):
    """在 AI_Modeling 临时窗口上下文中执行建模命令，返回 (success, message)。"""
    parsed = dict(parsed)  # 不污染调用方的 dict
    # AI JSON 兼容：modify 指令用 changes 字段，而本地执行方法读 params
    if parsed.get('action') == 'modify' and 'params' not in parsed and 'changes' in parsed:
        parsed['params'] = parsed['changes']
    # AI JSON 兼容：color 字段归一化为 (r,g,b,a) 0~1 浮点
    if 'color' in parsed:
        parsed['color'] = _normalize_color_value(parsed.get('color'))
    params = parsed.get('params')
    if isinstance(params, dict) and '颜色' in params:
        params['颜色'] = _normalize_color_value(params['颜色'])
    from ai_modeling_launcher import execute_modeling_action
    return execute_modeling_action(parsed, original_text)
