
# -*- coding: utf-8 -*-
"""
自动生成的BIMBase参数化组件脚本
在VSCode中按F5运行，然后在BIMBase三维视图中点击放置位置
"""

from pyp3d import *
import math

# ============ 兼容性处理 ============
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

# ============ 组件类 ============


class Line3DComponent(Component):
    """参数化线段"""
    def __init__(self, x1=0, y1=0, z1=0, x2=100, y2=100, z2=0, radius=5):
        super().__init__()
        self['x1'] = Attr(float(x1), show=True)
        self['y1'] = Attr(float(y1), show=True)
        self['z1'] = Attr(float(z1), show=True)
        self['x2'] = Attr(float(x2), show=True)
        self['y2'] = Attr(float(y2), show=True)
        self['z2'] = Attr(float(z2), show=True)
        self['radius'] = Attr(float(radius), show=True)
        self['线段'] = Attr(None, show=True)
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
    """参数化拉伸体"""
    def __init__(self, x=0, y=0, z_bottom=0, z_top=100, 
                 length=100, width=100, chamfer=0):
        super().__init__()
        self['x'] = Attr(float(x), show=True)
        self['y'] = Attr(float(y), show=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True)
        self['z_top'] = Attr(float(z_top), show=True)
        self['length'] = Attr(float(length), show=True)
        self['width'] = Attr(float(width), show=True)
        self['chamfer'] = Attr(float(chamfer), show=True)
        self['拉伸体'] = Attr(None, show=True)
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
            section = Section(
                Vec2(x, y), Vec2(x+L, y),
                Vec2(x+L, y+W), Vec2(x, y+W)
            )
        path = Line(Vec3(0, 0, zb), Vec3(0, 0, zt))
        self['拉伸体'] = Sweep(section, path)


class Circle3DComponent(Component):
    """参数化圆柱"""
    def __init__(self, cx=0, cy=0, z_bottom=0, z_top=100, radius=50):
        super().__init__()
        self['cx'] = Attr(float(cx), show=True)
        self['cy'] = Attr(float(cy), show=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True)
        self['z_top'] = Attr(float(z_top), show=True)
        self['radius'] = Attr(float(radius), show=True)
        self['圆柱'] = Attr(None, show=True)
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
    """参数化圆弧"""
    def __init__(self, cx=0, cy=0, radius=50, start_angle=0, end_angle=90,
                 z_bottom=0, z_top=100, thickness=5):
        super().__init__()
        self['cx'] = Attr(float(cx), show=True)
        self['cy'] = Attr(float(cy), show=True)
        self['radius'] = Attr(float(radius), show=True)
        self['start_angle'] = Attr(float(start_angle), show=True)
        self['end_angle'] = Attr(float(end_angle), show=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True)
        self['z_top'] = Attr(float(z_top), show=True)
        self['thickness'] = Attr(float(thickness), show=True)
        self['圆弧'] = Attr(None, show=True)
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
        except:
            section = _circle_section(t / 2)
            path = Line(Vec3(cx, cy, zb), Vec3(cx, cy, zt))
            self['圆弧'] = Sweep(section, path)


class Ellipse3DComponent(Component):
    """参数化椭圆柱"""
    def __init__(self, cx=0, cy=0, rx=50, ry=30, z_bottom=0, z_top=100):
        super().__init__()
        self['cx'] = Attr(float(cx), show=True)
        self['cy'] = Attr(float(cy), show=True)
        self['rx'] = Attr(float(rx), show=True)
        self['ry'] = Attr(float(ry), show=True)
        self['z_bottom'] = Attr(float(z_bottom), show=True)
        self['z_top'] = Attr(float(z_top), show=True)
        self['椭圆柱'] = Attr(None, show=True)
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
        except:
            path = Line(Vec3(cx, cy, zb), Vec3(cx, cy, zt))
            self['椭圆柱'] = Sweep(_circle_section(max(rx, ry)), path)


class Point3DComponent(Component):
    """参数化点"""
    def __init__(self, x=0, y=0, z=0, radius=5):
        super().__init__()
        self['x'] = Attr(float(x), show=True)
        self['y'] = Attr(float(y), show=True)
        self['z'] = Attr(float(z), show=True)
        self['radius'] = Attr(float(radius), show=True)
        self['点'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        x, y, z = self['x'], self['y'], self['z']
        r = max(self['radius'], 1)
        self['点'] = translate(x, y, z) * scale(r*2, r*2, r*2) * Cube()


# ============ 主入口 ============
if __name__ == "__main__":

    print("="*50)
    print("CADBoard -> BIMBase 同步脚本")
    print("="*50)
    print(f"共 1 个元素")
    print("请在BIMBase三维视图中逐个点击放置位置")
    print("="*50)
    print()

    # --- 元素 1 ---

    # 矩形: (134.5,134.2) 114.0x20.0 H=100.0
    comp = SweepBoxComponent(134.4981412639405, 134.22490706319704, 0.0, 100.0, 113.97769516728624, 20.0)
    FinalGeometry = comp
    place(FinalGeometry)



    print("\n全部放置完成！")
