# -*- coding: utf-8 -*-
"""
AI建模组件工厂
直接生成 pyp3d 参数化组件并通过 place_to 布置到指定坐标
"""
import math
import sys
import os
import traceback
import importlib.util

# 确保 AI_Modeling 目录在 sys.path 最前面，避免 CADBoard 的同名模块抢先。
_plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _plugin_dir in sys.path:
    sys.path.remove(_plugin_dir)
sys.path.insert(0, _plugin_dir)
# place/place_to 需要 sys.argv[0] 指向包含组件类定义的 aim_bimbase_sync.py
# BIMBase 通过 DependentFile 读取该文件来定位组件类
_aim_bimbase_sync_path = os.path.join(_plugin_dir, 'aim_bimbase_sync.py')

_pyp3d_ok = False
Component = Attr = Line = Section = Sweep = Cube = Sphere = Cone = None
Vec2 = Vec3 = Point = place = place_to = scale = translate = rotation = None
_pyp3d_create = None  # create() 直接放置 API（绕过被覆盖的 place_to）

try:
    from pyp3d import (
        Component, Attr, Line, Section,
        Sweep, Cube, Sphere, Cone,
        Vec2, Vec3, Point, place, place_to, scale, translate, rotation,
        create_geometry, entityid_isvaid,
    )
    _pyp3d_ok = True
except ImportError as e:
    pass

# 调试日志
_debug_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai_modeling_debug.log')

# 项目根目录（用于加载复杂组件）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 组件注册表（延迟导入，避免循环依赖）
_ComponentRegistry = None

def _get_registry():
    global _ComponentRegistry
    if _ComponentRegistry is None:
        from ai_modeling.component_registry import ComponentRegistry
        _ComponentRegistry = ComponentRegistry()
    return _ComponentRegistry

def _log(msg):
    try:
        with open(_debug_log_path, 'a', encoding='utf-8') as f:
            import datetime
            f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

_log("=" * 60)
_log("component_factory.py loaded")
_log("=" * 60)

# place_to 被 interface 层覆盖（需要 Handle 工具上下文），
# 这里直接调用底层 UnifiedFunction 绕过覆盖。
# 不同版本 pyp3d 的 place_to 实现不同，需要兼容两种调用方式：
#   - v18446497933429178368: UnifiedFunction(..., "BPParametricComponentManager::create")
#   - v18446497929133817856: UnifiedFunction(..., PARACMPT_PLACE_INSTANCE_TO)
_PlaceToDirect = None

def _init_place_to_direct():
    """动态构建底层 place_to 函数，绕过 interface 覆盖"""
    global _PlaceToDirect
    if _PlaceToDirect is not None:
        return True
    try:
        from pyp3d import DependentFile, UnifiedFunction, PARACMPT_PARAMETRIC_COMPONENT
        from pyp3d import PARACMPT_KEYWORD_DEPENDENT_FILE, PARACMPT_KEYWORD_TRANSFORMATION
        # 尝试获取 PARACMPT_PLACE_INSTANCE_TO（某些版本有）
        try:
            from pyp3d import PARACMPT_PLACE_INSTANCE_TO
            _place_to_flag = PARACMPT_PLACE_INSTANCE_TO
            _log(f"_init_place_to_direct: using PARACMPT_PLACE_INSTANCE_TO = {_place_to_flag}")
        except ImportError as e:
            _place_to_flag = None
            _log(f"_init_place_to_direct: PARACMPT_PLACE_INSTANCE_TO not available, will use BPParametricComponentManager::create")

        def _place_impl(noumenon, transform):
            # 关键：先调用 create_component 预处理
            # 它会设置 PARACMTP_PLACE_CUSTOM_TOOL=True 等关键标志
            from pyp3d import create_component
            _log("_place_impl: calling create_component...")
            create_component(noumenon)
            _log("_place_impl: create_component done")
            # 然后设置位置并调用 create
            noumenon[PARACMPT_KEYWORD_TRANSFORMATION] = transform
            try:
                _log("_place_impl: calling BPParametricComponentManager::create...")
                UnifiedFunction(PARACMPT_PARAMETRIC_COMPONENT, "BPParametricComponentManager::create")(noumenon)
                _log("_place_impl: create done")
                # 尝试获取 entityId 并验证
                try:
                    from pyp3d import get_place_to_entityId, entityid_isvaid
                    eid = get_place_to_entityId()
                    is_valid = entityid_isvaid(eid) if eid else False
                    mid = getattr(eid, '_ModelId', 'N/A')
                    eid_val = getattr(eid, '_ElementId', 'N/A')
                    _log(f"_place_impl: get_place_to_entityId() = ModelId={mid}, ElementId={eid_val}, valid={is_valid}")
                except Exception as e2:
                    _log(f"_place_impl: get_place_to_entityId() failed: {e2}")
            except Exception as e:
                _log(f"_place_impl: UnifiedFunction error: {e}")
                raise

        _PlaceToDirect = _place_impl
        _log("_PlaceToDirect initialized successfully")
        return True
    except Exception as e:
        _log(f"_init_place_to_direct failed: {e}")
        return False

_init_place_to_direct()

try:
    from pyp3d import export
except ImportError:
    def export(func):
        return func


def _set_argv_for_place():
    """place/place_to 依赖 sys.argv[0] 读取 DependentFile"""
    original = sys.argv[0]
    sys.argv[0] = _aim_bimbase_sync_path
    return original


def _restore_argv(original):
    sys.argv[0] = original


def _circle_section(radius, segments=32):
    points = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        points.append(Vec2(radius * math.cos(angle), radius * math.sin(angle)))
    return Section(*points)


