# -*- coding: utf-8 -*-
"""
AI建模插件 - 参数化组件定义（供 place/place_to DependentFile 读取）
所有组件类必须在此文件中定义，BIMBase 才能通过 sys.argv[0] 找到它们
"""

import math
import sys
import os


def _log(msg):
    """调试日志：写入 AI_Modeling/ai_modeling_debug.log"""
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_modeling_debug.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        pass
# 关键：确保 AI_Modeling 目录在 sys.path 最前面，
# 这样 python_transformation_operation 等跨上下文调用时能找到本模块，
# 并避免 CADBoard 的 bimbase_sync.py 同名模块冲突。
_bimbase_sync_dir = os.path.dirname(os.path.abspath(__file__))
if _bimbase_sync_dir in sys.path:
    sys.path.remove(_bimbase_sync_dir)
sys.path.insert(0, _bimbase_sync_dir)

# pyp3d 导入（在 BIMBase 环境中可用）
try:
    from pyp3d import (
        Component, Attr, Line, Section,
        Sweep, Cube, Sphere, Cone,
        Vec2, Vec3, Point, scale, translate, rotation,
        rotate, Combine,
    )
except ImportError:
    # 独立运行时占位
    class Component:
        pass
    class Attr:
        def __init__(self, v, show=False, obvious=False):
            self.v = v
    class Line:
        pass
    class Section:
        pass
    class Sweep:
        pass
    class Cube:
        pass
    class Sphere:
        pass
    class Cone:
        pass
    class Vec2:
        def __init__(self, x, y):
            self.x, self.y = x, y
    class Vec3:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z
    class Point:
        pass
    def scale(*a):
        pass
    def translate(*a):
        pass
    def rotation(*a):
        pass
    def rotate(*a):
        pass
    def Combine(*a):
        pass

try:
    from pyp3d import export
except ImportError:
    def export(func):
        return func


def _circle_section(radius, segments=32):
    points = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        points.append(Vec2(radius * math.cos(angle), radius * math.sin(angle)))
    return Section(*points)


class CylinderComponent(Component):
    """圆柱组件 - 几何体出生在原点，由 place_to 负责定位"""
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
        r = self['半径']
        h = self['高度']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
        section = _circle_section(r)
        path = Line(Vec3(ox, oy, oz), Vec3(ox, oy, oz + h))
        self['圆柱'] = Sweep(section, path)


class BoxComponent(Component):
    """长方体组件 - 几何体出生在原点，由 place_to 负责定位"""
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
        L = self['长度']
        W = self['宽度']
        H = self['高度']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
        section = Section(Vec2(ox, oy), Vec2(ox + L, oy), Vec2(ox + L, oy + W), Vec2(ox, oy + W))
        path = Line(Vec3(0, 0, oz), Vec3(0, 0, oz + H))
        self['长方体'] = Sweep(section, path)


class CubeComponent(Component):
    """正方体组件 - 几何体出生在原点，由 place_to 负责定位"""
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


class SphereComponent(Component):
    """球体组件 - 几何体出生在原点，由 place_to 负责定位"""
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


class ConeComponent(Component):
    """圆锥组件 - 几何体出生在原点，由 place_to 负责定位"""
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
        r = self['底面半径']
        h = self['高度']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
        self['圆锥'] = translate(ox, oy, oz) * scale(r, r, h) * Cone()


class TriangularPrismComponent(Component):
    """直角三棱柱组件 - 几何体出生在原点，由 place_to 负责定位"""
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


