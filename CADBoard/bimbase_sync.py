# -*- coding: utf-8 -*-
"""
BIMBase参数化组件同步引擎 v8

改动：
- Phase 2: 增强反向同步，利用BIMBase实体查询API
- 统一使用 show=True, obvious=True 兼容BIMBase 2025
"""

import math
import os
import sys
import traceback
import importlib.util
from datetime import datetime

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# 在 pyp3d 初始化 _Core/Port 前，确保 sys.argv[1] 为 BIMBase 进程 PID，
# 防止 CADBoard 窗口成为前台窗口时连接到错误进程。
from utils.bimbase_pid import ensure_bimbase_pid_argv
ensure_bimbase_pid_argv()

from utils.component_registry import ComponentRegistry, apply_component_params_to_element

_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bimbase_sync_debug.log')

def _log(msg):
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

_log("=" * 60)
_log("BIMBaseSync v8 start")
_log("=" * 60)

_pyp3d_ok = False
Component = Attr = Line = Section = Sweep = Cube = Sphere = Cone = Arc = None
Vec2 = Vec3 = Point = place = scale = translate = rotation = None
get_element_from_boxselect = None
entityid_isvaid = None
get_datakey_from_entity = None
get_noumKV_from_instancekey = None

try:
    from pyp3d import (
        Component, Attr, Line, Section,
        Sweep, Cube, Sphere, Cone, Arc,
        Vec2, Vec3, Point, place, place_to, scale, translate, rotation,
        isinside_global_variable, set_global_variable,
        create_geometry, entityid_isvaid,
    )
    _pyp3d_ok = True
    _log("pyp3d imported OK")
except ImportError as e:
    _log(f"pyp3d import failed: {e}")

try:
    from pyp3d import export
except ImportError:
    def export(func):
        return func

# 实体查询 API（可能不可用）
get_element_from_boxselect = None
get_datakey_from_entity = None
get_noumKV_from_instancekey = None
get_noumenon_from_instancekey = None
get_all_instancekey = None
get_entity_property = None
get_entityid_from_boxselection = None
get_current_entityId = None

try:
    from pyp3d import (
        get_element_from_boxselect,
        entityid_isvaid,
        get_datakey_from_entity,
        get_noumKV_from_instancekey,
        get_noumenon_from_instancekey,
        get_all_instancekey,
        get_entity_property,
        get_entityid_from_boxselection,
        get_current_entityId,
    )
    _log("BIMBase entity query APIs imported OK")
except ImportError as e:
    _log(f"BIMBase entity query APIs import failed: {e}")


# ============================================================
# 直接布置 API（绕过被覆盖的 place_to，支持批量自动放置）
# ============================================================
_create_component_fn = None
_UnifiedFunction = None
_PARACMPT_PARAMETRIC_COMPONENT = None
_PARACMPT_KEYWORD_TRANSFORMATION = None
_PARACMPT_KEYWORD_DEPENDENT_FILE = None

try:
    from pyp3d import (
        create_component as _create_component_fn,
        UnifiedFunction as _UnifiedFunction,
        PARACMPT_PARAMETRIC_COMPONENT,
        PARACMPT_KEYWORD_TRANSFORMATION,
        PARACMPT_KEYWORD_DEPENDENT_FILE,
    )
    _log("BIMBase direct placement APIs imported OK")
except ImportError as e:
    _log(f"BIMBase direct placement APIs import failed: {e}")

_PlaceToDirect = None


def _ensure_pyp3d_port():
    """检查 pyp3d _Core 通信端口是否健康；若损坏则尝试重新初始化。

    当 CADBoard 窗口成为前台窗口或 BIMBase 进程变化时，已有的 _Core 可能
    指向错误/失效的 named pipe，后续 UnifiedFunction 调用会抛出
    'NoneType' object has no attribute 'send'。本函数在放置前检测并重建
    _Core 单例。
    """
    try:
        import pyp3d.runtime as _rt
        core_cls = getattr(_rt, '_Core', None)
        if core_cls is None:
            return False
        core = core_cls._ins.get(core_cls)
        if core is None:
            return False
        port = getattr(core, '_port', None)
        if port is None or getattr(port, '_pipe', None) is None:
            _log("_ensure_pyp3d_port: core port is unhealthy, reinitializing...")
            # 清除损坏的单例，让下一次 UnifiedFunction 调用重建 _Core
            core_cls._ins.pop(core_cls, None)
            ensure_bimbase_pid_argv()
            from pyp3d import UnifiedFunction, PARACMPT_PARAMETRIC_COMPONENT
            UnifiedFunction(PARACMPT_PARAMETRIC_COMPONENT, 'get_version')()
            _log("_ensure_pyp3d_port: reinitialized successfully")
        return True
    except Exception as e:
        _log(f"_ensure_pyp3d_port: failed: {e}")
        return False


def _ensure_place_to_direct():
    """延迟初始化底层 place_to 函数，使用官方 create_component + place_to。"""
    global _PlaceToDirect
    if _PlaceToDirect is not None:
        return True
    try:
        # 在放置时刻才导入，确保 BIMBase/pyp3d 已就绪
        from pyp3d import create_component, place_to as _place_to

        def _place_impl(noumenon, transform):
            _log("_place_impl: calling create_component...")
            create_component(noumenon)
            _log("_place_impl: create_component done, calling place_to...")
            _place_to(noumenon, transform)
            _log("_place_impl: place_to done")

        _PlaceToDirect = _place_impl
        _log("_PlaceToDirect initialized (lazy)")
        return True
    except Exception as e:
        _log(f"_ensure_place_to_direct failed: {e}")
        return False


def _count_entities():
    """获取当前 BIMBase 中的实体数量（用于验证放置是否真正生效）"""
    try:
        from pyp3d import get_all_instancekey
        keys = get_all_instancekey()
        if keys is not None:
            _log(f"_count_entities: get_all_instancekey returned {len(keys)} keys")
            return len(keys)
    except Exception as e:
        _log(f"_count_entities: get_all_instancekey failed: {e}")
    try:
        from pyp3d import get_all_entityid
        ids = get_all_entityid()
        if ids is not None:
            _log(f"_count_entities: get_all_entityid returned {len(ids)} ids")
            return len(ids)
    except Exception as e:
        _log(f"_count_entities: get_all_entityid failed: {e}")
    return -1


def _request_placement_coordinate(parent, defaults=(0, 0, 0)):
    """弹出 X/Y/Z 三轴坐标输入对话框（BIMBase 内嵌环境兼容版）"""
    try:
        from PyQt5.QtWidgets import (
            QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        )
        from PyQt5.QtCore import Qt
    except ImportError:
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        )
        from PyQt6.QtCore import Qt

    dx, dy, dz = [float(v) for v in defaults]
    dlg = QDialog(parent)
    dlg.setWindowTitle("输入放置坐标")
    dlg.setWindowModality(Qt.ApplicationModal)
    layout = QFormLayout(dlg)
    x_edit = QLineEdit(str(dx))
    y_edit = QLineEdit(str(dy))
    z_edit = QLineEdit(str(dz))
    layout.addRow("X:", x_edit)
    layout.addRow("Y:", y_edit)
    layout.addRow("Z:", z_edit)
    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addRow(btns)
    exec_method = getattr(dlg, 'exec_', getattr(dlg, 'exec', None))
    if exec_method and exec_method() == QDialog.Accepted:
        return (
            float(x_edit.text()),
            float(y_edit.text()),
            float(z_edit.text()),
        )
    return None


def _place_and_verify(place_fn, *args, **kwargs):
    """调用放置函数并验证实体数量确实增加"""
    before = _count_entities()
    try:
        result = place_fn(*args, **kwargs)
    except Exception as e:
        _log(f"_place_and_verify: place_fn raised: {e}")
        raise
    after = _count_entities()
    _log(f"_place_and_verify: entity count before={before}, after={after}")
    if after <= before and before >= 0:
        raise RuntimeError(f"实体数量未增加（before={before}, after={after}）")
    return result


def _set_argv_for_place():
    """place/place_to 依赖 sys.argv[0] 读取 DependentFile"""
    original = sys.argv[0]
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    sys.argv[0] = os.path.join(plugin_dir, 'bimbase_sync.py')
    return original


def _restore_argv(original):
    sys.argv[0] = original