# ============================================================
# 参数化组件定义
# ============================================================
# 关键：从 aim_bimbase_sync 导入组件类，这样 create_component 会记录
# PARACMPT_KEYWORD_REPRESENTATION = 'aim_bimbase_sync.CylinderComponent'
# python_transformation_operation 执行时就能正确找到模块

_CylinderComponent = _BoxComponent = _CubeComponent = _SphereComponent = _ConeComponent = _TriangularPrismComponent = None
_ApproachPierComponent = _GatePierComponent = _PileFoundationComponent = None

# 无论 pyp3d 是否可用都尝试导入（aim_bimbase_sync 自带占位回退，可离线导入），
# 保证 COMPONENT_CLASSES/COMPONENT_DEFAULTS 注册完整，便于离线测试与诊断。
try:
    from aim_bimbase_sync import (
        CylinderComponent as _CylinderComponent,
        BoxComponent as _BoxComponent,
        CubeComponent as _CubeComponent,
        SphereComponent as _SphereComponent,
        ConeComponent as _ConeComponent,
        TriangularPrismComponent as _TriangularPrismComponent,
        ApproachPierComponent as _ApproachPierComponent,
        GatePierComponent as _GatePierComponent,
        PileFoundationComponent as _PileFoundationComponent,
    )
    _log("component_factory: imported classes from aim_bimbase_sync")
except Exception as e:
    _log(f"component_factory: failed to import from aim_bimbase_sync: {e}")

# 兜底：如果 aim_bimbase_sync 导入失败且 pyp3d 可用，使用本地定义
if _CylinderComponent is None and Component is not None:
    class CylinderComponent(Component):
        def __init__(self, radius=100, height=200, ox=0, oy=0, oz=0):
            super().__init__()
            self['半径'] = Attr(float(radius), show=True, obvious=True)
            self['高度'] = Attr(float(height), show=True, obvious=True)
            self['偏移X'] = Attr(float(ox), show=False)
            self['偏移Y'] = Attr(float(oy), show=False)
            self['偏移Z'] = Attr(float(oz), show=False)
            self['圆柱'] = Attr(None, show=True)
            self.replace()
        @export
        def replace(self):
            section = _circle_section(self['半径'])
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            path = Line(Vec3(ox, oy, oz), Vec3(ox, oy, oz + self['高度']))
            self['圆柱'] = Sweep(section, path)
    _CylinderComponent = CylinderComponent

if _BoxComponent is None and Component is not None:
    class BoxComponent(Component):
        def __init__(self, length=200, width=100, height=150, ox=0, oy=0, oz=0):
            super().__init__()
            self['长度'] = Attr(float(length), show=True, obvious=True)
            self['宽度'] = Attr(float(width), show=True, obvious=True)
            self['高度'] = Attr(float(height), show=True, obvious=True)
            self['偏移X'] = Attr(float(ox), show=False)
            self['偏移Y'] = Attr(float(oy), show=False)
            self['偏移Z'] = Attr(float(oz), show=False)
            self['长方体'] = Attr(None, show=True)
            self.replace()
        @export
        def replace(self):
            L, W, H = self['长度'], self['宽度'], self['高度']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            section = Section(Vec2(ox, oy), Vec2(ox + L, oy), Vec2(ox + L, oy + W), Vec2(ox, oy + W))
            path = Line(Vec3(0, 0, oz), Vec3(0, 0, oz + H))
            self['长方体'] = Sweep(section, path)
    _BoxComponent = BoxComponent

if _CubeComponent is None and Component is not None:
    class CubeComponent(Component):
        def __init__(self, size=100, ox=0, oy=0, oz=0):
            super().__init__()
            self['边长'] = Attr(float(size), show=True, obvious=True)
            self['偏移X'] = Attr(float(ox), show=False)
            self['偏移Y'] = Attr(float(oy), show=False)
            self['偏移Z'] = Attr(float(oz), show=False)
            self['正方体'] = Attr(None, show=True)
            self.replace()
        @export
        def replace(self):
            a = self['边长']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            self['正方体'] = translate(ox, oy, oz) * scale(a, a, a) * Cube()
    _CubeComponent = CubeComponent

if _SphereComponent is None and Component is not None:
    class SphereComponent(Component):
        def __init__(self, radius=100, ox=0, oy=0, oz=0):
            super().__init__()
            self['半径'] = Attr(float(radius), show=True, obvious=True)
            self['偏移X'] = Attr(float(ox), show=False)
            self['偏移Y'] = Attr(float(oy), show=False)
            self['偏移Z'] = Attr(float(oz), show=False)
            self['球体'] = Attr(None, show=True)
            self.replace()
        @export
        def replace(self):
            r = self['半径']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            self['球体'] = translate(ox, oy, oz) * scale(r, r, r) * Sphere()
    _SphereComponent = SphereComponent

if _ConeComponent is None and Component is not None:
    class ConeComponent(Component):
        def __init__(self, radius=100, height=200, ox=0, oy=0, oz=0):
            super().__init__()
            self['底面半径'] = Attr(float(radius), show=True, obvious=True)
            self['高度'] = Attr(float(height), show=True, obvious=True)
            self['偏移X'] = Attr(float(ox), show=False)
            self['偏移Y'] = Attr(float(oy), show=False)
            self['偏移Z'] = Attr(float(oz), show=False)
            self['圆锥'] = Attr(None, show=True)
            self.replace()
        @export
        def replace(self):
            r, h = self['底面半径'], self['高度']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            self['圆锥'] = translate(ox, oy, oz) * scale(r, r, h) * Cone()
    _ConeComponent = ConeComponent

