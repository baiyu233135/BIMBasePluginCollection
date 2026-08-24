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
        Sweep, Cube, Sphere, Cone, Loft,
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
    class Loft:
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


def _apply_color_attr(comp, geom):
    """若组件带 '颜色' 属性（"r,g,b[,a]" 字符串，0~1），对几何整体上色后返回；否则原样返回。
    在 replace() 末尾调用，保证任何参数重建后颜色仍然保持（6面统一色）。
    注意：pyp3d 的 Attr 只能存标量/字符串，颜色必须以字符串形式存储（元组无法序列化）。"""
    try:
        c = comp['颜色'] if '颜色' in comp else None
        if not c:
            return geom
        if isinstance(c, str):
            vals = [float(x) for x in c.split(',') if x.strip()]
        else:
            vals = [float(v) for v in c]
        if len(vals) >= 3:
            return geom.color(*vals)
    except Exception as e:
        _log(f"_apply_color_attr failed: {e}")
    return geom


class CylinderComponent(Component):
    """圆柱组件 - 几何体出生在原点，由 place_to 负责定位"""
    def __init__(self, radius=100, height=200, ox=0, oy=0, oz=0):
        super().__init__()
        self['半径'] = Attr(float(radius), show=True, obvious=True)
        self['高度'] = Attr(float(height), show=True, obvious=True)
        self['偏移X'] = Attr(float(ox), show=False)
        self['偏移Y'] = Attr(float(oy), show=False)
        self['偏移Z'] = Attr(float(oz), show=False)
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
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
        self['圆柱'] = _apply_color_attr(self, Sweep(section, path))


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
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
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
        self['长方体'] = _apply_color_attr(self, Sweep(section, path))