class ApproachPierComponent(Component):
    """引桥桥墩：带斜边和凸起的盖梁 + 双墩柱 + 多根系梁

    与 组件测试/引桥桥墩.py 保持一致的精简参数与几何逻辑。
    移植自 CADBoard/bimbase_sync.py 的 ApproachPierComponent（已实测可用）。
    注意：组件类必须定义在本文件（DependentFile）中，BIMBase 才能序列化/放置。
    """

    DEFAULT_PARAMS = {
        '盖梁总长': 1930.0,
        '盖梁总高': 300.0,
        '盖梁宽': 300.0,
        '墩柱直径': 250.0,
        '墩柱间距': 1140.0,
        '墩高': 1200.0,
        '系梁根数': 2,
    }

    def __init__(self, **kwargs):
        super().__init__()
        for k, v in self.DEFAULT_PARAMS.items():
            self[k] = Attr(float(v) if isinstance(v, (int, float)) else v, show=True, obvious=True)
        # 隐藏属性：坐标烘焙兜底时使用
        for k in ('偏移X', '偏移Y', '偏移Z'):
            self[k] = Attr(0.0, show=False)
        # 允许外部传入参数覆盖默认值
        for k, v in kwargs.items():
            if k in self.DEFAULT_PARAMS or k in ('偏移X', '偏移Y', '偏移Z'):
                is_number = isinstance(v, (int, float))
                self[k] = Attr(float(v) if is_number and k != '系梁根数' else v,
                               show=(k in self.DEFAULT_PARAMS), obvious=(k in self.DEFAULT_PARAMS))
        self['引桥桥墩'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            cap_l = self['盖梁总长']
            cap_h = self['盖梁总高']
            cap_w = self['盖梁宽']
            col_d = self['墩柱直径']
            col_s = self['墩柱间距']
            col_h = self['墩高']
            tie_n = int(self['系梁根数'])
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

            # 细部尺寸固定为图纸默认值（与参考 DWG 一致）
            boss_w = 30.0
            boss_h = 50.0
            cap_bottom_w = 1390.0
            chamfer_h = 120.0
            tie_h = 200.0
            # 与参考 DWG 一致：上系梁顶面距柱顶 100，间距 500
            # 公式中 tie_start 包含 half tie_h，因此取 200 才能得到顶距 100
            tie_start = 200.0
            tie_step = 500.0
            # 系梁长随墩柱间距自动适配，保证与两圆柱墩柱相连接
            tie_l = max(col_s - col_d, 100.0)

            half_l = cap_l / 2.0
            half_bottom = cap_bottom_w / 2.0
            mid_h = cap_h - boss_h

            # 盖梁整体截面（含梯形台、矩形主体、顶部两端凸起），一次 Sweep 成型
            outer = Section(
                Vec2(-half_bottom, 0),
                Vec2(half_bottom, 0),
                Vec2(half_l, chamfer_h),
                Vec2(half_l, cap_h),
                Vec2(-half_l, cap_h),
                Vec2(-half_l, chamfer_h)
            )
            inner = Section(
                Vec2(-half_l + boss_w, mid_h),
                Vec2(half_l - boss_w, mid_h),
                Vec2(half_l - boss_w, cap_h),
                Vec2(-half_l + boss_w, cap_h)
            )
            path = Line(Vec3(0, -cap_w / 2, 0), Vec3(0, cap_w / 2, 0))
            try:
                section = rotate(Vec3(1, 0, 0), 0.5 * math.pi) * (outer - inner)
                cap = translate(ox, oy, oz + col_h) * Sweep(section, path)
            except Exception as e:
                _log(f"  ApproachPierComponent cap beam boolean difference failed, fallback to solid section: {e}")
                section = rotate(Vec3(1, 0, 0), 0.5 * math.pi) * outer
                cap = translate(ox, oy, oz + col_h) * Sweep(section, path)

            # 双墩柱（圆柱）
            col_r = col_d / 2.0
            col1 = translate(ox - col_s / 2, oy, oz + col_h / 2) * Cone(Vec3(0, 0, -col_h / 2), Vec3(0, 0, col_h / 2), col_r, col_r)
            col2 = translate(ox + col_s / 2, oy, oz + col_h / 2) * Cone(Vec3(0, 0, -col_h / 2), Vec3(0, 0, col_h / 2), col_r, col_r)

            # 系梁
            ties = None
            if tie_n > 0 and col_h > 0:
                for i in range(tie_n):
                    z_top = col_h - tie_start - i * tie_step
                    z = z_top - tie_h / 2
                    if z < 0:
                        z = 0
                    tie = translate(ox, oy, oz + z + tie_h / 2) * Cone(Vec3(-tie_l / 2, 0, 0), Vec3(tie_l / 2, 0, 0), tie_h / 2, tie_h / 2)
                    if ties is None:
                        ties = tie
                    else:
                        ties = Combine(ties, tie)

            parts = [cap, col1, col2]
            if ties is not None:
                parts.append(ties)
            self['引桥桥墩'] = Combine(*parts)
        except Exception as e:
            _log(f"  ApproachPierComponent.replace() error: {e}")
            self['引桥桥墩'] = Cube()