if _TriangularPrismComponent is None and Component is not None:
    class TriangularPrismComponent(Component):
        def __init__(self, 直角边1=100, 直角边2=100, 高度=200, ox=0, oy=0, oz=0):
            super().__init__()
            self['直角边1'] = Attr(float(直角边1), show=True, obvious=True)
            self['直角边2'] = Attr(float(直角边2), show=True, obvious=True)
            self['高度'] = Attr(float(高度), show=True, obvious=True)
            self['偏移X'] = Attr(float(ox), show=False)
            self['偏移Y'] = Attr(float(oy), show=False)
            self['偏移Z'] = Attr(float(oz), show=False)
            self['直角三棱柱'] = Attr(None, show=True)
            self.replace()
        @export
        def replace(self):
            a = self['直角边1']
            b = self['直角边2']
            h = self['高度']
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
            section = Section(Vec2(ox, oy), Vec2(ox + a, oy), Vec2(ox, oy + b))
            path = Line(Vec3(0, 0, oz), Vec3(0, 0, oz + h))
            self['直角三棱柱'] = Sweep(section, path)
    _TriangularPrismComponent = TriangularPrismComponent

# 统一别名
COMPONENT_CLASSES = {
    'cylinder': _CylinderComponent,
    'box': _BoxComponent,
    'cube': _CubeComponent,
    'sphere': _SphereComponent,
    'cone': _ConeComponent,
    'triangular_prism': _TriangularPrismComponent,
    # 引桥桥墩：类定义在 aim_bimbase_sync.py（DependentFile），BIMBase 才能序列化/放置
    'pier': _ApproachPierComponent,
    'gate_pier': _GatePierComponent,
    'pile_foundation': _PileFoundationComponent,
}

COMPONENT_DEFAULTS = {
    'cylinder': {'radius': 100, 'height': 200},
    'box': {'length': 200, 'width': 100, 'height': 150},
    'cube': {'size': 100},
    'sphere': {'radius': 100},
    'cone': {'radius': 100, 'height': 200},
    'triangular_prism': {'直角边1': 100, '直角边2': 100, '高度': 200},
    'pier': dict(_ApproachPierComponent.DEFAULT_PARAMS) if _ApproachPierComponent is not None else {
        '盖梁总长': 1930.0, '盖梁总高': 300.0, '盖梁宽': 300.0,
        '墩柱直径': 250.0, '墩柱间距': 1140.0, '墩高': 1200.0, '系梁根数': 2,
    },
    'gate_pier': dict(_GatePierComponent.DEFAULT_PARAMS) if _GatePierComponent is not None else {
        '盖梁总长': 4700.0, '盖梁总高': 400.0, '盖梁宽': 1000.0, '墩高': 5000.0,
        '墩柱间距': 3500.0, '柱顶宽': 1200.0, '柱底宽': 1400.0,
        '柱顶厚': 1000.0, '柱底厚': 1200.0, '系梁根数': 1,
    },
    'pile_foundation': dict(_PileFoundationComponent.DEFAULT_PARAMS) if _PileFoundationComponent is not None else {
        '承台长': 5500.0, '承台宽': 2350.0, '承台高': 500.0,
        '桩径': 250.0, '桩长': 5000.0, '桩间距': 630.0, '桩列数': 9, '桩排数': 4,
    },
}

# 各组件允许写入的参数键（用于过滤解析器/注册表带入的伪参数与内部键）
_COMPONENT_ALLOWED_KEYS = {
    'pier': set(COMPONENT_DEFAULTS['pier'].keys()) | {'偏移X', '偏移Y', '偏移Z'},
    'gate_pier': set(COMPONENT_DEFAULTS['gate_pier'].keys()) | {'偏移X', '偏移Y', '偏移Z'},
    'pile_foundation': set(COMPONENT_DEFAULTS['pile_foundation'].keys()) | {'偏移X', '偏移Y', '偏移Z'},
}

# 复杂组件（__init__ 不接受参数，参数通过 Attr 设置）
_COMPLEX_COMPONENT_TYPES = set()


def _read_component_keys(comp):
    """安全读取 Component 的所有键名"""
    try:
        if hasattr(comp, 'keys'):
            return list(comp.keys())
        if hasattr(comp, '__iter__'):
            return list(comp)
    except Exception as e:
        _log(f"_read_component_keys error: {e}")
    return []


def _attr_to_value(v):
    """把 Attr/数值统一转成可序列化的 Python 值"""
    try:
        if hasattr(v, 'value'):
            v = v.value
        return float(v)
    except Exception:
        pass
    try:
        return int(v)
    except Exception:
        pass
    if v is None:
        return None
    return str(v)


def _load_complex_component(file_path, class_name, component_key):
    """动态加载组件测试目录下的复杂组件"""
    global _COMPLEX_COMPONENT_TYPES
    if not os.path.exists(file_path):
        _log(f"complex component file not found: {file_path}")
        return False
    try:
        module_name = f"_ai_modeling_complex_{component_key}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        # 避免模块内 if __name__ == '__main__' 的 place() 被触发
        module.__name__ = module_name
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, class_name)

        # 实例化一次以读取默认参数
        defaults = {}
        try:
            sample = cls()
            for k in _read_component_keys(sample):
                try:
                    defaults[k] = _attr_to_value(sample[k])
                except Exception as e2:
                    _log(f"  read default {k} failed: {e2}")
        except Exception as e:
            _log(f"complex component sample instantiate failed: {e}")

        COMPONENT_CLASSES[component_key] = cls
        COMPONENT_DEFAULTS[component_key] = defaults
        _COMPLEX_COMPONENT_TYPES.add(component_key)
        _log(f"loaded complex component '{component_key}' from {file_path} with defaults={defaults}")
        return True
    except Exception as e:
        _log(f"failed to load complex component '{component_key}': {e}")
        return False