class CubeComponent(Component):
    """正方体组件 - 几何体出生在原点，由 place_to 负责定位"""
    def __init__(self, size=100, ox=0, oy=0, oz=0):
        super().__init__()
        self['边长'] = Attr(float(size), show=True, obvious=True)
        self['偏移X'] = Attr(float(ox), show=False)
        self['偏移Y'] = Attr(float(oy), show=False)
        self['偏移Z'] = Attr(float(oz), show=False)
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
        self['正方体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        a = self['边长']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
        self['正方体'] = _apply_color_attr(self, translate(ox, oy, oz) * scale(a, a, a) * Cube())


class SphereComponent(Component):
    """球体组件 - 几何体出生在原点，由 place_to 负责定位"""
    def __init__(self, radius=100, ox=0, oy=0, oz=0):
        super().__init__()
        self['半径'] = Attr(float(radius), show=True, obvious=True)
        self['偏移X'] = Attr(float(ox), show=False)
        self['偏移Y'] = Attr(float(oy), show=False)
        self['偏移Z'] = Attr(float(oz), show=False)
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
        self['球体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        r = self['半径']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
        self['球体'] = _apply_color_attr(self, translate(ox, oy, oz) * scale(r, r, r) * Sphere())


class ConeComponent(Component):
    """圆锥组件 - 几何体出生在原点，由 place_to 负责定位"""
    def __init__(self, radius=100, height=200, ox=0, oy=0, oz=0):
        super().__init__()
        self['底面半径'] = Attr(float(radius), show=True, obvious=True)
        self['高度'] = Attr(float(height), show=True, obvious=True)
        self['偏移X'] = Attr(float(ox), show=False)
        self['偏移Y'] = Attr(float(oy), show=False)
        self['偏移Z'] = Attr(float(oz), show=False)
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
        self['圆锥'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        r = self['底面半径']
        h = self['高度']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0
        self['圆锥'] = _apply_color_attr(self, translate(ox, oy, oz) * scale(r, r, h) * Cone())


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
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
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
        self['直角三棱柱'] = _apply_color_attr(self, Sweep(section, path))


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
        # 整体颜色 (r,g,b,a)，None 表示不上色；replace() 末尾统一应用
        self['颜色'] = Attr(None, show=False)
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
            self['引桥桥墩'] = _apply_color_attr(self, Combine(*parts))
        except Exception as e:
            _log(f"  ApproachPierComponent.replace() error: {e}")
            self['引桥桥墩'] = Cube()


def _octagon_section(w, d, c):
    """XY 平面内的倒角八边形截面：宽 w（X），深 d（Y），倒角 c"""
    hw, hd = w / 2.0, d / 2.0
    c = min(c, hw, hd)
    return Section(
        Vec2(-hw + c, -hd), Vec2(hw - c, -hd),
        Vec2(hw, -hd + c), Vec2(hw, hd - c),
        Vec2(hw - c, hd), Vec2(-hw + c, hd),
        Vec2(-hw, hd - c), Vec2(-hw, -hd + c)
    )


def _rect_section(w, d):
    """XY 平面内的矩形截面：宽 w（X），深 d（Y）"""
    hw, hd = w / 2.0, d / 2.0
    return Section(
        Vec2(-hw, -hd), Vec2(hw, -hd), Vec2(hw, hd), Vec2(-hw, hd)
    )


class GatePierComponent(Component):
    """门式桥墩：盖梁（含垫石）+ 双根变截面空心八边形墩柱 + 系梁

    与 组件测试/门式桥墩.py 保持一致的精简参数与几何逻辑。
    坐标系：X 横向（盖梁长度方向），Y 深度，Z 高度；原点在柱底中心、地面处。
    注意：组件类必须定义在本文件（DependentFile）中，BIMBase 才能序列化/放置。
    """

    DEFAULT_PARAMS = {
        '盖梁总长': 4700.0,
        '盖梁总高': 400.0,
        '盖梁宽': 1000.0,
        '墩高': 5000.0,
        '墩柱间距': 3500.0,     # 两柱中心间距
        '柱顶宽': 1200.0,       # X 向
        '柱底宽': 1400.0,       # X 向
        '柱顶厚': 1000.0,       # Y 向
        '柱底厚': 1200.0,       # Y 向
        '系梁根数': 1,
    }

    def __init__(self, **kwargs):
        super().__init__()
        for k, v in self.DEFAULT_PARAMS.items():
            self[k] = Attr(float(v) if isinstance(v, (int, float)) else v, show=True, obvious=True)
        # 隐藏属性：坐标烘焙兜底时使用
        for k in ('偏移X', '偏移Y', '偏移Z'):
            self[k] = Attr(0.0, show=False)
        # 整体颜色 (r,g,b,a)，None 表示不上色；replace() 末尾统一应用
        self['颜色'] = Attr(None, show=False)
        # 允许外部传入参数覆盖默认值
        for k, v in kwargs.items():
            if k in self.DEFAULT_PARAMS or k in ('偏移X', '偏移Y', '偏移Z'):
                is_number = isinstance(v, (int, float))
                self[k] = Attr(float(v) if is_number and k != '系梁根数' else v,
                               show=(k in self.DEFAULT_PARAMS), obvious=(k in self.DEFAULT_PARAMS))
        self['门式桥墩'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            cap_l = self['盖梁总长']
            cap_h = self['盖梁总高']
            cap_w = self['盖梁宽']
            col_h = self['墩高']
            col_s = self['墩柱间距']
            top_w = self['柱顶宽']
            bot_w = self['柱底宽']
            top_d = self['柱顶厚']
            bot_d = self['柱底厚']
            tie_n = int(self['系梁根数'])
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

            # 细部尺寸固定为图纸默认值（与 组件测试/门式桥墩.py 一致）
            pad_l = 400.0       # 垫石平面边长
            pad_h = 80.0        # 垫石高
            wall = 300.0        # 空心柱壁厚
            chamfer = 300.0     # 八边形倒角
            tie_h = 400.0       # 系梁高
            tie_d = 400.0       # 系梁深（Y 向）
            tie_step = 1000.0   # 多根系梁时的竖向间距（顶到顶）

            parts = []

            # 盖梁：z 从 墩高 到 墩高+盖梁总高
            cap = translate(-cap_l / 2, -cap_w / 2, col_h) * scale(cap_l, cap_w, cap_h) * Cube()
            parts.append(cap)

            # 垫石×2：位于柱顶中心的盖梁顶面
            for sx in (-col_s / 2, col_s / 2):
                pad = translate(sx - pad_l / 2, -pad_l / 2, col_h + cap_h) * scale(pad_l, pad_l, pad_h) * Cube()
                parts.append(pad)

            # 墩柱×2：变截面空心八边形（底截面 -> 顶截面 Loft）
            outer_bot = _octagon_section(bot_w, bot_d, chamfer)
            outer_top = _octagon_section(top_w, top_d, chamfer)
            core_bot = _rect_section(max(bot_w - 2 * wall, 10.0), max(bot_d - 2 * wall, 10.0))
            core_top = _rect_section(max(top_w - 2 * wall, 10.0), max(top_d - 2 * wall, 10.0))
            for sx in (-col_s / 2, col_s / 2):
                outer = Loft(outer_bot, translate(0, 0, col_h) * outer_top)
                try:
                    # 空心：减去内腔（布尔运算不稳定时退化为实心柱）
                    core = Loft(core_bot, translate(0, 0, col_h) * core_top)
                    col = outer - core
                except Exception:
                    col = outer
                parts.append(translate(sx, 0, 0) * col)

            # 系梁：贴盖梁底向下均布，长度随柱身锥度自动适配（与两柱内侧面相接）
            if tie_n > 0 and col_h > 0:
                for i in range(tie_n):
                    z_top = col_h - i * tie_step
                    if z_top - tie_h < 0:
                        z_top = tie_h
                    zc = z_top - tie_h / 2
                    # 该高度处柱身 X 向宽度（线性插值）
                    w_at = bot_w + (top_w - bot_w) * (zc / col_h)
                    tie_l = max(col_s - w_at, 100.0)
                    tie = translate(-tie_l / 2, -tie_d / 2, z_top - tie_h) * scale(tie_l, tie_d, tie_h) * Cube()
                    parts.append(tie)

            geom = translate(ox, oy, oz) * Combine(*parts)
            self['门式桥墩'] = _apply_color_attr(self, geom)
        except Exception as e:
            _log(f"  GatePierComponent.replace() error: {e}")
            self['门式桥墩'] = Cube()


class PileFoundationComponent(Component):
    """承台及桩基：矩形承台 + 列×排圆柱桩阵列

    与 组件测试/承台及桩基.py 保持一致的精简参数与几何逻辑。
    坐标系：X 长向，Y 宽向，Z 高度；原点在承台底面中心，桩向下延伸。
    注意：组件类必须定义在本文件（DependentFile）中，BIMBase 才能序列化/放置。
    """

    DEFAULT_PARAMS = {
        '承台长': 5500.0,
        '承台宽': 2350.0,
        '承台高': 500.0,
        '桩径': 250.0,
        '桩长': 5000.0,
        '桩间距': 630.0,        # 桩中心间距
        '桩列数': 9,            # X 向桩数
        '桩排数': 4,            # Y 向桩数
    }

    def __init__(self, **kwargs):
        super().__init__()
        for k, v in self.DEFAULT_PARAMS.items():
            self[k] = Attr(float(v) if isinstance(v, (int, float)) else v, show=True, obvious=True)
        # 隐藏属性：坐标烘焙兜底时使用
        for k in ('偏移X', '偏移Y', '偏移Z'):
            self[k] = Attr(0.0, show=False)
        # 整体颜色 (r,g,b,a)，None 表示不上色；replace() 末尾统一应用
        self['颜色'] = Attr(None, show=False)
        # 允许外部传入参数覆盖默认值
        for k, v in kwargs.items():
            if k in self.DEFAULT_PARAMS or k in ('偏移X', '偏移Y', '偏移Z'):
                is_number = isinstance(v, (int, float))
                self[k] = Attr(float(v) if is_number and k not in ('桩列数', '桩排数') else v,
                               show=(k in self.DEFAULT_PARAMS), obvious=(k in self.DEFAULT_PARAMS))
        self['承台及桩基'] = Attr(None, show=True, obvious=True)
        self.replace()

    @export
    def replace(self):
        try:
            cap_l = self['承台长']
            cap_w = self['承台宽']
            cap_h = self['承台高']
            pile_d = self['桩径']
            pile_l = self['桩长']
            spacing = self['桩间距']
            n_col = max(int(self['桩列数']), 1)
            n_row = max(int(self['桩排数']), 1)
            ox = float(self['偏移X']) if '偏移X' in self else 0.0
            oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
            oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

            # 承台：z 从 0 到 承台高，中心在原点
            cap = translate(-cap_l / 2, -cap_w / 2, 0) * scale(cap_l, cap_w, cap_h) * Cube()

            # 桩阵列：桩顶伸入承台底（z=0），桩底 z=-桩长
            r = pile_d / 2
            x0 = -(n_col - 1) * spacing / 2
            y0 = -(n_row - 1) * spacing / 2
            piles = []
            for i in range(n_col):
                for j in range(n_row):
                    x = x0 + i * spacing
                    y = y0 + j * spacing
                    piles.append(Cone(Vec3(x, y, -pile_l), Vec3(x, y, 0), r, r))

            geom = translate(ox, oy, oz) * Combine(cap, *piles)
            self['承台及桩基'] = _apply_color_attr(self, geom)
        except Exception as e:
            _log(f"  PileFoundationComponent.replace() error: {e}")
            self['承台及桩基'] = Cube()