def _auto_place_click_and_move(comp, x, y, z):
    """
    自动模拟交互放置（坐标烘焙 + place + create_geometry/SendInput 兜底）。

    关键：BIMBase 的 place() 手动工具在点击时会将组件放置到点击位置。
    为了让组件出生在目标坐标 (x,y,z)，我们先把偏移写进组件隐藏参数，
    再 replace()，这样几何体本身已经出生在目标位置；后续即使只点击视图中心，
    组件也会落在 (x,y,z)。
    """
    import time
    import ctypes
    from ctypes import wintypes

    pos = (float(x), float(y), float(z))
    _log(f"_auto_place: start pos={pos}")

    # Windows API 结构定义
    class _RECT(ctypes.Structure):
        _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                    ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ('dx', wintypes.LONG),
            ('dy', wintypes.LONG),
            ('mouseData', wintypes.DWORD),
            ('dwFlags', wintypes.DWORD),
            ('time', wintypes.DWORD),
            ('dwExtraInfo', ctypes.c_void_p),
        ]

    class _INPUT(ctypes.Structure):
        _fields_ = [
            ('type', wintypes.DWORD),
            ('mi', _MOUSEINPUT),
        ]

    user32 = ctypes.windll.user32

    # 0. 把目标坐标烘焙进组件隐藏偏移参数，并重新生成几何体
    try:
        _log(f"_auto_place: baking offset {pos} into component...")
        has_offset = False
        for axis, key in [('x', '偏移X'), ('y', '偏移Y'), ('z', '偏移Z')]:
            if key in comp:
                comp[key] = float(pos[{'x': 0, 'y': 1, 'z': 2}[axis]])
                has_offset = True
        if has_offset and hasattr(comp, 'replace'):
            comp.replace()
            _log("_auto_place: component replace() done with baked offset")
    except Exception as e:
        _log(f"_auto_place: bake offset failed: {e}")

    # 1. 标准化视图：俯视图 + 全图缩放，确保视图中心接近原点
    try:
        from pyp3d import set_view_direction_by_index, zoom_all_view
        _log("_auto_place: setting standard view (index=0) + zoom all...")
        set_view_direction_by_index(0)
        time.sleep(0.2)
        zoom_all_view()
        time.sleep(0.3)
        _log("_auto_place: view standardized")
    except Exception as e:
        _log(f"_auto_place: view standardization failed: {e}")

    # 2. 启动手动放置工具
    _log("_auto_place: starting place() tool...")
    if place is None:
        raise RuntimeError("place() 不可用")
    place(comp)
    time.sleep(0.6)

    # 3. 尝试在不点击的情况下直接创建几何体（某些版本可用）
    try:
        from pyp3d import create_geometry, entityid_isvaid, get_place_to_entityId
        _log("_auto_place: trying create_geometry() while place tool is active...")
        eid = create_geometry(comp)
        is_valid = entityid_isvaid(eid) if eid is not None else False
        _log(f"_auto_place: create_geometry() valid={is_valid}")
        if is_valid:
            try:
                from pyp3d import exit_tool, zoom_all_view
                exit_tool()
                time.sleep(0.3)
                zoom_all_view()
            except Exception as e:
                _log(f"_auto_place: cleanup failed: {e}")
            return
    except Exception as e:
        _log(f"_auto_place: create_geometry() failed: {e}")

    # 3. 找到 BIMBase 主窗口
    _windows = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                rect = _RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 300 and h > 300:
                    _windows.append((hwnd, title, w, h))
        return True

    user32.EnumWindows(_enum_cb, 0)
    for hwnd, title, w, h in _windows:
        _log(f"_auto_place: Win32 window '{title}' hwnd={hwnd} size={w}x{h}")

    bimbase_hwnd = None
    max_area = 0
    for hwnd, title, w, h in _windows:
        area = w * h
        if ('BIMBase' in title or 'P3D' in title or 'PKPM' in title) and area > max_area:
            max_area = area
            bimbase_hwnd = hwnd

    if bimbase_hwnd is None:
        # 兜底：选面积最大的可见窗口
        for hwnd, title, w, h in _windows:
            area = w * h
            if 'AI' not in title and '智能建模' not in title and area > max_area:
                max_area = area
                bimbase_hwnd = hwnd

    if bimbase_hwnd is None:
        raise RuntimeError("未找到 BIMBase 主窗口")

    _log(f"_auto_place: selected main hwnd={bimbase_hwnd}")

    # 4. 找到最大的可见子窗口（视图）
    _children = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_child_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            rect = _RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 200 and h > 200:
                _children.append((hwnd, w, h))
        return True

    user32.EnumChildWindows(bimbase_hwnd, _enum_child_cb, 0)
    _children.sort(key=lambda t: t[1] * t[2], reverse=True)
    for hwnd, w, h in _children[:5]:
        _log(f"_auto_place: child hwnd={hwnd} size={w}x{h}")

    if _children:
        viewport_hwnd = _children[0][0]
    else:
        viewport_hwnd = bimbase_hwnd

    # 5. 获取视图子窗口的屏幕坐标
    rect = _RECT()
    user32.GetWindowRect(viewport_hwnd, ctypes.byref(rect))
    cx = rect.left + (rect.right - rect.left) // 2
    cy = rect.top + (rect.bottom - rect.top) // 2
    _log(f"_auto_place: viewport hwnd={viewport_hwnd} click_screen=({cx},{cy})")

    # 6. 将 BIMBase 设为前台窗口
    user32.SetForegroundWindow(bimbase_hwnd)
    time.sleep(0.1)

    # 7. 用 SendInput 模拟真实鼠标点击（绝对坐标）
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    abs_x = int((cx * 65535) / screen_w)
    abs_y = int((cy * 65535) / screen_h)

    _log(f"_auto_place: SendInput click abs=({abs_x},{abs_y}) screen=({screen_w}x{screen_h})")

    inp = _INPUT()
    inp.type = 0  # INPUT_MOUSE

    inp.mi.dx = abs_x
    inp.mi.dy = abs_y
    inp.mi.dwFlags = 0x8000 | 0x0001 | 0x0002  # ABSOLUTE | MOVE | LEFTDOWN
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    time.sleep(0.05)

    inp.mi.dwFlags = 0x8000 | 0x0001 | 0x0004  # ABSOLUTE | MOVE | LEFTUP
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    time.sleep(0.5)

    # 8. 退出放置工具
    try:
        from pyp3d import exit_tool
        exit_tool()
        _log("_auto_place: exit_tool() called")
    except Exception as e:
        _log(f"_auto_place: exit_tool() failed: {e}")

    # 9. 验证 entityId
    try:
        from pyp3d import get_place_to_entityId, entityid_isvaid
        eid = get_place_to_entityId()
        is_valid = entityid_isvaid(eid) if eid is not None else False
        _log(f"_auto_place: entityId valid={is_valid}")
    except Exception as e:
        _log(f"_auto_place: entity validation failed: {e}")

    # 10. 刷新视图
    try:
        from pyp3d import zoom_all_view
        zoom_all_view()
        _log("_auto_place: zoom_all_view() called")
    except Exception as e:
        _log(f"_auto_place: zoom_all_view() failed: {e}")


def place_component_at(comp, x, y, z, _in_modal=False):
    """将组件自动布置到指定三维坐标（画板自主处理，不再调用 AI_Modeling）"""
    if not _pyp3d_ok:
        return False, "pyp3d 未加载"
    if comp is None:
        return False, "组件为 None"

    pos = (float(x), float(y), float(z))
    _log(f"place_component_at: type={type(comp).__name__} pos={pos}")

    try:
        from pyp3d import translate as _translate, zoom_all_view
    except Exception as e:
        _log(f"place_component_at: failed to import translate/zoom_all_view: {e}")
        return False, f"pyp3d API 导入失败: {e}"

    def _refresh_view():
        try:
            zoom_all_view()
            _log("place_component_at: zoom_all_view() called")
        except Exception as e:
            _log(f"place_component_at: zoom_all_view() failed: {e}")

    def _core_recover():
        """放置过程中若 API 调用损坏 _Core，尝试恢复"""
        try:
            _ensure_pyp3d_port()
        except Exception as e:
            _log(f"place_component_at: core recover failed: {e}")

    # 初始化 place 需要的依赖
    _ensure_place_to_direct()
    original_argv = _set_argv_for_place()
    try:
        # 方案1：底层 _PlaceToDirect（create_component + place_instance_to）
        if _PlaceToDirect is not None:
            _core_recover()
            try:
                _log(f"place_component_at: trying _PlaceToDirect({pos})")
                before = _count_entities()
                _PlaceToDirect(comp, _translate(*pos))
                # 给 BIMBase 一点刷新时间再统计实体数量
                import time
                time.sleep(0.3)
                after = _count_entities()
                _log(f"place_component_at: _PlaceToDirect SUCCESS, entity count before={before}, after={after}")
                if after <= before and before >= 0:
                    _log("place_component_at: entity count did not increase, treating as failure")
                    raise RuntimeError(f"实体数量未增加（before={before}, after={after}）")
                _refresh_view()
                return True, f"已自动布置到 {pos}"
            except Exception as e:
                _log(f"place_component_at: _PlaceToDirect failed: {e}")

        # 方案2：原生 place_to
        _core_recover()
        try:
            from pyp3d import place_to as _place_to
            _log(f"place_component_at: trying place_to({pos})")
            _place_to(comp, _translate(*pos))
            _log("place_component_at: place_to SUCCESS")
            _refresh_view()
            return True, f"已自动布置到 {pos}"
        except Exception as e:
            _log(f"place_component_at: place_to failed: {e}")

        # 方案3：create_geometry 直接创建（不依赖 place 工具上下文）
        _core_recover()
        try:
            _log(f"place_component_at: trying create_geometry at {pos}")
            if hasattr(comp, 'replace'):
                try:
                    comp.replace()
                    _log("place_component_at: comp.replace() done")
                except Exception as e:
                    _log(f"place_component_at: comp.replace() warning: {e}")
            placed_geom = _translate(*pos) * comp
            eid = create_geometry(placed_geom)
            eid_detail = "None"
            is_valid = False
            if eid is not None:
                try:
                    eid_detail = f"ModelId={getattr(eid, '_ModelId', '?')}, ElementId={getattr(eid, '_ElementId', '?')}"
                    is_valid = entityid_isvaid(eid)
                except Exception as ve:
                    eid_detail = f"<{type(eid).__name__}>(inspect error: {ve})"
            _log(f"place_component_at: create_geometry returned eid={eid_detail}, valid={is_valid}")
            if is_valid:
                _refresh_view()
                return True, f"已自动布置到 {pos}"
        except Exception as e:
            _log(f"place_component_at: create_geometry failed: {e}")

        # 方案4：坐标烘焙 + place() + create_geometry/SendInput
        _core_recover()
        try:
            _log(f"place_component_at: trying offset bake + auto click placement {pos}")
            _auto_place_click_and_move(comp, *pos)
            _log("place_component_at: offset bake + auto click placement SUCCESS")
            _refresh_view()
            return True, f"已自动布置到 {pos}"
        except Exception as e:
            _log(f"place_component_at: offset bake + auto click placement failed: {e}")

        # 方案5：回退到手动放置
        _core_recover()
        try:
            from pyp3d import place as _place
            _log("place_component_at: falling back to place()")
            _place(comp)
            return True, "已启动手动放置工具"
        except Exception as e:
            _log(f"place_component_at: place() fallback failed: {e}")

        _log("place_component_at: all placement methods failed")
        return False, "自动布置失败"
    except Exception as e:
        _log(f"place_component_at: exception: {e}")
        traceback.print_exc()
        return False, f"放置失败: {e}"
    finally:
        _restore_argv(original_argv)