# 尝试加载复杂组件（失败不影响基础几何体）
# 注意：引桥桥墩（pier）已改为在 aim_bimbase_sync.py 中定义（BIMBase 序列化要求），
# 不再走动态加载；索缆锚锭（anchor）暂未迁移，保持原动态加载路径。
_load_complex_component(
    os.path.join(_PROJECT_ROOT, '组件测试', '索缆锚锭.py'),
    '索塔锚块',
    'anchor'
)


def _get_valid_kwargs(cls, kwargs):
    """过滤掉组件 __init__ 不接受的参数，避免 AI 误识别参数导致构造失败"""
    try:
        import inspect
        sig = inspect.signature(cls.__init__)
        # __init__ 含 **kwargs 时放行全部参数（如 ApproachPierComponent）
        for p in sig.parameters.values():
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                return kwargs
        valid = set(sig.parameters.keys()) - {'self'}
        return {k: v for k, v in kwargs.items() if k in valid}
    except Exception:
        return kwargs


def _filter_component_params(component_type, params):
    """过滤不属于该组件的参数（解析器伪参数、注册表带入的内部键等）"""
    allowed = _COMPONENT_ALLOWED_KEYS.get(component_type)
    if not allowed or not params:
        return params
    return {k: v for k, v in params.items() if k in allowed}


def create_component(component_type, params=None):
    """
    创建指定类型的参数化组件实例（几何体出生在原点）
    返回: component_instance or None
    """
    if not _pyp3d_ok:
        return None
    cls = COMPONENT_CLASSES.get(component_type)
    if not cls:
        return None
    defaults = COMPONENT_DEFAULTS.get(component_type, {}).copy()
    color = None
    if params:
        params = dict(params)
        # 颜色不是组件构造参数，单独取出在建模完成后整体上色
        color = params.pop('颜色', None)
        defaults.update(_filter_component_params(component_type, params))

    try:
        if component_type in _COMPLEX_COMPONENT_TYPES:
            # 复杂组件 __init__ 不接受参数，先默认实例化再覆盖 Attr
            comp = cls()
            for k, v in defaults.items():
                try:
                    if k in _read_component_keys(comp):
                        comp[k] = v
                except Exception as e2:
                    _log(f"create_component override {k} failed: {e2}")
            if hasattr(comp, 'replace'):
                try:
                    comp.replace()
                except Exception as e2:
                    _log(f"create_component complex replace failed: {e2}")
        else:
            defaults = _get_valid_kwargs(cls, defaults)
            comp = cls(**defaults)

        # 记录 AI 建模使用的参数和类型，供注册表/复制使用（含颜色，复制时保留颜色）
        try:
            comp._ai_modeling_component_type = component_type
            meta = dict(defaults)
            if color:
                meta['颜色'] = color
            comp._ai_modeling_params = meta
        except Exception as e2:
            _log(f"create_component store metadata failed: {e2}")
        # 整体上色（6面统一色）：pyp3d Attr 只能存标量/字符串，
        # 颜色以 "r,g,b,a" 字符串写入 '颜色' 属性，由组件 replace() 解析上色并保持；
        # 同时记录 _ai_color 供放置阶段兜底重染，写入失败则直接染几何
        if color:
            try:
                comp._ai_color = color
            except Exception:
                pass
            try:
                comp['颜色'] = ','.join(str(float(v)) for v in color)
                if hasattr(comp, 'replace'):
                    comp.replace()
            except Exception as e:
                _log(f"create_component set 颜色 attr failed: {e}")
                apply_component_color(comp, color, component_type)
        return comp
    except Exception as e:
        _log(f"create_component error: {e}")
        return None


def _infer_component_type_from_comp(comp):
    """从组件实例推断 component_type key"""
    if comp is None:
        return None
    # 优先使用创建时记录的元数据
    try:
        t = getattr(comp, '_ai_modeling_component_type', None)
        if t:
            return t
    except Exception:
        pass
    # 按类型名匹配
    type_name = type(comp).__name__
    name_map = {
        'CylinderComponent': 'cylinder',
        'BoxComponent': 'box',
        'CubeComponent': 'cube',
        'SphereComponent': 'sphere',
        'ConeComponent': 'cone',
        'TriangularPrismComponent': 'triangular_prism',
        'ApproachPierComponent': 'pier',
        '引桥桥墩': 'pier',
        'GatePierComponent': 'gate_pier',
        '门式桥墩': 'gate_pier',
        'PileFoundationComponent': 'pile_foundation',
        '承台及桩基': 'pile_foundation',
        '索塔锚块': 'anchor',
    }
    if type_name in name_map:
        return name_map[type_name]
    # 按已有类反向查找
    for key, cls in COMPONENT_CLASSES.items():
        if type(comp) is cls:
            return key
    return None


def _extract_component_params_from_comp(comp):
    """从组件实例提取可序列化的参数字典"""
    if comp is None:
        return {}
    # 优先使用创建时记录的参数
    try:
        params = getattr(comp, '_ai_modeling_params', None)
        if params:
            return dict(params)
    except Exception:
        pass
    # 实时读取 Attr
    result = {}
    for k in _read_component_keys(comp):
        try:
            result[k] = _attr_to_value(comp[k])
        except Exception:
            pass
    return result


