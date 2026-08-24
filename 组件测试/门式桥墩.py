# -*- coding: utf-8 -*-
"""
门式桥墩参数化组件（精简参数版）

参考：数据参考源/门式桥墩/门式桥墩.dwg

保留用户可交互调整的核心外轮廓参数，其余细部尺寸固定为图纸默认值。

结构：盖梁 + 垫石×2 + 双根变截面空心八边形墩柱 + 系梁
坐标系（BIMBase）：X 横向（盖梁长度方向），Y 深度，Z 高度；原点在柱底中心、地面处
"""

from pyp3d import *


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


class 门式桥墩(Component):
    """门式桥墩：盖梁（含垫石）+ 双根变截面空心八边形墩柱 + 系梁"""

    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数（单位 cm，在属性面板可交互修改）
        self['盖梁总长'] = Attr(4700.0, obvious=True)
        self['盖梁总高'] = Attr(400.0, obvious=True)
        self['盖梁宽'] = Attr(1000.0, obvious=True)
        self['墩高'] = Attr(5000.0, obvious=True)
        self['墩柱间距'] = Attr(3500.0, obvious=True)   # 两柱中心间距
        self['柱顶宽'] = Attr(1200.0, obvious=True)     # X 向
        self['柱底宽'] = Attr(1400.0, obvious=True)     # X 向
        self['柱顶厚'] = Attr(1000.0, obvious=True)     # Y 向
        self['柱底厚'] = Attr(1200.0, obvious=True)     # Y 向
        self['系梁根数'] = Attr(1, obvious=True)
        self['门式桥墩'] = Attr(None, show=True)
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
        self.replace()

    @export
    def replace(self):
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

        # 细部尺寸固定为图纸默认值（cm）
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

        geom = Combine(*parts)
        try:
            c = self['颜色'] if '颜色' in self else None
            if c:
                vals = [float(x) for x in str(c).split(',') if x.strip()]
                if len(vals) >= 3:
                    geom = geom.color(*vals)
        except Exception:
            pass
        self['门式桥墩'] = geom


if __name__ == "__main__":
    FinalGeometry = 门式桥墩()
    place(FinalGeometry)