# ============================================================
# AI_Modeling 桥接：实体类型复用其已成功验证的 component_factory
# ============================================================
_SOLID_AI_TYPE_MAP = {
    '圆柱': 'cylinder',
    '长方体': 'box',
    '正方体': 'cube',
    '球体': 'sphere',
    '圆锥': 'cone',
    '直角三棱柱': 'triangular_prism',
}

_SOLID_AI_PARAM_MAP = {
    '圆柱': {'半径': 'radius', '高度': 'height'},
    '长方体': {'长度': 'length', '宽度': 'width', '高度': 'height'},
    '正方体': {'边长': 'size'},
    '球体': {'半径': 'radius'},
    '圆锥': {'底面半径': 'radius', '高度': 'height'},
    '直角三棱柱': {'直角边1': '直角边1', '直角边2': '直角边2', '高度': '高度'},
}


def _place_via_ai_modeling(comp_type, params, x, y, z):
    """
    通过 AI_Modeling 窗口执行实体组件放置。
    经验：只有在 AI_Modeling 窗口真正显示并进入其事件循环后，
    pyp3d 的 place_to / _PlaceToDirect 才能正常工作。
    因此这里把命令构造为 AI_Modeling 可识别的 parsed 结构，
    由 ai_modeling_launcher 打开/复用 AI_Modeling 窗口执行。
    """
    ai_type = _SOLID_AI_TYPE_MAP.get(comp_type)
    if not ai_type:
        return False, f"{comp_type} 暂无 AI_Modeling 桥接"
    try:
        param_map = _SOLID_AI_PARAM_MAP.get(comp_type, {})
        ai_params = {}
        for cn_key, en_key in param_map.items():
            if cn_key in params:
                ai_params[en_key] = params[cn_key]

        parsed = {
            'action': 'create',
            'component_type': ai_type,
            'params': ai_params,
            'position': {'mode': 'absolute', 'x': float(x), 'y': float(y), 'z': float(z)},
            'array': None,
            'route': None,
        }
        original_text = f"在({x},{y},{z})生成{comp_type}"

        _log(f"_place_via_ai_modeling: delegating to AI_Modeling window: {parsed}")

        # 导入 launcher 中的代理执行函数
        try:
            from ai_modeling_launcher import execute_parsed_command
        except ImportError:
            # 如果 sys.path 中 CADBoard 目录不在，手动加载
            launcher_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_modeling_launcher.py')
            spec = importlib.util.spec_from_file_location("ai_modeling_launcher", launcher_path)
            launcher_mod = importlib.util.module_from_spec(spec)
            sys.modules['ai_modeling_launcher'] = launcher_mod
            spec.loader.exec_module(launcher_mod)
            execute_parsed_command = launcher_mod.execute_parsed_command

        ok, msg = execute_parsed_command(parsed, original_text)
        _log(f"_place_via_ai_modeling: ok={ok}, msg={msg}")
        return ok, msg
    except Exception as e:
        _log(f"_place_via_ai_modeling error: {e}")
        traceback.print_exc()
        return False, f"AI_Modeling 桥接失败: {e}"


def place_element_to_bimbase(elem):
    """根据画板元素创建组件并直接布置到其三维坐标（画板自主处理）"""
    try:
        sync = BIMBaseSync(None)
        comp, params, comp_type = sync._make_component(elem)
        if comp is None:
            return False, "无法创建组件"
        x = getattr(elem, 'x', getattr(elem, 'cx', getattr(elem, 'x1', 0)))
        y = getattr(elem, 'y', getattr(elem, 'cy', getattr(elem, 'y1', 0)))
        z = getattr(elem, 'z_start', 0)
        ok, msg = place_component_at(comp, x, y, z)
        return ok, msg
    except Exception as e:
        _log(f"place_element_to_bimbase error: {e}")
        traceback.print_exc()
        return False, f"直接布置失败: {e}"


def _get_point_xy(p):
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return float(p[0]), float(p[1])
    elif hasattr(p, 'x') and hasattr(p, 'y'):
        return float(p.x), float(p.y)
    elif isinstance(p, dict):
        return float(p.get('x', 0)), float(p.get('y', 0))
    return 0.0, 0.0


def _get_elem_points_2d(elem):
    points = []
    if hasattr(elem, 'points') and elem.points:
        for i, p in enumerate(elem.points):
            px, py = _get_point_xy(p)
            points.append([px, py])
    return points


def _circle_section(radius, segments=32):
    points = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        points.append(Vec2(radius * math.cos(angle), radius * math.sin(angle)))
    return Section(*points)