def _record_placement(comp, x, y, z, eid=None):
    """将成功放置的组件记录到注册表"""
    try:
        registry = _get_registry()
        entity_id = eid
        instance_key = None

        # 尝试通过 entity_id 获取 datakey
        if entity_id is not None:
            try:
                from pyp3d import get_datakey_from_entity
                dk = get_datakey_from_entity(entity_id)
                if dk is not None:
                    instance_key = dk
            except Exception as e:
                _log(f"_record_placement get_datakey_from_entity failed: {e}")

        # 如果没有传入 entity_id，尝试从 place_to 工具读取
        if entity_id is None:
            try:
                from pyp3d import get_place_to_entityId, entityid_isvaid
                eid2 = get_place_to_entityId()
                if eid2 is not None and entityid_isvaid(eid2):
                    entity_id = eid2
            except Exception:
                pass

        comp_type = _infer_component_type_from_comp(comp)
        params = _extract_component_params_from_comp(comp)
        placement = {'x': float(x), 'y': float(y), 'z': float(z)}
        key = instance_key if instance_key is not None else entity_id
        registry.register(key, comp_type, params, placement, entity_id=entity_id)
    except Exception as e:
        _log(f"_record_placement error: {e}")


def _count_entities():
    """统计当前模型实体数（用于校验放置是否真的成功），失败返回 -1"""
    try:
        from pyp3d import get_all_entityid
        ids = get_all_entityid() or []
        return len(ids)
    except Exception as e:
        _log(f"_count_entities failed: {e}")
        return -1


def _verify_new_entity(before_count):
    """校验放置后是否真的产生了新实体；before_count < 0 表示无法统计，回退到 entityId 校验"""
    eid_valid = False
    try:
        from pyp3d import get_place_to_entityId
        eid = get_place_to_entityId()
        eid_valid = bool(eid) and bool(entityid_isvaid(eid))
    except Exception as e:
        _log(f"_verify_new_entity: get_place_to_entityId failed: {e}")
    if before_count >= 0:
        after_count = _count_entities()
        _log(f"_verify_new_entity: before={before_count}, after={after_count}, eid_valid={eid_valid}")
        return after_count > before_count or eid_valid
    _log(f"_verify_new_entity: entity count unavailable, eid_valid={eid_valid}")
    return eid_valid


# 组件类型 → 几何属性键名（上色时定位几何体用）
_GEOMETRY_KEY_MAP = {
    'cylinder': '圆柱', 'box': '长方体', 'cube': '正方体', 'sphere': '球体',
    'cone': '圆锥', 'triangular_prism': '直角三棱柱', 'pier': '引桥桥墩',
    'gate_pier': '门式桥墩', 'pile_foundation': '承台及桩基',
    'anchor': '索塔',
}


def apply_component_color(comp, rgba, comp_type=None):
    """
    给组件几何整体上色（现阶段为6面统一色，BIMBase默认方向）。
    rgba: 0~1 浮点 (r, g, b[, a])。返回是否成功。
    """
    if comp is None or not rgba:
        return False
    try:
        key = _GEOMETRY_KEY_MAP.get(comp_type or _infer_component_type_from_comp(comp))
        if not key or key not in comp:
            # 兜底：扫描组件属性，找到带 .color() 方法的几何值（如动态加载的锚锭）
            key = None
            for k in _read_component_keys(comp):
                try:
                    v = comp[k]
                except Exception:
                    continue
                if v is not None and hasattr(v, 'color'):
                    key = k
                    break
        if not key:
            return False
        geom = comp[key]
        if geom is None or not hasattr(geom, 'color'):
            return False
        vals = [float(v) for v in rgba]
        comp[key] = geom.color(*vals)
        _log(f"apply_component_color: {key} colored rgba={vals}")
        return True
    except Exception as e:
        _log(f"apply_component_color error: {e}")
        return False


def _bake_offset_attrs(comp, x, y, z):
    """
    把放置坐标写入组件的 偏移X/Y/Z 参数，并设为属性面板可见。
    写入后几何位置以组件参数为准，调用方应使用恒等变换放置，避免双重偏移。
    返回 True 表示烘焙成功。
    """
    if comp is None or Attr is None:
        return False
    try:
        keys = set(_read_component_keys(comp))
    except Exception:
        return False
    if '偏移X' not in keys:
        return False
    ok = True
    for k, v in (('偏移X', x), ('偏移Y', y), ('偏移Z', z)):
        try:
            comp[k] = Attr(float(v), show=True, obvious=True)
        except Exception as e:
            _log(f"_bake_offset_attrs: assign Attr {k} failed: {e}")
            try:
                comp[k] = float(v)
            except Exception as e2:
                _log(f"_bake_offset_attrs: assign {k} failed: {e2}")
                ok = False
    if ok:
        _log(f"_bake_offset_attrs: baked ({x},{y},{z}) into 偏移X/Y/Z (visible)")
    return ok


