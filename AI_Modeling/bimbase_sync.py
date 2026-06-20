# -*- coding: utf-8 -*-
"""
AI建模插件 - 参数化组件定义（供 place/place_to DependentFile 读取）
所有组件类必须在此文件中定义，BIMBase 才能通过 sys.argv[0] 找到它们
"""

import math
import sys
import os
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