class Line3DComponent(Component):
    def __init__(self, x1=0, y1=0, z1=0, x2=100, y2=100, z2=0, radius=5):
        super().__init__()
        self['x1'] = Attr(float(x1), show=True, obvious=True)
        self['y1'] = Attr(float(y1), show=True, obvious=True)
        self['z1'] = Attr(float(z1), show=True, obvious=True)
        self['x2'] = Attr(float(x2), show=True, obvious=True)
        self['y2'] = Attr(float(y2), show=True, obvious=True)
        self['z2'] = Attr(float(z2), show=True, obvious=True)
        self['radius'] = Attr(float(radius), show=True, obvious=True)
        self['线段'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        x1, y1, z1 = self['x1'], self['y1'], self['z1']
        x2, y2, z2 = self['x2'], self['y2'], self['z2']
        r = max(self['radius'], 1)
        length = math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
        if length < 0.001:
            self['线段'] = translate(x1, y1, z1) * scale(r*2, r*2, r*2) * Cube()
        else:
            section = _circle_section(r)
            path = Line(Vec3(x1, y1, z1), Vec3(x2, y2, z2))
            self['线段'] = Sweep(section, path)


class SweepBoxComponent(Component):
    def __init__(self, x=0, y=0, z_bottom=0, z_top=100, length=100, width=100, chamfer=0):
        super().__init__()
        self['x'] = Attr(float(x), show=True, obvious=True)
        self['y'] = Attr(float(y), show=True, obvious=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True, obvious=True)
        self['z_top'] = Attr(float(z_top), show=True, obvious=True)
        self['length'] = Attr(float(length), show=True, obvious=True)
        self['width'] = Attr(float(width), show=True, obvious=True)
        self['chamfer'] = Attr(float(chamfer), show=True, obvious=True)
        self['拉伸体'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        x, y = self['x'], self['y']
        zb, zt = self['z_bottom'], self['z_top']
        L, W = self['length'], self['width']
        C = self['chamfer']
        if L <= 0: L = 100
        if W <= 0: W = 100
        if C > 0 and C < min(L, W) / 2:
            section = Section(
                Vec2(x+C, y), Vec2(x+L-C, y),
                Vec2(x+L, y+C), Vec2(x+L, y+W-C),
                Vec2(x+L-C, y+W), Vec2(x+C, y+W),
                Vec2(x, y+W-C), Vec2(x, y+C)
            )
        else:
            section = Section(Vec2(x, y), Vec2(x+L, y), Vec2(x+L, y+W), Vec2(x, y+W))
        path = Line(Vec3(0, 0, zb), Vec3(0, 0, zt))
        self['拉伸体'] = Sweep(section, path)


class Circle3DComponent(Component):
    def __init__(self, cx=0, cy=0, z_bottom=0, z_top=100, radius=50):
        super().__init__()
        self['cx'] = Attr(float(cx), show=True, obvious=True)
        self['cy'] = Attr(float(cy), show=True, obvious=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True, obvious=True)
        self['z_top'] = Attr(float(z_top), show=True, obvious=True)
        self['radius'] = Attr(float(radius), show=True, obvious=True)
        self['圆柱'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        cx, cy = self['cx'], self['cy']
        zb, zt = self['z_bottom'], self['z_top']
        r = max(self['radius'], 1)
        section = _circle_section(r)
        path = Line(Vec3(cx, cy, zb), Vec3(cx, cy, zt))
        self['圆柱'] = Sweep(section, path)


class Arc3DComponent(Component):
    def __init__(self, cx=0, cy=0, radius=50, start_angle=0, end_angle=90,
                 z_bottom=0, z_top=100, thickness=5):
        super().__init__()
        self['cx'] = Attr(float(cx), show=True, obvious=True)
        self['cy'] = Attr(float(cy), show=True, obvious=True)
        self['radius'] = Attr(float(radius), show=True, obvious=True)
        self['start_angle'] = Attr(float(start_angle), show=True, obvious=True)
        self['end_angle'] = Attr(float(end_angle), show=True, obvious=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True, obvious=True)
        self['z_top'] = Attr(float(z_top), show=True, obvious=True)
        self['thickness'] = Attr(float(thickness), show=True, obvious=True)
        self['圆弧'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        cx, cy = self['cx'], self['cy']
        r = max(self['radius'], 1)
        sa = math.radians(self['start_angle'])
        ea = math.radians(self['end_angle'])
        if ea < sa: ea += 2 * math.pi
        zb = self['z_bottom']
        zt = self['z_top']
        t = max(self['thickness'], 2)
        try:
            mid = (sa + ea) / 2
            p1 = Vec3(cx + r*math.cos(sa), cy + r*math.sin(sa), zb)
            p2 = Vec3(cx + r*math.cos(mid), cy + r*math.sin(mid), zb)
            p3 = Vec3(cx + r*math.cos(ea), cy + r*math.sin(ea), zb)
            arc_geom = Arc(p1, p2, p3)
            section = _circle_section(t / 2)
            self['圆弧'] = Sweep(section, arc_geom)
        except Exception:
            section = _circle_section(t / 2)
            path = Line(Vec3(cx, cy, zb), Vec3(cx, cy, zt))
            self['圆弧'] = Sweep(section, path)


class Ellipse3DComponent(Component):
    def __init__(self, cx=0, cy=0, rx=50, ry=30, z_bottom=0, z_top=100):
        super().__init__()
        self['cx'] = Attr(float(cx), show=True, obvious=True)
        self['cy'] = Attr(float(cy), show=True, obvious=True)
        self['rx'] = Attr(float(rx), show=True, obvious=True)
        self['ry'] = Attr(float(ry), show=True, obvious=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True, obvious=True)
        self['z_top'] = Attr(float(z_top), show=True, obvious=True)
        self['椭圆柱'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        cx, cy = self['cx'], self['cy']
        rx = max(self['rx'], 1)
        ry = max(self['ry'], 1)
        zb = self['z_bottom']
        zt = self['z_top']
        try:
            section = _circle_section(1)
            scaled = scale(rx, ry) * section
            path = Line(Vec3(cx, cy, zb), Vec3(cx, cy, zt))
            self['椭圆柱'] = Sweep(scaled, path)
        except Exception:
            path = Line(Vec3(cx, cy, zb), Vec3(cx, cy, zt))
            self['椭圆柱'] = Sweep(_circle_section(max(rx, ry)), path)


class Point3DComponent(Component):
    def __init__(self, x=0, y=0, z=0, radius=5):
        super().__init__()
        self['x'] = Attr(float(x), show=True, obvious=True)
        self['y'] = Attr(float(y), show=True, obvious=True)
        self['z'] = Attr(float(z), show=True, obvious=True)
        self['radius'] = Attr(float(radius), show=True, obvious=True)
        self['点'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        x, y, z = self['x'], self['y'], self['z']
        r = max(self['radius'], 1)
        self['点'] = translate(x, y, z) * scale(r*2, r*2, r*2) * Cube()


class Polygon3DComponent(Component):
    def __init__(self, points_2d=None, z_bottom=0, z_top=100):
        super().__init__()
        if points_2d is None:
            points_2d = [[0, 0], [100, 0], [100, 100]]
        self['z_bottom'] = Attr(float(z_bottom), show=True, obvious=True)
        self['z_top'] = Attr(float(z_top), show=True, obvious=True)
        self['point_count'] = Attr(len(points_2d), show=True, obvious=True)
        for i, (px, py) in enumerate(points_2d):
            self[f'px{i}'] = Attr(float(px), show=True, obvious=True)
            self[f'py{i}'] = Attr(float(py), show=True, obvious=True)
        self['多边形'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            zb = self['z_bottom']
            zt = self['z_top']
            count = self['point_count']
            vecs = []
            for i in range(count):
                px = self.get(f'px{i}', 0)
                py = self.get(f'py{i}', 0)
                vecs.append(Vec2(float(px), float(py)))
            if len(vecs) < 3:
                self['多边形'] = Cube()
                return
            section = Section(*vecs)
            path = Line(Vec3(0, 0, zb), Vec3(0, 0, zt))
            self['多边形'] = Sweep(section, path)
        except Exception as e:
            _log(f"  Polygon3DComponent.replace() error: {e}")
            self['多边形'] = Cube()

    def get(self, key, default=0):
        try:
            return self[key]
        except Exception:
            return default


class TriangularPrismComponent(Component):
    """直角三棱柱：底面为直角三角形，沿高度方向拉伸
    与 组件测试/model.py 保持一致的参数：直角边1, 直角边2, 高度（3个可变参数）"""
    def __init__(self, 直角边1=100, 直角边2=100, 高度=200):
        super().__init__()
        self['直角边1'] = Attr(float(直角边1), show=True, obvious=True)
        self['直角边2'] = Attr(float(直角边2), show=True, obvious=True)
        self['高度'] = Attr(float(高度), show=True, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['直角三棱柱'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            a = self['直角边1']
            b = self['直角边2']
            h = self['高度']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            section = Section(Vec2(0, 0), Vec2(a, 0), Vec2(0, b))
            path = Line(Vec3(0, 0, 0), Vec3(0, 0, h))
            self['直角三棱柱'] = translate(ox, oy, oz) * Sweep(section, path)
        except Exception as e:
            _log(f"  TriangularPrismComponent.replace() error: {e}")
            self['直角三棱柱'] = Cube()


class CylinderComponent(Component):
    """圆柱：底面为圆形，沿高度方向拉伸
    与 组件测试/圆柱.py 保持一致的参数：半径, 高度"""
    def __init__(self, 半径=50, 高度=100):
        super().__init__()
        self['半径'] = Attr(float(半径), show=True, obvious=True)
        self['高度'] = Attr(float(高度), show=True, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['圆柱'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            r = self['半径']
            h = self['高度']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            points = []
            for i in range(32):
                angle = 2 * math.pi * i / 32
                points.append(Vec2(r * math.cos(angle), r * math.sin(angle)))
            section = Section(*points)
            path = Line(Vec3(0, 0, 0), Vec3(0, 0, h))
            self['圆柱'] = translate(ox, oy, oz) * Sweep(section, path)
        except Exception as e:
            _log(f"  CylinderComponent.replace() error: {e}")
            self['圆柱'] = Cube()


class CubeComponent(Component):
    """正方体：长宽高相等的立方体
    与 组件测试/正方体.py 保持一致的参数：边长"""
    def __init__(self, 边长=100):
        super().__init__()
        self['边长'] = Attr(float(边长), show=True, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['正方体'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            a = self['边长']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            self['正方体'] = translate(ox, oy, oz) * scale(a, a, a) * Cube()
        except Exception as e:
            _log(f"  CubeComponent.replace() error: {e}")
            self['正方体'] = scale(100, 100, 100) * Cube()


class BoxComponent(Component):
    """长方体：长宽高三维尺寸可调的立方体
    与 组件测试/长方体.py 保持一致的参数：长度, 宽度, 高度"""
    def __init__(self, 长度=200, 宽度=100, 高度=150):
        super().__init__()
        self['长度'] = Attr(float(长度), show=True, obvious=True)
        self['宽度'] = Attr(float(宽度), show=True, obvious=True)
        self['高度'] = Attr(float(高度), show=True, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['长方体'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            L = self['长度']
            W = self['宽度']
            H = self['高度']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            self['长方体'] = translate(ox, oy, oz) * scale(L, W, H) * Cube()
        except Exception as e:
            _log(f"  BoxComponent.replace() error: {e}")
            self['长方体'] = scale(200, 100, 150) * Cube()


class SphereComponent(Component):
    """球体：由半径定义，几何中心在原点（通过 place 平移到目标位置）"""
    def __init__(self, 半径=50):
        super().__init__()
        self['半径'] = Attr(float(半径), show=True, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['球体'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            r = self['半径']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            self['球体'] = translate(ox, oy, oz) * scale(r, r, r) * Sphere()
        except Exception as e:
            _log(f"  SphereComponent.replace() error: {e}")
            self['球体'] = scale(50, 50, 50) * Sphere()


class Polyline3DComponent(Component):
    def __init__(self, points_3d=None, thickness=5):
        super().__init__()
        if points_3d is None:
            points_3d = [[0, 0, 0], [100, 0, 0]]
        self['point_count'] = Attr(len(points_3d), show=True, obvious=True)
        for i, (px, py, pz) in enumerate(points_3d):
            self[f'px{i}'] = Attr(float(px), show=True, obvious=True)
            self[f'py{i}'] = Attr(float(py), show=True, obvious=True)
            self[f'pz{i}'] = Attr(float(pz), show=True, obvious=True)
        self['thickness'] = Attr(float(thickness), show=True, obvious=True)
        self['多段线'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            count = self['point_count']
            t = max(self['thickness'], 2)
            if count < 2:
                self['多段线'] = Cube()
                return
            points = []
            for i in range(count):
                px = self.get(f'px{i}', 0)
                py = self.get(f'py{i}', 0)
                pz = self.get(f'pz{i}', 0)
                points.append(Vec3(float(px), float(py), float(pz)))
            section = _circle_section(t / 2)
            result = None
            for i in range(len(points) - 1):
                path = Line(points[i], points[i + 1])
                swept = Sweep(section, path)
                if result is None:
                    result = swept
                else:
                    result = result + swept
            self['多段线'] = result if result else Cube()
        except Exception as e:
            _log(f"  Polyline3DComponent.replace() error: {e}")
            self['多段线'] = Cube()

    def get(self, key, default=0):
        try:
            return self[key]
        except Exception:
            return default



class BIMBaseSync:
    def __init__(self, board):
        self.board = board
        self.registry = ComponentRegistry()
        self.replaced_bimbase_origins = []  # 记录来源于BIMBase、重新放置了新组件的元素（旧组件仍在BIMBase中）
        _log("BIMBaseSync initialized")

    def _get_params_from_datakey(self, datakey):
        """从 P3DInstanceKey 获取参数。使用 get_noumKV_from_instancekey。
        注意：不要对 datakey 调用 str() / repr() / bool()，会触发 P3DInstanceKey.__str__ 的
        _data AttributeError bug，进而破坏 SDK 内部状态导致后续 get_noumKV 全部失败。"""
        if datakey is None:
            return None
        try:
            params = get_noumKV_from_instancekey(datakey)
            _log(f"    get_noumKV: type={type(params).__name__ if params is not None else 'None'} "
                 f"len={len(params) if params is not None else 0} "
                 f"keys={list(params.keys())[:12] if params is not None else 'None'}")
            # 如果直接获取参数为空，尝试获取 noumenon（本体）并遍历其键值对
            if (params is None or (isinstance(params, dict) and len(params) == 0)) and get_noumenon_from_instancekey is not None:
                try:
                    noumenon = get_noumenon_from_instancekey(datakey)
                    _log(f"    trying noumenon: type={type(noumenon).__name__ if noumenon is not None else 'None'}")
                    if noumenon is not None:
                        # 参数化组件的 Noumenon 通常把参数放在 ParaCmptProperty 中
                        params = {}
                        try:
                            prop = noumenon.at('ParaCmptProperty')
                            _log(f"    noumenon.at('ParaCmptProperty') type={type(prop).__name__ if prop is not None else 'None'}")
                            if prop is not None and hasattr(prop, 'keys'):
                                for key in prop:
                                    params[key] = prop[key]
                                _log(f"    ParaCmptProperty copied: len={len(params)} keys={list(params.keys())[:12]}")
                            elif prop is not None and isinstance(prop, dict):
                                params = dict(prop)
                                _log(f"    ParaCmptProperty dict: len={len(params)} keys={list(params.keys())[:12]}")
                            else:
                                _log(f"    ParaCmptProperty has no keys, fallback to iterate noumenon")
                                for key in noumenon:
                                    params[key] = noumenon[key]
                                _log(f"    noumenon copied: len={len(params)} keys={list(params.keys())[:12]}")
                        except Exception as e2:
                            _log(f"    noumenon at/iterate error: {e2}")
                except Exception as e:
                    _log(f"    get_noumenon failed: {e}")
            if params is not None and isinstance(params, dict) and len(params) > 0:
                # 只有包含 CADBoard 组件特有字段时才认为是我们的组件
                keys = set(params.keys())
                cadboard_keys = {'z_bottom', 'z_top', 'length', 'width', 'radius',
                                 'cx', 'cy', 'x', 'y', 'x1', 'y1', 'px0', 'py0',
                                 'point_count', 'start_angle', 'end_angle', 'rx', 'ry',
                                 'a', 'b', 'h',
                                 '直角边1', '直角边2', '高度',
                                 '半径', '边长', '长度', '宽度'}
                matched_keys = keys & cadboard_keys
                _log(f"    matched cadboard_keys={len(matched_keys)}: {list(matched_keys)[:6]}")
                if matched_keys:
                    params['_type'] = self._infer_component_type(params)
                    _log(f"    inferred _type='{params['_type']}'")
                    # 保存原始 datakey，以便后续直接修改已有实例
                    params['_datakey'] = datakey
                    # 只保留 CADBoard 关心的字段 + 内部标记，丢弃 BIMBase 内部属性（UserLabel/Guid 等）
                    keep_keys = cadboard_keys | {'_type', '_datakey'}
                    def _is_clean(v):
                        return isinstance(v, (int, float, str, bool, type(None), list, tuple, dict))
                    params = {k: v for k, v in params.items() if k in keep_keys and _is_clean(v)}
                    return params
                else:
                    _log(f"    no cadboard_keys matched, skip")
        except Exception as e:
            _log(f"    get_noumKV failed: {e}")
        return None

    def _infer_component_type(self, params):
        """根据参数字典的键推断组件类型"""
        keys = set(params.keys())
        if 'px0' in keys and 'py0' in keys:
            if 'pz0' in keys:
                return 'Polyline3DComponent'
            return 'Polygon3DComponent'
        if 'length' in keys and 'width' in keys:
            return 'SweepBoxComponent'
        if 'radius' in keys and 'cx' in keys:
            return 'Circle3DComponent'
        if 'x1' in keys and 'y1' in keys:
            return 'Line3DComponent'
        if 'x' in keys and 'y' in keys and 'radius' in keys:
            return 'Point3DComponent'
        if 'start_angle' in keys and 'end_angle' in keys:
            return 'Arc3DComponent'
        if 'rx' in keys and 'ry' in keys:
            return 'Ellipse3DComponent'
        if '直角边1' in keys and '直角边2' in keys and '高度' in keys:
            return '直角三棱柱'
        if '半径' in keys and '高度' not in keys and '边长' not in keys:
            return '球体'
        if '半径' in keys and '高度' in keys and '边长' not in keys:
            return '圆柱'
        if '边长' in keys and '长度' not in keys:
            return '正方体'
        if '长度' in keys and '宽度' in keys and '高度' in keys:
            return '长方体'
        return ''

    def _place_component(self, comp):
        try:
            if _pyp3d_ok:
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                import bimbase_sync as _bimbase_sync_ref

                # 临时修改 sys.argv[0] 为 bimbase_sync.py 的路径。
                # place() 内部使用 sys.argv[0] 读取 DependentFile，且 _push_to()
                # 使用 sys.argv[0] 生成 representation。修改为 bimbase_sync.py
                # 可确保 BIMBase 在解析组件时能正确定位到定义组件类的模块。
                original_argv0 = sys.argv[0]
                bimbase_sync_path = os.path.join(plugin_dir, 'bimbase_sync.py')
                sys.argv[0] = bimbase_sync_path
                _log(f"  _place_component: sys.argv[0] -> {sys.argv[0]}")
                try:
                    _log(f"  _place_component: calling place() for {type(comp).__name__}")
                    # 使用 place() 启动手动放置工具，组件会被正确注册为可选中实体
                    place(comp)
                    _log("  place() success (manual place tool activated)")
                    return True
                finally:
                    sys.argv[0] = original_argv0
                    _log(f"  _place_component: sys.argv[0] restored -> {original_argv0}")
            else:
                _log("  place() not available (pyp3d missing)")
                return False
        except Exception as e:
            _log(f"  place() error: {e}")
            traceback.print_exc()
            return False

    def sync_all(self, elements=None):
        self.replaced_bimbase_origins = []
        if elements is None:
            elements = getattr(self.board, 'elements', [])
        # 过滤掉面元素，避免每个面被同步为独立组件
        raw_count = len(elements)
        elements = [e for e in elements if not self._is_face_element(e)]
        _log(f"sync_all() with {len(elements)} elements (faces filtered: {raw_count - len(elements)})")
        if not _pyp3d_ok:
            _log("  pyp3d not available, skipping sync")
            return False
        success_count = 0
        error_count = 0
        for elem in elements:
            try:
                is_bimbase_origin = getattr(elem, '_bimbase_datakey', None) is not None
                result = self._sync_element(elem)
                if result is True:
                    success_count += 1
                    if is_bimbase_origin:
                        self.replaced_bimbase_origins.append(elem)
                else:
                    error_count += 1
            except Exception as e:
                _log(f"  sync element error: {e}")
                error_count += 1
        self._sync_stats = (success_count, error_count)
        _log(f"sync_all() done: {success_count} success, {error_count} errors, {len(self.replaced_bimbase_origins)} re-placed (BIMBase origin)")
        return error_count == 0

    def _sync_element(self, elem):
        try:
            # 先检查该元素是否已有已放置的BIMBase实例（画板独立创建并 place 过的）
            info = self.registry.get(elem.id)
            if info and info.get('instance'):
                inst = info['instance']
                comp_type = info.get('component_type', '')
                _log(f"  found existing instance for {elem.id}, type={comp_type}")
                # 重新构建当前参数
                _, new_params, _ = self._make_component(elem)
                if new_params:
                    # 写入新参数到已有实例
                    for k, v in new_params.items():
                        if k in inst:
                            try:
                                inst[k] = v
                            except Exception:
                                pass
                    # 原地更新几何（不重新place）
                    try:
                        inst.replace()
                        _log("  inst.replace() success (in-place update)")
                        self.registry.update_params(elem.id, new_params)
                        # 更新元素状态
                        elem.component_params = dict(new_params)
                        if comp_type == '直角三棱柱':
                            if '高度' in new_params:
                                elem.z_end = elem.z_start + float(new_params['高度'])
                        elif comp_type == '圆柱':
                            if '高度' in new_params:
                                elem.z_end = elem.z_start + float(new_params['高度'])
                        elif comp_type == '正方体':
                            if '边长' in new_params:
                                elem.z_end = elem.z_start + float(new_params['边长'])
                        elif comp_type == '长方体':
                            if '高度' in new_params:
                                elem.z_end = elem.z_start + float(new_params['高度'])
                        elif comp_type == '球体':
                            if '半径' in new_params:
                                elem.z_end = elem.z_start + 2 * float(new_params['半径'])
                        else:
                            z_bottom = new_params.get('z_bottom') or new_params.get('z1') or new_params.get('z', 0)
                            z_top = new_params.get('z_top') or new_params.get('z2') or new_params.get('z', 0)
                            if z_bottom is not None:
                                elem.z_start = float(z_bottom)
                            if z_top is not None:
                                elem.z_end = float(z_top)
                        elem.is_3d = True
                        return True
                    except Exception as e:
                        _log(f"  inst.replace() failed: {e}, fallback to re-place")
                        # replace失败则回退到重新放置

            # 方式2：元素来源于BIMBase（从BIMBase同步回画板的）
            # BIMBase SDK不提供直接修改已有组件实例的API，因此重新 place() 一个新组件。
            # 旧组件会保留在BIMBase中，需要用户手动删除。
            dk = getattr(elem, '_bimbase_datakey', None)
            if dk is not None:
                _log(f"  element {elem.id} originates from BIMBase (_bimbase_datakey present). Will re-place as new component (old one remains in BIMBase).")
                # 继续执行下面的 place() 逻辑，而不是跳过

            # PDF 识别来源的元素：首次同步时弹出坐标对话框让用户输入放置位置
            if getattr(elem, 'pdf_recognized', False) and not (info and info.get('instance')):
                _log(f"  PDF recognized element {elem.id}, requesting placement coordinate...")
                try:
                    defaults = (
                        float(getattr(elem, 'pdf_anchor_x', 0.0)),
                        float(getattr(elem, 'pdf_anchor_y', 0.0)),
                        float(getattr(elem, 'pdf_anchor_z', 0.0)),
                    )
                    coord = _request_placement_coordinate(self.board, defaults=defaults)
                except Exception as e:
                    _log(f"  coordinate dialog failed: {e}")
                    return False
                if coord is None:
                    _log("  user cancelled coordinate input")
                    return False
                px, py, pz = coord
                # 保存用户输入的放置坐标到 PDF 锚点属性（兼容无 x/y/cx/cy 的元素，
                # 例如由 PolylineElement 表示的直角三棱柱）
                elem.pdf_anchor_x = float(px)
                elem.pdf_anchor_y = float(py)
                elem.pdf_anchor_z = float(pz)
                # 同时更新已有的几何属性（如果存在）
                if hasattr(elem, 'x'):
                    elem.x = px
                if hasattr(elem, 'y'):
                    elem.y = py
                if hasattr(elem, 'cx'):
                    elem.cx = px
                if hasattr(elem, 'cy'):
                    elem.cy = py
                elem.z_start = pz
                elem.pdf_recognized = False
                _log(f"  user selected placement coordinate: ({px}, {py}, {pz})")

            # 首次同步：创建新组件并 place
            comp, params, comp_type = self._make_component(elem)
            if comp is None:
                return False
            # 所有组件统一使用 create_geometry 优先的 place_component_at 自动放置
            SOLID_TYPES = {'圆柱', '正方体', '长方体', '球体', '直角三棱柱', '圆锥'}
            if comp_type in SOLID_TYPES:
                # 优先使用用户通过弹窗输入的 PDF 放置锚点，防止 PolylineElement 等
                # 没有 x/y/cx/cy 属性的元素丢失 X/Y 坐标
                x = float(getattr(elem, 'pdf_anchor_x',
                                  getattr(elem, 'x', getattr(elem, 'cx', 0))))
                y = float(getattr(elem, 'pdf_anchor_y',
                                  getattr(elem, 'y', getattr(elem, 'cy', 0))))
                z = float(getattr(elem, 'pdf_anchor_z', getattr(elem, 'z_start', 0)))
            else:
                # 非实体组件（线、矩形、多边形等）：坐标已 baked 进组件参数，用 identity 自动放置
                x, y, z = 0, 0, 0
            ok, pmsg = place_component_at(comp, x, y, z)
            _log(f"  auto place result: ok={ok}, msg={pmsg}")
            if not ok:
                return False
            self.registry.register(elem.id, comp, params, comp_type)
            elem.bimbase_component_id = id(comp)
            elem.component_type = comp_type
            elem.component_params = params.copy()
            # 将组件参数中的高度信息写回元素，使3D预览能正确显示
            if comp_type == '直角三棱柱':
                if '高度' in params:
                    elem.z_end = elem.z_start + float(params['高度'])
            elif comp_type == '圆柱':
                if '高度' in params:
                    elem.z_end = elem.z_start + float(params['高度'])
            elif comp_type == '正方体':
                if '边长' in params:
                    elem.z_end = elem.z_start + float(params['边长'])
            elif comp_type == '长方体':
                if '高度' in params:
                    elem.z_end = elem.z_start + float(params['高度'])
            elif comp_type == '球体':
                if '半径' in params:
                    elem.z_end = elem.z_start + 2 * float(params['半径'])
            else:
                z_bottom = params.get('z_bottom') or params.get('z1') or params.get('z', 0)
                z_top = params.get('z_top') or params.get('z2') or params.get('z', 0)
                if z_bottom is not None:
                    elem.z_start = float(z_bottom)
                if z_top is not None:
                    elem.z_end = float(z_top)
            elem.is_3d = True
            return True
        except Exception as e:
            _log(f"  _sync_element error: {e}")
            traceback.print_exc()
            return False

    def _make_component(self, elem):
        # 优先使用元素已记录的 component_type，保证与原始BIMBase组件类型一致
        comp_type = getattr(elem, 'component_type', '')
        if comp_type:
            _log(f"  _make_component using existing component_type={comp_type} id={elem.id}")
            return self._make_component_by_type(elem, comp_type)

        et = getattr(elem, 'element_type', '')
        # 兼容 ElementType 枚举和字符串
        if hasattr(et, 'name'):
            elem_type = et.name.lower()
        else:
            elem_type = str(et).lower()
        _log(f"  making component for {elem_type} id={elem.id}")
        return self._make_component_by_type(elem, None, elem_type)

    def _make_component_by_type(self, elem, comp_type=None, elem_type=None):
        """根据 comp_type 或 elem_type 创建对应组件"""
        x = getattr(elem, 'x', 0)
        y = getattr(elem, 'y', 0)
        z = getattr(elem, 'z', 0)
        z_start = getattr(elem, 'z_start', 0)
        z_end = getattr(elem, 'z_end', 0)
        # 防止默认z_end=0导致拉伸体高度为0而不可见
        if z_end <= z_start:
            user_height = getattr(elem, 'thickness', 0)
            if user_height <= 0 and getattr(elem, 'element_type', '') != 'rectangle':
                user_height = getattr(elem, 'height', 0)
            if user_height > 0:
                z_end = z_start + user_height
            else:
                z_end = z_start + 100
        thickness = getattr(elem, 'thickness', 5)
        width = getattr(elem, 'width', 100)
        height = getattr(elem, 'height', 100)
        radius = getattr(elem, 'radius', 50)

        # 如果 comp_type 明确指定了 直角三棱柱，直接创建
        if comp_type == '直角三棱柱':
            cp = getattr(elem, 'component_params', {})
            a = float(cp.get('直角边1', width))
            b = float(cp.get('直角边2', height))
            h = float(cp.get('高度', z_end - z_start))
            params = {'直角边1': a, '直角边2': b, '高度': h}
            comp = TriangularPrismComponent(直角边1=a, 直角边2=b, 高度=h)
            return comp, params, '直角三棱柱'

        if comp_type == '圆柱':
            cp = getattr(elem, 'component_params', {})
            r = float(cp.get('半径', radius))
            h = float(cp.get('高度', z_end - z_start))
            params = {'半径': r, '高度': h}
            comp = CylinderComponent(半径=r, 高度=h)
            return comp, params, '圆柱'

        if comp_type == '正方体':
            cp = getattr(elem, 'component_params', {})
            a = float(cp.get('边长', max(width, height, z_end - z_start)))
            params = {'边长': a}
            comp = CubeComponent(边长=a)
            return comp, params, '正方体'

        if comp_type == '长方体':
            cp = getattr(elem, 'component_params', {})
            L = float(cp.get('长度', width))
            W = float(cp.get('宽度', height))
            H = float(cp.get('高度', z_end - z_start))
            params = {'长度': L, '宽度': W, '高度': H}
            comp = BoxComponent(长度=L, 宽度=W, 高度=H)
            return comp, params, '长方体'

        if comp_type == '球体':
            cp = getattr(elem, 'component_params', {})
            r = float(cp.get('半径', radius))
            params = {'半径': r}
            comp = SphereComponent(半径=r)
            return comp, params, '球体'

        if elem_type == 'line' or comp_type == 'Line3DComponent':
            x2 = getattr(elem, 'x2', x + 100)
            y2 = getattr(elem, 'y2', y)
            params = {'x1': x, 'y1': y, 'z1': z_start, 'x2': x2, 'y2': y2, 'z2': z_end, 'radius': thickness}
            comp = Line3DComponent(**params)
            return comp, params, 'Line3DComponent'

        elif elem_type == 'rectangle' or comp_type == 'SweepBoxComponent':
            params = {'x': x, 'y': y, 'z_bottom': z_start, 'z_top': z_end, 'length': width, 'width': height}
            comp = SweepBoxComponent(**params)
            return comp, params, 'SweepBoxComponent'

        elif elem_type == 'circle' or comp_type == 'Circle3DComponent':
            params = {'cx': x, 'cy': y, 'z_bottom': z_start, 'z_top': z_end, 'radius': radius}
            comp = Circle3DComponent(**params)
            return comp, params, 'Circle3DComponent'

        elif elem_type == 'arc' or comp_type == 'Arc3DComponent':
            start_angle = getattr(elem, 'start_angle', 0)
            end_angle = getattr(elem, 'end_angle', 90)
            params = {'cx': x, 'cy': y, 'radius': radius, 'start_angle': start_angle,
                      'end_angle': end_angle, 'z_bottom': z_start, 'z_top': z_end, 'thickness': thickness}
            comp = Arc3DComponent(**params)
            return comp, params, 'Arc3DComponent'

        elif elem_type == 'ellipse' or comp_type == 'Ellipse3DComponent':
            rx = getattr(elem, 'rx', radius)
            ry = getattr(elem, 'ry', radius * 0.6)
            params = {'cx': x, 'cy': y, 'rx': rx, 'ry': ry, 'z_bottom': z_start, 'z_top': z_end}
            comp = Ellipse3DComponent(**params)
            return comp, params, 'Ellipse3DComponent'

        elif elem_type == 'point' or comp_type == 'Point3DComponent':
            params = {'x': x, 'y': y, 'z': z, 'radius': thickness}
            comp = Point3DComponent(**params)
            return comp, params, 'Point3DComponent'

        elif elem_type == 'polygon' or comp_type == 'Polygon3DComponent':
            points_2d = _get_elem_points_2d(elem)
            if not points_2d:
                points_2d = [[x, y], [x + width, y], [x + width, y + height]]
            params = {'z_bottom': z_start, 'z_top': z_end}
            for i, (px, py) in enumerate(points_2d):
                params[f'px{i}'] = px
                params[f'py{i}'] = py
            params['point_count'] = len(points_2d)
            comp = Polygon3DComponent(points_2d=points_2d, z_bottom=z_start, z_top=z_end)
            return comp, params, 'Polygon3DComponent'

        elif elem_type == 'polyline' or comp_type == 'Polyline3DComponent':
            points_3d = []
            points_2d = _get_elem_points_2d(elem)
            if points_2d:
                for px, py in points_2d:
                    points_3d.append([px, py, z_start])
            else:
                points_3d = [[x, y, z_start], [x + 100, y, z_start]]
            params = {'thickness': thickness}
            for i, (px, py, pz) in enumerate(points_3d):
                params[f'px{i}'] = px
                params[f'py{i}'] = py
                params[f'pz{i}'] = pz
            params['point_count'] = len(points_3d)
            comp = Polyline3DComponent(points_3d=points_3d, thickness=thickness)
            return comp, params, 'Polyline3DComponent'

        _log(f"    unknown element type: {elem_type}, comp_type: {comp_type}")
        return None, None, None

    def _is_face_element(self, e):
        """判断元素是否为面元素（用于过滤）"""
        fi = getattr(e, 'face_info', None)
        return isinstance(fi, dict) and fi.get('face_name') is not None

    def sync_from_bimbase(self, selected_elements=None):
        _log("sync_from_bimbase() start")
        # 获取画板中选中的元素（过滤掉面元素）
        if selected_elements is None:
            selected_elements = [e for e in getattr(self.board, 'elements', [])
                                 if getattr(e, 'selected', False)]
        raw_count = len(selected_elements)
        selected_elements = [e for e in selected_elements if not self._is_face_element(e)]
        filtered_count = len(selected_elements)
        _log(f"  selected_elements raw={raw_count} filtered={filtered_count} (faces removed={raw_count-filtered_count})")
        for e in selected_elements:
            _log(f"    elem id={e.id[:8]} type={e.element_type.value} comp_type={getattr(e, 'component_type', '')}")
        # 同时记录被过滤掉的面元素信息（用于排查）
        if raw_count != filtered_count:
            for e in getattr(self.board, 'elements', []):
                if getattr(e, 'selected', False) and self._is_face_element(e):
                    _log(f"    [FACE-FILTERED] id={e.id[:8]} face_name={e.face_info.get('face_name','')} comp_type={getattr(e,'component_type','')}")
        
        # 如果没有选中非面元素，但当前处于面编辑模式，自动找到对应的隐藏源元素
        if not selected_elements:
            face_cid = getattr(self.board, '_face_component_id', None)
            if face_cid:
                for e in getattr(self.board, 'elements', []):
                    if e.id == face_cid and not self._is_face_element(e):
                        selected_elements = [e]
                        _log(f"  auto-selected hidden source element from face mode: {e.id[:8]}")
                        break

        entity_params_list = []
        CADBOARD_TYPES = {
            'SweepBoxComponent', 'Circle3DComponent', 'Arc3DComponent',
            'Ellipse3DComponent', 'Line3DComponent', 'Point3DComponent',
            'Polygon3DComponent', 'Polyline3DComponent',
            '直角三棱柱', '圆柱', '正方体', '长方体',
        }

        # 辅助：定期刷新 UI
        _process_events = None
        try:
            from PyQt5.QtWidgets import QApplication
            _process_events = lambda: QApplication.processEvents()
        except Exception:
            pass

        def _process_selected_entityids(entity_ids):
            """将 entityid 列表转换为参数列表"""
            result = []
            for idx, eid in enumerate(entity_ids):
                try:
                    if entityid_isvaid is not None:
                        try:
                            if not entityid_isvaid(eid):
                                continue
                        except Exception:
                            pass
                    dk = get_datakey_from_entity(eid)
                    _log(f"  entity {idx}: dk_type={type(dk).__name__ if dk is not None else 'None'}")
                    if dk is None:
                        _log(f"  entity {idx}: dk is None, skip")
                        continue
                    params = self._get_params_from_datakey(dk)
                    if params is None:
                        _log(f"  entity {idx}: params is None, skip")
                        continue
                    if not isinstance(params, dict):
                        _log(f"  entity {idx}: params is not dict (type={type(params).__name__}), skip")
                        continue
                    comp_type = params.get('_type', '')
                    _log(f"  entity {idx}: inferred comp_type='{comp_type}' keys={list(params.keys())[:8]}")
                    if comp_type in CADBOARD_TYPES:
                        result.append(params)
                        _log(f"  entity {idx}: APPEND to result")
                    else:
                        _log(f"  entity {idx}: comp_type '{comp_type}' not in CADBOARD_TYPES, skip")
                except Exception as e:
                    _log(f"  parse entity error: {e}")
                if _process_events and idx % 5 == 0:
                    _process_events()
            return result

        # ===== 优先方式1：获取用户在 BIMBase 中已选中的实体 =====
        selected_ids = []
        if get_entityid_from_boxselection is not None:
            try:
                selected_ids = get_entityid_from_boxselection() or []
                _log(f"  get_entityid_from_boxselection returned {len(selected_ids)} entities")
                if selected_ids:
                    entity_params_list = _process_selected_entityids(selected_ids)
            except Exception as e:
                _log(f"  get_entityid_from_boxselection error: {e}")

        # 方式1b：如果没有框选结果，尝试获取当前单个选中实体
        if not entity_params_list and get_current_entityId is not None:
            try:
                cur = get_current_entityId()
                if cur and entityid_isvaid and entityid_isvaid(cur):
                    _log("  get_current_entityId returned 1 entity")
                    selected_ids = [cur]
                    entity_params_list = _process_selected_entityids([cur])
            except Exception as e:
                _log(f"  get_current_entityId error: {e}")

        # ===== 回退方式2：扫描 instance key 找到 CADBoard 组件 =====
        # 框选/单选返回的 entity ID 对应的是代理实体，无法直接获取参数。
        # 因此回退到扫描全部 instance key，收集所有 CADBoard 组件。
        # 如果画板中有选中元素，后续会按位置匹配最接近的组件。
        if not entity_params_list and get_all_instancekey is not None and selected_ids:
            try:
                instance_keys = get_all_instancekey() or []
                total = len(instance_keys)
                _log(f"  fallback scan: get_all_instancekey returned {total} keys")
                MAX_SCAN = 200
                scanned = 0
                for ik in instance_keys:
                    if scanned >= MAX_SCAN:
                        _log(f"  fallback scan: reached MAX_SCAN ({MAX_SCAN}), stop. found {len(entity_params_list)} CADBoard components")
                        break
                    scanned += 1
                    try:
                        params = self._get_params_from_datakey(ik)
                        if params and params.get('_type', '') in CADBOARD_TYPES:
                            entity_params_list.append(params)
                            _log(f"  fallback scan: found CADBoard component #{len(entity_params_list)}: {params['_type']}")
                    except Exception as e:
                        _log(f"  fallback scan parse error: {e}")
                    if _process_events and scanned % 20 == 0:
                        _process_events()
            except Exception as e:
                _log(f"  fallback scan error: {e}")

        if not entity_params_list:
            if not selected_elements:
                _log("  no CADBoard entities selected in BIMBase")
                return 0, 0, 0
            # 尝试通过 component_registry.json 中记录的 instance 引用更新
            updated = 0
            failed = 0
            for elem in selected_elements:
                try:
                    if self._sync_single_from_bimbase(elem):
                        updated += 1
                    else:
                        failed += 1
                except Exception as e:
                    _log(f"  sync_from_bimbase element error: {e}")
                    failed += 1
            _log(f"sync_from_bimbase() done: {updated} updated, {failed} failed")
            return updated, 0, failed

        updated = 0
        created = 0
        failed = 0

        # 如果画板中有选中元素，优先为它们匹配更新
        if selected_elements:
            for elem in selected_elements:
                try:
                    matched = self._match_and_update_entity(entity_params_list, elem)
                    if matched:
                        updated += 1
                    else:
                        failed += 1
                except Exception as e:
                    _log(f"  update element error: {e}")
                    failed += 1
        else:
            # 画板没有选中元素：将BIMBase实体导入为新的画板元素
            from utils.component_registry import create_element_from_params
            for params in entity_params_list:
                try:
                    comp_type = params.get('_type', '')
                    new_elem = create_element_from_params(params, comp_type)
                    if new_elem:
                        new_elem.component_type = comp_type
                        new_elem.component_params = dict(params)
                        # 保存原始 BIMBase datakey，用于后续直接修改已有实例
                        dk = params.get('_datakey')
                        if dk is not None:
                            new_elem._bimbase_datakey = dk
                            _log(f"  saved _bimbase_datakey for new element {new_elem.id}")
                        self.board.elements.append(new_elem)
                        created += 1
                    else:
                        failed += 1
                except Exception as e:
                    _log(f"  create element error: {e}")
                    failed += 1

        _log(f"sync_from_bimbase() done: {updated} updated, {created} created, {failed} failed")
        return updated, created, failed

    def _match_and_update_entity(self, entity_params_list, elem):
        """为画板元素在BIMBase实体列表中找最佳匹配并更新"""
        comp_type = elem.component_type
        elem_id_short = getattr(elem, 'id', '')[:8]
        if not comp_type:
            # 尝试从元素几何推断类型
            et = getattr(elem, 'element_type', '')
            if hasattr(et, 'name'):
                et_name = et.name.lower()
            else:
                et_name = str(et).lower()
            type_map = {
                'rectangle': 'SweepBoxComponent',
                'circle': 'Circle3DComponent',
                'line': 'Line3DComponent',
                'arc': 'Arc3DComponent',
                'ellipse': 'Ellipse3DComponent',
                'point': 'Point3DComponent',
                'polygon': 'Polygon3DComponent',
                'polyline': 'Polyline3DComponent',
            }
            comp_type = type_map.get(et_name, '')
            _log(f"    _match: elem={elem_id_short} inferred comp_type={comp_type} from et_name={et_name}")

        if not comp_type:
            _log(f"    _match: elem={elem_id_short} FAILED - no comp_type")
            return False

        # 先筛选同类型实体
        candidates = [p for p in entity_params_list if p.get('_type', '') == comp_type]
        _log(f"    _match: elem={elem_id_short} comp_type={comp_type} candidates={len(candidates)} (total entities={len(entity_params_list)})")
        if not candidates:
            _log(f"    _match: elem={elem_id_short} FAILED - no candidates of type {comp_type}")
            return False
        if len(candidates) == 1:
            applied = apply_component_params_to_element(elem, candidates[0], comp_type)
            dk = candidates[0].get('_datakey')
            if dk is not None:
                elem._bimbase_datakey = dk
            _log(f"    _match: elem={elem_id_short} SUCCESS (1 candidate, applied={applied})")
            return True

        # 多个同类型实体：按位置参数找最近匹配
        # 获取画板元素的关键位置
        elem_pos = self._get_element_position(elem)
        if elem_pos is None:
            # 无法获取位置，直接用第一个
            apply_component_params_to_element(elem, candidates[0], comp_type)
            _log(f"    _match: elem={elem_id_short} SUCCESS (fallback to first candidate, no position)")
            return True

        best = None
        best_dist = float('inf')
        for params in candidates:
            pos = self._get_params_position(params, comp_type)
            if pos is None:
                continue
            dist = math.hypot(elem_pos[0] - pos[0], elem_pos[1] - pos[1])
            if dist < best_dist:
                best_dist = dist
                best = params

        if best:
            apply_component_params_to_element(elem, best, comp_type)
            dk = best.get('_datakey')
            if dk is not None:
                elem._bimbase_datakey = dk
            _log(f"    _match: elem={elem_id_short} SUCCESS (best match dist={best_dist:.1f})")
            return True
        _log(f"    _match: elem={elem_id_short} FAILED - no best match found")
        return False

    def _get_element_position(self, elem):
        """获取画板元素的2D位置（用于匹配）"""
        if hasattr(elem, 'x') and hasattr(elem, 'y'):
            return (float(elem.x), float(elem.y))
        if hasattr(elem, 'cx') and hasattr(elem, 'cy'):
            return (float(elem.cx), float(elem.cy))
        if hasattr(elem, 'x1') and hasattr(elem, 'y1'):
            return (float(elem.x1), float(elem.y1))
        return None

    def _get_params_position(self, params, comp_type):
        """获取BIMBase组件参数的2D位置"""
        if comp_type == 'SweepBoxComponent':
            return (float(params.get('x', 0)), float(params.get('y', 0)))
        if comp_type in ('Circle3DComponent', 'Arc3DComponent', 'Ellipse3DComponent'):
            return (float(params.get('cx', 0)), float(params.get('cy', 0)))
        if comp_type == 'Line3DComponent':
            return (float(params.get('x1', 0)), float(params.get('y1', 0)))
        if comp_type == 'Point3DComponent':
            return (float(params.get('x', 0)), float(params.get('y', 0)))
        return None

    def _sync_single_from_bimbase(self, elem):
        try:
            if self.registry.update_params_from_instance(elem.id):
                params, comp_type = self.registry.get_params(elem.id)
                if params and comp_type:
                    apply_component_params_to_element(elem, params, comp_type)
                    return True
            return self._sync_from_boxselect(elem)
        except Exception as e:
            _log(f"  _sync_single_from_bimbase error: {e}")
            return False

    def _sync_from_boxselect(self, elem):
        if get_element_from_boxselect is None:
            return False
        try:
            sel = get_element_from_boxselect()
            if not sel:
                return False
            for entity in sel:
                if not entityid_isvaid(entity):
                    continue
                datakey = get_datakey_from_entity(entity)
                if datakey is None:
                    continue
                params = self._get_params_from_datakey(datakey)
                if not params:
                    continue
                comp_type = params.get('_type', '')
                if comp_type and comp_type == elem.component_type:
                    apply_component_params_to_element(elem, params, comp_type)
                    return True
            return False
        except Exception as e:
            _log(f"  _sync_from_boxselect error: {e}")
            return False


def is_bimbase_available():
    return _pyp3d_ok


def sync_to_bimbase(board):
    """
    兼容board.py的调用接口。
    board: 画板对象 (含 elements 属性)
    返回: (success_count, error_list, replaced_bimbase_origins)
    """
    sync = BIMBaseSync(board)
    sync.sync_all()
    replaced = getattr(sync, 'replaced_bimbase_origins', [])
    success_count, error_count = getattr(sync, '_sync_stats', (0, 0))
    errors = []
    if error_count > 0:
        errors.append(f"{error_count} 个元素同步失败，详见 bimbase_sync_debug.log")
    return success_count, errors, replaced


def sync_from_bimbase(board, selected_elements=None):
    """
    兼容board.py的调用接口。
    board: 画板对象
    返回: (updated_count, created_count, error_list)
    """
    sync = BIMBaseSync(board)
    updated, created, failed = sync.sync_from_bimbase(selected_elements)
    errors = []
    if failed > 0:
        errors.append(f"{failed} 个元素处理失败")
    if updated == 0 and created == 0 and failed == 0:
        errors.append("未找到CADBoard组件。建议：先在BIMBase中框选要同步的组件，再点击更新。")
    # 如果通过回退扫描导入了多个组件，提示用户
    if created > 1:
        errors.append(f"扫描到 {created} 个CADBoard组件并已全部导入。"
                      f"框选实体为参数化组件代理，无法直接精确匹配单个组件。"
                      f"如需精确同步单个组件，建议先在画板中创建对应类型的占位元素并选中它，再点击更新。")
    return updated, created, errors