def place_component_at(comp, x, y, z, bake=True):
    """
    将组件自动布置到指定三维坐标（官方 create_geometry 优先）

    放置坐标会先烘焙进组件的 偏移X/偏移Y/偏移Z 参数（属性面板可见），
    几何位置以该参数为准，放置变换使用恒等矩阵，避免双重偏移；
    若组件没有偏移参数（烘焙失败），仍按原方式用 translate(x,y,z) 放置。

    官方推荐的原地创建方式：
      create_geometry(translate(x,y,z) * comp)
    该 API 在全局坐标系原点创建几何体，因此先通过 translate 把组件变换到
    目标位置；它不依赖 place/place_to 的交互式工具上下文，也不会触发
    BPParametricComponentManager::create 的反向回调，从而避免破坏 pyp3d
    的 _Core 通信线程。

    兜底策略：
      1. create_geometry 直接创建
      2. _PlaceToDirect / place_to
      3. 文件导入方案（IFC）
      4. 模拟点击方案（坐标烘焙 + SendInput）
      5. 回退到 place() 手动放置
    返回: (success: bool, message: str)
    """
    _log(f"place_component_at: type={type(comp).__name__ if comp else 'None'}, pos=({x},{y},{z})")
    if not _pyp3d_ok:
        return False, "pyp3d 未加载"
    if comp is None:
        return False, "组件为 None"

    # 方案0（官方首选）：create_geometry + 平移变换
    try:
        _log(f"place_component_at: trying create_geometry at ({x},{y},{z})")
        # 先把放置坐标烘焙进组件的 偏移X/Y/Z 参数（属性面板可见），
        # 几何位置以组件参数为准，放置变换用恒等矩阵，避免双重偏移；
        # bake=False（用户要求"不写入位置参数"）时跳过烘焙，用 translate 放置
        baked = _bake_offset_attrs(comp, x, y, z) if bake else False
        if hasattr(comp, 'replace'):
            try:
                comp.replace()
                _log("place_component_at: comp.replace() done")
            except Exception as e:
                _log(f"place_component_at: comp.replace() warning: {e}")
        # 若组件带颜色但 replace 未保持（未支持'颜色'属性的组件类），重新染色兜底
        ai_color = getattr(comp, '_ai_color', None)
        if ai_color:
            apply_component_color(comp, ai_color)
        if baked:
            eid = create_geometry(translate(0.0, 0.0, 0.0) * comp)
        else:
            eid = create_geometry(translate(float(x), float(y), float(z)) * comp)
        is_valid = entityid_isvaid(eid) if eid is not None else False
        _log(f"place_component_at: create_geometry eid={eid}, valid={is_valid}")
        if is_valid:
            _record_placement(comp, x, y, z, eid=eid)
            try:
                from pyp3d import zoom_all_view
                zoom_all_view()
            except Exception as e:
                _log(f"place_component_at: zoom_all_view failed: {e}")
            return True, f"✅ 已自动布置到 ({x}, {y}, {z})"
    except Exception as e:
        _log(f"place_component_at: create_geometry failed: {e}")

    original_argv = _set_argv_for_place()
    try:
        # 方案1：绕过 interface 覆盖的 _PlaceToDirect，直接设置 transformation 后创建实例
        if _PlaceToDirect is not None:
            try:
                _log(f"place_component_at: trying _PlaceToDirect({x},{y},{z})")
                before = _count_entities()
                _PlaceToDirect(comp, translate(float(x), float(y), float(z)))
                if _verify_new_entity(before):
                    _log("place_component_at: _PlaceToDirect SUCCESS (verified)")
                    _record_placement(comp, x, y, z)
                    return True, f"✅ 已自动布置到 ({x}, {y}, {z})"
                _log("place_component_at: _PlaceToDirect produced no new entity, falling through")
            except Exception as e:
                _log(f"place_component_at: _PlaceToDirect failed: {e}")

        # 方案1b：原生 place_to 直接放置
        if place_to is not None:
            try:
                _log(f"place_component_at: trying place_to({x},{y},{z})")
                before = _count_entities()
                place_to(comp, translate(float(x), float(y), float(z)))
                if _verify_new_entity(before):
                    _log("place_component_at: place_to SUCCESS (verified)")
                    _record_placement(comp, x, y, z)
                    return True, f"✅ 已自动布置到 ({x}, {y}, {z})"
                _log("place_component_at: place_to produced no new entity, falling through")
            except Exception as e:
                _log(f"place_component_at: place_to failed: {e}")

        # 方案1c：把坐标烘焙到组件内部偏移参数，再走 place_to（identity）
        # （bake=False 表示用户要求"不写入位置参数"，跳过烘焙，直接用原坐标放置）
        if bake:
            try:
                _log(f"place_component_at: baking offset ({x},{y},{z}) into component")
                comp['偏移X'] = float(x)
                comp['偏移Y'] = float(y)
                comp['偏移Z'] = float(z)
                if hasattr(comp, 'replace'):
                    comp.replace()
                    _log("place_component_at: component replace() done with offset")
            except Exception as e:
                _log(f"place_component_at: bake offset failed: {e}")

        if place_to is not None:
            try:
                _log("place_component_at: trying place_to with baked offset")
                place_to(comp, translate(0.0, 0.0, 0.0) if bake else translate(float(x), float(y), float(z)))
                _log("place_component_at: place_to with baked offset SUCCESS")
                _record_placement(comp, x, y, z)
                return True, f"✅ 已自动布置到 ({x}, {y}, {z})"
            except Exception as e:
                _log(f"place_component_at: place_to with baked offset failed: {e}")

        # 方案2：文件导入（纯自动化）
        try:
            comp_type = None
            comp_params = {}
            type_name = type(comp).__name__.lower()
            if 'cylinder' in type_name:
                comp_type = 'cylinder'
                comp_params = {'radius': comp['半径'], 'height': comp['高度']}
            elif 'box' in type_name and 'cube' not in type_name:
                comp_type = 'box'
                comp_params = {'length': comp['长度'], 'width': comp['宽度'], 'height': comp['高度']}
            elif 'cube' in type_name:
                comp_type = 'cube'
                comp_params = {'size': comp['边长']}
            elif 'sphere' in type_name:
                comp_type = 'sphere'
                comp_params = {'radius': comp['半径']}
            elif 'cone' in type_name:
                comp_type = 'cone'
                comp_params = {'radius': comp['底面半径'], 'height': comp['高度']}

            if comp_type:
                ok, msg = _place_via_file_import(comp_type, comp_params, x, y, z)
                if ok:
                    _record_placement(comp, x, y, z)
                    return True, msg
                _log(f"place_component_at: file import failed, falling back: {msg}")
        except Exception as e:
            _log(f"place_component_at: file import exception: {e}")

        # 方案3：自动模拟交互点击
        try:
            _auto_place_click_and_move(comp, float(x), float(y), float(z))
            _record_placement(comp, x, y, z)
            return True, f"✅ 已自动布置到 ({x}, {y}, {z})"
        except Exception as e:
            _log(f"place_component_at: auto_click scheme failed: {e}")

        # 方案4：回退到 place() 手动放置
        if place is not None:
            _log("place_component_at: falling back to place()")
            place(comp)
            return True, "已启动手动放置工具（请在视图中点击确认位置）"

        return False, "自动布置和手动放置均失败"
    except Exception as e:
        _log(f"place_component_at: exception: {e}")
        return False, f"放置失败: {e}"
    finally:
        _restore_argv(original_argv)


