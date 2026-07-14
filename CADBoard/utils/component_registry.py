# -*- coding: utf-8 -*-
"""
BIMBase组件注册表 - 管理元素与参数化组件的映射关系

Phase 2 功能:
1. 正向同步时记录 element_id -> (component_instance, params, type)
2. 反向同步时读取组件实例最新参数（如果引用仍有效）
3. 持久化参数到JSON文件（实例对象不可序列化，只存参数）
"""

import json
import os


class ComponentRegistry:
    """组件注册表 - 全局单例模式管理"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._registry = {}  # element_id -> {instance, params, component_type}
        self._file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "component_registry.json"
        )
        self._load_from_file()

    def register(self, element_id, component_instance, params, component_type):
        """注册一个新的组件映射"""
        self._registry[element_id] = {
            'instance': component_instance,
            'params': dict(params),
            'component_type': str(component_type),
        }
        self._save_to_file()

    def get(self, element_id):
        """获取指定元素的注册信息"""
        return self._registry.get(element_id)

    def get_all(self):
        """获取所有映射"""
        return list(self._registry.items())

    def clear(self):
        """清空所有映射"""
        self._registry.clear()
        self._save_to_file()

    def update_params_from_instance(self, element_id):
        """
        尝试从组件实例读取最新参数值。
        只有当参数确实发生变化时才返回True。
        """
        info = self._registry.get(element_id)
        if not info:
            return False
        inst = info.get('instance')
        if inst is None:
            return False
        try:
            old_params = dict(info['params'])
            new_params = {}
            for key in old_params:
                try:
                    val = inst[key]
                    if hasattr(val, 'value'):
                        new_params[key] = val.value
                    else:
                        new_params[key] = val
                except Exception:
                    pass
            # 检查是否有实质性变化（忽略微小浮点差异）
            changed = False
            for k, v in new_params.items():
                old_v = old_params.get(k)
                try:
                    if old_v is None or abs(float(v) - float(old_v)) > 1e-6:
                        changed = True
                        break
                except (TypeError, ValueError):
                    if str(v) != str(old_v):
                        changed = True
                        break
            if changed:
                info['params'].update(new_params)
                self._save_to_file()
                return True
            return False
        except Exception:
            return False

    def get_params(self, element_id):
        """获取指定元素的参数和组件类型"""
        info = self._registry.get(element_id)
        if not info:
            return None, None
        return dict(info.get('params', {})), info.get('component_type', '')

    def update_params(self, element_id, params):
        """手动更新参数（用于外部脚本读取后写回）"""
        if element_id in self._registry:
            self._registry[element_id]['params'].update(params)
            self._save_to_file()

    def _save_to_file(self):
        """持久化参数到JSON（实例对象不可序列化）"""
        serializable = {}
        for eid, info in self._registry.items():
            serializable[eid] = {
                'params': info.get('params', {}),
                'component_type': info.get('component_type', ''),
            }
        try:
            with open(self._file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_from_file(self):
        """从JSON文件恢复参数映射（无实例对象）"""
        if not os.path.exists(self._file_path):
            return
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            for eid, info in loaded.items():
                if eid not in self._registry:
                    self._registry[eid] = {
                        'instance': None,
                        'params': info.get('params', {}),
                        'component_type': info.get('component_type', ''),
                    }
        except Exception:
            pass


def get_registry():
    """获取全局唯一的ComponentRegistry实例"""
    return ComponentRegistry()


def infer_component_params_from_element(elem):
    """
    从画板元素的2D几何直接推断组件类型和参数。
    这样即使元素没有同步到BIMBase（component_type为空），
    也能使用面编辑功能。
    
    返回: (component_type, params_dict) 或 (None, None)
    """
    et = getattr(elem, 'element_type', '')
    if hasattr(et, 'name'):
        et_name = et.name.lower()
    else:
        et_name = str(et).lower()

    z_start = float(getattr(elem, 'z_start', 0))
    z_end = float(getattr(elem, 'z_end', 0))
    if z_end <= z_start:
        # 给一个默认高度
        z_end = z_start + 100

    if et_name == 'rectangle':
        x = float(getattr(elem, 'x', 0))
        y = float(getattr(elem, 'y', 0))
        w = float(getattr(elem, 'width', 100))
        h = float(getattr(elem, 'height', 100))
        return 'SweepBoxComponent', {
            'x': x, 'y': y,
            'length': w, 'width': h,
            'z_bottom': z_start, 'z_top': z_end,
        }

    if et_name == 'circle':
        cx = float(getattr(elem, 'cx', 0))
        cy = float(getattr(elem, 'cy', 0))
        r = float(getattr(elem, 'radius', 50))
        return 'Circle3DComponent', {
            'cx': cx, 'cy': cy, 'radius': r,
            'z_bottom': z_start, 'z_top': z_end,
        }

    if et_name == 'line':
        x1 = float(getattr(elem, 'x1', 0))
        y1 = float(getattr(elem, 'y1', 0))
        x2 = float(getattr(elem, 'x2', 100))
        y2 = float(getattr(elem, 'y2', 0))
        t = float(getattr(elem, 'thickness', 5))
        return 'Line3DComponent', {
            'x1': x1, 'y1': y1, 'z1': z_start,
            'x2': x2, 'y2': y2, 'z2': z_end,
            'radius': t,
        }

    if et_name == 'arc':
        cx = float(getattr(elem, 'cx', 0))
        cy = float(getattr(elem, 'cy', 0))
        r = float(getattr(elem, 'radius', 50))
        sa = float(getattr(elem, 'start_angle', 0))
        ea = float(getattr(elem, 'end_angle', 90))
        t = float(getattr(elem, 'thickness', 5))
        return 'Arc3DComponent', {
            'cx': cx, 'cy': cy, 'radius': r,
            'start_angle': sa, 'end_angle': ea,
            'z_bottom': z_start, 'z_top': z_end,
            'thickness': t,
        }

    if et_name == 'ellipse':
        cx = float(getattr(elem, 'cx', 0))
        cy = float(getattr(elem, 'cy', 0))
        rx = float(getattr(elem, 'rx', 50))
        ry = float(getattr(elem, 'ry', 30))
        return 'Ellipse3DComponent', {
            'cx': cx, 'cy': cy, 'rx': rx, 'ry': ry,
            'z_bottom': z_start, 'z_top': z_end,
        }

    if et_name == 'point':
        x = float(getattr(elem, 'x', 0))
        y = float(getattr(elem, 'y', 0))
        t = float(getattr(elem, 'thickness', 5))
        return 'Point3DComponent', {
            'x': x, 'y': y, 'z': z_start,
            'radius': t,
        }

    if et_name == 'polygon':
        pts = getattr(elem, 'points', [])
        params = {'z_bottom': z_start, 'z_top': z_end}
        for i, (px, py) in enumerate(pts):
            params[f'px{i}'] = float(px)
            params[f'py{i}'] = float(py)
        params['point_count'] = len(pts)
        return 'Polygon3DComponent', params

    if et_name == 'polyline':
        pts = getattr(elem, 'points', [])
        params = {'thickness': float(getattr(elem, 'thickness', 5))}
        for i, (px, py) in enumerate(pts):
            params[f'px{i}'] = float(px)
            params[f'py{i}'] = float(py)
            params[f'pz{i}'] = z_start
        params['point_count'] = len(pts)
        return 'Polyline3DComponent', params

    return None, None


# ========== 组件参数 ↔ 元素几何 映射 ==========

PARAM_MAP_RULES = {
    'SweepBoxComponent': {
        'x': ('x', 'direct'),
        'y': ('y', 'direct'),
        'length': ('width', 'direct'),
        'width': ('height', 'direct'),
        'z_bottom': ('z_start', 'direct'),
        'z_top': ('z_end', 'direct'),
    },
    'Circle3DComponent': {
        'cx': ('cx', 'direct'),
        'cy': ('cy', 'direct'),
        'radius': ('radius', 'direct'),
        'z_bottom': ('z_start', 'direct'),
        'z_top': ('z_end', 'direct'),
    },
    'Line3DComponent': {
        'x1': ('x1', 'direct'),
        'y1': ('y1', 'direct'),
        'z1': ('z_start', 'direct'),
        'x2': ('x2', 'direct'),
        'y2': ('y2', 'direct'),
        'z2': ('z_end', 'direct'),
        'radius': ('thickness', 'direct'),
    },
    'Arc3DComponent': {
        'cx': ('cx', 'direct'),
        'cy': ('cy', 'direct'),
        'radius': ('radius', 'direct'),
        'z_bottom': ('z_start', 'direct'),
        'z_top': ('z_end', 'direct'),
    },
    'Ellipse3DComponent': {
        'cx': ('cx', 'direct'),
        'cy': ('cy', 'direct'),
        'rx': ('rx', 'direct'),
        'ry': ('ry', 'direct'),
        'z_bottom': ('z_start', 'direct'),
        'z_top': ('z_end', 'direct'),
    },
    'Point3DComponent': {
        'x': ('x', 'direct'),
        'y': ('y', 'direct'),
        'z': ('z_start', 'direct'),
        'radius': ('size', 'direct'),
    },
    'Polygon3DComponent': {
        'z_bottom': ('z_start', 'direct'),
        'z_top': ('z_end', 'direct'),
        # px0/py0, px1/py1... 映射到 points 列表
    },
    'Polyline3DComponent': {
        # px0/py0/pz0... 映射到 points 列表
    },
    '直角三棱柱': {
        '直角边1': ('width', 'direct'),
        '直角边2': ('height', 'direct'),
        '高度': ('thickness', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
    '圆柱': {
        '半径': ('radius', 'direct'),
        '高度': ('thickness', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
    '正方体': {
        '边长': ('width', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
    '长方体': {
        '长度': ('width', 'direct'),
        '宽度': ('height', 'direct'),
        '高度': ('thickness', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
    '球体': {
        '半径': ('radius', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
    '引桥桥墩': {
        '盖梁总长': ('width', 'direct'),
        '盖梁宽': ('height', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
    '索缆锚锭': {
        '承台长度': ('width', 'direct'),
        '承台宽度': ('height', 'direct'),
        'z_bottom': ('z_start', 'direct'),
    },
}


def apply_component_params_to_element(elem, params, component_type):
    """
    将组件参数应用到元素的2D几何属性上。
    返回成功应用的参数数量。
    """
    rules = PARAM_MAP_RULES.get(component_type)
    if not rules:
        return 0

    applied = 0
    for param_key, (elem_attr, mode) in rules.items():
        if param_key not in params:
            continue
        val = params[param_key]
        try:
            if hasattr(elem, elem_attr):
                setattr(elem, elem_attr, float(val))
                applied += 1
        except Exception:
            pass

    # Polygon3DComponent / Polyline3DComponent 特殊处理 points
    if component_type in ('Polygon3DComponent', 'Polyline3DComponent'):
        point_count = params.get('point_count', 0)
        new_points = []
        for i in range(point_count):
            px = params.get(f'px{i}')
            py = params.get(f'py{i}')
            if px is not None and py is not None:
                new_points.append((float(px), float(py)))
        if new_points and hasattr(elem, 'points'):
            elem.points = new_points
            applied += 1

    # 直角三棱柱 特殊处理：更新直角三角形 points
    if component_type == '直角三棱柱' and hasattr(elem, 'points'):
        a = float(params.get('直角边1', 100))
        b = float(params.get('直角边2', 100))
        new_points = [(0, 0), (a, 0), (0, b)]
        if elem.points != new_points:
            elem.points = new_points
            applied += 1
        z_bottom = float(params.get('z_bottom', 0))
        h = float(params.get('高度', 200))
        if hasattr(elem, 'z_start'):
            elem.z_start = z_bottom
        if hasattr(elem, 'z_end'):
            elem.z_end = z_bottom + h
        applied += 1

    # 圆柱 特殊处理：半径→圆形，高度→z_end
    if component_type == '圆柱':
        r = float(params.get('半径', 50))
        h = float(params.get('高度', 100))
        if hasattr(elem, 'radius'):
            elem.radius = r
        z_bottom = float(params.get('z_bottom', 0))
        if hasattr(elem, 'z_start'):
            elem.z_start = z_bottom
        if hasattr(elem, 'z_end'):
            elem.z_end = z_bottom + h
        applied += 1

    # 球体 特殊处理：半径→圆，z→直径
    if component_type == '球体':
        r = float(params.get('半径', 50))
        if hasattr(elem, 'radius'):
            elem.radius = r
        z_bottom = float(params.get('z_bottom', 0))
        if hasattr(elem, 'z_start'):
            elem.z_start = z_bottom
        if hasattr(elem, 'z_end'):
            elem.z_end = z_bottom + 2 * r
        applied += 1

    # 正方体 特殊处理：边长→正方形，z→高度
    if component_type == '正方体':
        a = float(params.get('边长', 100))
        if hasattr(elem, 'width'):
            elem.width = a
        if hasattr(elem, 'height'):
            elem.height = a
        z_bottom = float(params.get('z_bottom', 0))
        if hasattr(elem, 'z_start'):
            elem.z_start = z_bottom
        if hasattr(elem, 'z_end'):
            elem.z_end = z_bottom + a
        applied += 1

    # 长方体 特殊处理：长/宽/高
    if component_type == '长方体':
        L = float(params.get('长度', 200))
        W = float(params.get('宽度', 100))
        H = float(params.get('高度', 150))
        if hasattr(elem, 'width'):
            elem.width = L
        if hasattr(elem, 'height'):
            elem.height = W
        z_bottom = float(params.get('z_bottom', 0))
        if hasattr(elem, 'z_start'):
            elem.z_start = z_bottom
        if hasattr(elem, 'z_end'):
            elem.z_end = z_bottom + H
        applied += 1

    # 引桥桥墩 特殊处理：盖梁总长/盖梁宽/墩高/盖梁总高
    if component_type == '引桥桥墩':
        L = float(params.get('盖梁总长', 1930))
        W = float(params.get('盖梁宽', 300))
        col_h = float(params.get('墩高', 1200))
        cap_h = float(params.get('盖梁总高', 300))
        if hasattr(elem, 'width'):
            elem.width = L
        if hasattr(elem, 'height'):
            elem.height = W
        z_bottom = float(params.get('z_bottom', 0))
        if hasattr(elem, 'z_start'):
            elem.z_start = z_bottom
        if hasattr(elem, 'z_end'):
            elem.z_end = z_bottom + col_h + cap_h
        applied += 1

    # 统一更新 3D 高度（非矩形元素）
    if elem.__class__.__name__ != 'RectangleElement':
        if hasattr(elem, 'z_end') and hasattr(elem, 'z_start'):
            elem.height = elem.z_end - elem.z_start

    # 同步更新 component_params，确保后续面生成使用最新参数
    if hasattr(elem, 'component_params') and elem.component_params is not None:
        def _is_clean_value(v):
            return isinstance(v, (int, float, str, bool, type(None)))
        filtered = {k: v for k, v in params.items()
                    if not k.startswith('_') and _is_clean_value(v)}
        elem.component_params = filtered

    return applied


def create_element_from_params(params, component_type):
    """
    根据BIMBase组件参数创建对应的画板2D元素。
    用于反向同步时，将BIMBase中新放置的组件导入画板。
    
    返回: 新建的元素实例，或 None（不支持该类型时）
    """
    try:
        if component_type == 'SweepBoxComponent':
            from geometry.elements import RectangleElement
            x = float(params.get('x', 0))
            y = float(params.get('y', 0))
            length = float(params.get('length', 100))
            width = float(params.get('width', 100))
            elem = RectangleElement(x, y, length, width)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = float(params.get('z_top', 100))
            return elem

        elif component_type == 'Circle3DComponent':
            from geometry.elements import CircleElement
            cx = float(params.get('cx', 0))
            cy = float(params.get('cy', 0))
            radius = float(params.get('radius', 50))
            elem = CircleElement(cx, cy, radius)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = float(params.get('z_top', 100))
            return elem

        elif component_type == 'Line3DComponent':
            from geometry.elements import LineElement
            x1 = float(params.get('x1', 0))
            y1 = float(params.get('y1', 0))
            x2 = float(params.get('x2', 100))
            y2 = float(params.get('y2', 0))
            elem = LineElement(x1, y1, x2, y2)
            elem.z_start = float(params.get('z1', 0))
            elem.z_end = float(params.get('z2', 0))
            elem.thickness = float(params.get('radius', 5))
            return elem

        elif component_type == 'Arc3DComponent':
            from geometry.elements import ArcElement
            cx = float(params.get('cx', 0))
            cy = float(params.get('cy', 0))
            radius = float(params.get('radius', 50))
            sa = float(params.get('start_angle', 0))
            ea = float(params.get('end_angle', 90))
            elem = ArcElement(cx, cy, radius, sa, ea)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = float(params.get('z_top', 100))
            elem.thickness = float(params.get('thickness', 5))
            return elem

        elif component_type == 'Ellipse3DComponent':
            from geometry.elements import EllipseElement
            cx = float(params.get('cx', 0))
            cy = float(params.get('cy', 0))
            rx = float(params.get('rx', 50))
            ry = float(params.get('ry', 30))
            elem = EllipseElement(cx, cy, rx, ry)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = float(params.get('z_top', 100))
            return elem

        elif component_type == 'Point3DComponent':
            from geometry.elements import PointElement
            x = float(params.get('x', 0))
            y = float(params.get('y', 0))
            elem = PointElement(x, y)
            elem.z_start = float(params.get('z', 0))
            elem.thickness = float(params.get('radius', 5))
            return elem

        elif component_type == 'Polygon3DComponent':
            from geometry.elements import PolylineElement
            point_count = int(params.get('point_count', 0))
            pts = []
            for i in range(point_count):
                px = params.get(f'px{i}')
                py = params.get(f'py{i}')
                if px is not None and py is not None:
                    pts.append((float(px), float(py)))
            if len(pts) < 3:
                pts = [[0, 0], [100, 0], [100, 100]]
            elem = PolylineElement(pts, closed=True)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = float(params.get('z_top', 100))
            return elem

        elif component_type == 'Polyline3DComponent':
            from geometry.elements import PolylineElement
            point_count = int(params.get('point_count', 0))
            pts = []
            for i in range(point_count):
                px = params.get(f'px{i}')
                py = params.get(f'py{i}')
                if px is not None and py is not None:
                    pts.append((float(px), float(py)))
            if len(pts) < 2:
                pts = [[0, 0], [100, 0]]
            elem = PolylineElement(pts, closed=False)
            elem.thickness = float(params.get('thickness', 5))
            return elem

        elif component_type == '直角三棱柱':
            from geometry.elements import PolylineElement
            a = float(params.get('直角边1', 100))
            b = float(params.get('直角边2', 100))
            pts = [(0, 0), (a, 0), (0, b)]
            elem = PolylineElement(pts, closed=True)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + float(params.get('高度', 200))
            return elem

        elif component_type == '圆柱':
            from geometry.elements import CircleElement
            cx = float(params.get('cx', 0))
            cy = float(params.get('cy', 0))
            r = float(params.get('半径', 50))
            elem = CircleElement(cx, cy, r)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + float(params.get('高度', 100))
            return elem

        elif component_type == '正方体':
            from geometry.elements import RectangleElement
            x = float(params.get('x', 0))
            y = float(params.get('y', 0))
            a = float(params.get('边长', 100))
            elem = RectangleElement(x, y, a, a)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + a
            return elem

        elif component_type == '长方体':
            from geometry.elements import RectangleElement
            x = float(params.get('x', 0))
            y = float(params.get('y', 0))
            L = float(params.get('长度', 200))
            W = float(params.get('宽度', 100))
            elem = RectangleElement(x, y, L, W)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + float(params.get('高度', 150))
            return elem

        elif component_type == '球体':
            from geometry.elements import CircleElement
            cx = float(params.get('cx', params.get('x', 0)))
            cy = float(params.get('cy', params.get('y', 0)))
            r = float(params.get('半径', 50))
            elem = CircleElement(cx, cy, r)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + 2 * r
            return elem

        elif component_type == '引桥桥墩':
            from geometry.elements import RectangleElement
            # x,y 按几何中心处理
            cx = float(params.get('x', 0))
            cy = float(params.get('y', 0))
            L = float(params.get('盖梁总长', 1930))
            W = float(params.get('盖梁宽', 300))
            elem = RectangleElement(cx - L / 2, cy - W / 2, L, W)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + float(params.get('墩高', 1200)) + float(params.get('盖梁总高', 300))
            return elem

        elif component_type == '索缆锚锭':
            from geometry.elements import RectangleElement
            cx = float(params.get('x', 0))
            cy = float(params.get('y', 0))
            CL = float(params.get('承台长度', 5680))
            CW = float(params.get('承台宽度', 1600))
            elem = RectangleElement(cx - CL / 2, cy - CW / 2, CL, CW)
            elem.z_start = float(params.get('z_bottom', 0))
            elem.z_end = elem.z_start + float(params.get('底柱高度', 1000)) + float(params.get('承台高度', 400)) + float(params.get('锚块总高', 2039))
            return elem

    except Exception:
        pass

    return None