def _auto_place_click_and_move(comp, x, y, z):
    """
    自动模拟交互放置：
    1. 标准化视图（俯视图+全图缩放），确保点击位置接近原点
    2. 启动 place() 手动放置工具
    3. 用 SendInput 模拟真实鼠标点击到 BIMBase 视图子窗口
    4. 几何体本身已包含目标坐标偏移，直接出生在目标位置
    5. 不需要 python_transformation_operation
    """
    import time
    import ctypes
    from ctypes import wintypes

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

    # 0. 标准化视图：俯视图 + 全图缩放，确保视图中心接近原点
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

    # 0. 启动手动放置工具
    _log("_auto_place: starting place() tool...")
    place(comp)
    time.sleep(0.6)

    # 1. 【关键尝试】利用 place() 创建的活跃工具上下文，直接调用 create_geometry()
    # 如果成功，完全不需要鼠标点击！
    try:
        from pyp3d import create_geometry, entityid_isvaid, get_place_to_entityId
        _log("_auto_place: trying create_geometry() while place tool is active...")
        eid = create_geometry(comp)
        mid = getattr(eid, '_ModelId', 'N/A')
        eid_val = getattr(eid, '_ElementId', 'N/A')
        is_valid = entityid_isvaid(eid) if eid else False
        _log(f"_auto_place: create_geometry() = ModelId={mid}, ElementId={eid_val}, valid={is_valid}")
        if eid and entityid_isvaid(eid):
            _log("_auto_place: create_geometry() SUCCEEDED! No click needed!")
            # 退出工具并刷新视图
            try:
                from pyp3d import exit_tool, zoom_all_view
                exit_tool()
                time.sleep(0.3)
                zoom_all_view()
                _log("_auto_place: zoom_all_view() called")
            except Exception as e:
                _log(f"_auto_place: cleanup failed: {e}")
            return  # 直接返回，不执行 SendInput
    except Exception as e:
        _log(f"_auto_place: create_geometry() failed: {e}")

    # 2. 如果 create_geometry 失败，继续 SendInput 方案
    # 找到 BIMBase 主窗口
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
        for hwnd, title, w, h in _windows:
            area = w * h
            if 'AI' not in title and '智能建模' not in title and area > max_area:
                max_area = area
                bimbase_hwnd = hwnd

    if bimbase_hwnd is None:
        raise Exception("BIMBase main window not found via EnumWindows")

    _log(f"_auto_place: selected main hwnd={bimbase_hwnd}")

    # 3. 找到最大的可见子窗口（视图）
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
    _children.sort(key=lambda t: t[1]*t[2], reverse=True)
    for hwnd, w, h in _children[:5]:
        _log(f"_auto_place: child hwnd={hwnd} size={w}x{h}")

    if _children:
        viewport_hwnd = _children[0][0]
    else:
        viewport_hwnd = bimbase_hwnd

    # 4. 获取视图子窗口的屏幕坐标
    rect = _RECT()
    user32.GetWindowRect(viewport_hwnd, ctypes.byref(rect))
    cx = rect.left + (rect.right - rect.left) // 2
    cy = rect.top + (rect.bottom - rect.top) // 2
    _log(f"_auto_place: viewport hwnd={viewport_hwnd} screen=({rect.left},{rect.top},{rect.right},{rect.bottom}) click_screen=({cx},{cy})")

    # 5. 将 BIMBase 设为前台窗口（确保鼠标事件被它接收）
    user32.SetForegroundWindow(bimbase_hwnd)
    time.sleep(0.1)

    # 6. 用 SendInput 模拟真实鼠标点击（绝对坐标）
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    abs_x = int((cx * 65535) / screen_w)
    abs_y = int((cy * 65535) / screen_h)

    _log(f"_auto_place: SendInput click abs=({abs_x},{abs_y}) screen=({screen_w}x{screen_h})")

    inp = _INPUT()
    inp.type = 0  # INPUT_MOUSE

    # 移动到目标位置 + 左键按下
    inp.mi.dx = abs_x
    inp.mi.dy = abs_y
    inp.mi.dwFlags = 0x8000 | 0x0001 | 0x0002  # ABSOLUTE | MOVE | LEFTDOWN
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    time.sleep(0.05)

    # 左键释放
    inp.mi.dwFlags = 0x8000 | 0x0001 | 0x0004  # ABSOLUTE | MOVE | LEFTUP
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    # 7. 等待组件创建
    time.sleep(0.5)

    # 8. 退出放置工具
    try:
        from pyp3d import exit_tool
        exit_tool()
        _log("_auto_place: exit_tool() called")
    except Exception as e:
        _log(f"_auto_place: exit_tool() failed: {e}")

    # 9. 验证 entityId（可选，用于日志诊断）
    from pyp3d import get_place_to_entityId, entityid_isvaid
    eid = get_place_to_entityId()
    mid = getattr(eid, '_ModelId', 'N/A')
    eid_val = getattr(eid, '_ElementId', 'N/A')
    is_valid = entityid_isvaid(eid) if eid else False
    _log(f"_auto_place: entityId = ModelId={mid}, ElementId={eid_val}, valid={is_valid}")

    # 几何体本身已包含目标坐标偏移，不需要额外移动
    _log("_auto_place: geometry already contains target offset, placement done")

    # 10. 刷新视图确保组件可见
    try:
        zoom_all_view()
        _log("_auto_place: zoom_all_view() called")
    except Exception as e:
        _log(f"_auto_place: zoom_all_view() failed: {e}")


# ============================================================
# 文件导入方案（纯自动化，无需点击）
# ============================================================

def _place_via_file_import(component_type, params, x, y, z):
    """
    通过生成文件并导入的方式创建几何体
    1. 生成 IFC 文件
    2. 调用 execute_command 导入
    返回: (success, msg)
    """
    # 确保 ai_modeling 目录在 sys.path 中（CADBoard 加载时路径可能不同）
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    if _current_dir not in sys.path:
        sys.path.insert(0, _current_dir)
    _parent_dir = os.path.dirname(_current_dir)
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

    try:
        from geometry_exporter import export_geometry
    except ImportError as e:
        _log(f"_place_via_file_import: cannot import geometry_exporter: {e}")
        return False, f"缺少 geometry_exporter: {e}"

    import tempfile

    # 构建几何参数
    geom_params = {'cx': float(x), 'cy': float(y), 'cz': float(z)}
    if component_type == 'cylinder':
        geom_params['radius'] = float(params.get('radius', 100))
        geom_params['height'] = float(params.get('height', 200))
    elif component_type in ('box', 'cube'):
        if component_type == 'cube':
            s = float(params.get('size', 100))
            geom_params['length'] = s
            geom_params['width'] = s
            geom_params['height'] = s
        else:
            geom_params['length'] = float(params.get('length', 200))
            geom_params['width'] = float(params.get('width', 100))
            geom_params['height'] = float(params.get('height', 150))
    elif component_type == 'sphere':
        geom_params['radius'] = float(params.get('radius', 100))
    elif component_type == 'cone':
        geom_params['radius'] = float(params.get('radius', 100))
        geom_params['height'] = float(params.get('height', 200))
    else:
        return False, f"不支持的组件类型: {component_type}"

    # 生成临时 IFC 文件
    tmp_dir = tempfile.gettempdir()
    tmp_file = os.path.join(tmp_dir, f"ai_model_{component_type}_{int(x)}_{int(y)}_{int(z)}.ifc")

    try:
        _log(f"_place_via_file_import: generating IFC to {tmp_file}")
        export_geometry('ifc', component_type, tmp_file, **geom_params)
        _log(f"_place_via_file_import: IFC generated, size={os.path.getsize(tmp_file)} bytes")
    except Exception as e:
        _log(f"_place_via_file_import: IFC generation failed: {e}")
        return False, f"IFC 生成失败: {e}"

    # 调用导入命令
    try:
        from pyp3d import execute_command, get_all_entityid
        # 记录导入前的实体数量
        try:
            before_ids = get_all_entityid() or []
            before_count = len(before_ids)
        except Exception as e:
            _log(f"_place_via_file_import: get_all_entityid() before failed: {e}")
            before_count = -1

        # 尝试多种命令格式
        cmd_variants = [
            f'ImportIfcBimebase "{tmp_file}"',
            f'ImportIfcBimebase {tmp_file}',
            'ImportIfcBimebase',
        ]
        import time
        for cmd in cmd_variants:
            _log(f"_place_via_file_import: trying execute_command('{cmd}')...")
            try:
                execute_command(cmd)
                _log(f"_place_via_file_import: execute_command('{cmd}') returned")
                # 等待导入完成
                time.sleep(2.0)
            except Exception as e:
                _log(f"_place_via_file_import: execute_command('{cmd}') failed: {e}")
                continue
            # 验证：检查实体数量是否增加
            try:
                after_ids = get_all_entityid() or []
                after_count = len(after_ids)
                _log(f"_place_via_file_import: entity count before={before_count}, after={after_count}")
                if after_count > before_count:
                    return True, f"✅ 已导入 IFC，新增 {after_count - before_count} 个实体: {tmp_file}"
                else:
                    _log(f"_place_via_file_import: no new entities detected, trying next variant")
                    continue
            except Exception as e2:
                _log(f"_place_via_file_import: get_all_entityid() after failed: {e2}")
                continue
        return False, "IFC 导入未产生新实体"
    except Exception as e:
        _log(f"_place_via_file_import: import error: {e}")
        return False, f"导入失败: {e}"


def batch_place(component_type, params_list, coords_list):
    """
    批量生成并放置组件
    params_list: 参数字典列表（与 coords_list 一一对应）
    coords_list: [(x,y,z), ...]
    返回: [(success, msg), ...]
    """
    results = []
    for params, (x, y, z) in zip(params_list, coords_list):
        comp = create_component(component_type, params)
        result = place_component_at(comp, x, y, z)
        results.append(result)
    return results
