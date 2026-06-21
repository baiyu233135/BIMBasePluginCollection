# -*- coding: utf-8 -*-
"""
索缆锚锭参数化组件

可调参数（单位：mm）：
- 锚碇高度 : 锚碇主体总高度
- 锚碇底宽 : 锚碇底部宽度
- 锚碇顶宽 : 锚碇顶部宽度
- 承台宽   : 承台宽度
- 承台高   : 承台高度
- 索孔排数 : 索孔沿高度方向排数
- 每排索孔数 : 每排索孔数量
- 索孔直径 : 索孔直径
- 索孔间距 : 索孔中心间距

参考：数据参考源/索缆锚锭，引桥桥墩.pdf 第1页
"""

from pyp3d import *

class 索缆锚锭(Component):
    """索缆锚锭：上窄下宽的锚碇主体 + 底部承台 + 索孔"""

    def __init__(self):
        Component.__init__(self)
        self['锚碇高度'] = Attr(2000.0, obvious=True)
        self['锚碇底宽'] = Attr(2200.0, obvious=True)
        self['锚碇顶宽'] = Attr(1000.0, obvious=True)
        self['承台宽'] = Attr(1600.0, obvious=True)
        self['承台高'] = Attr(850.0, obvious=True)
        self['索孔排数'] = Attr(2, obvious=True)
        self['每排索孔数'] = Attr(4, obvious=True)
        self['索孔直径'] = Attr(200.0, obvious=True)
        self['索孔间距'] = Attr(200.0, obvious=True)
        self['索缆锚锭'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        H = self['锚碇高度']
        B_bottom = self['锚碇底宽']
        B_top = self['锚碇顶宽']
        base_w = self['承台宽']
        base_h = self['承台高']
        hole_rows = int(self['索孔排数'])
        hole_cols = int(self['每排索孔数'])
        hole_d = self['索孔直径']
        hole_s = self['索孔间距']

        # 锚碇主体：梯形截面，沿 Y 轴拉伸
        section = Section(
            Vec2(-B_bottom / 2, 0),
            Vec2(B_bottom / 2, 0),
            Vec2(B_top / 2, H),
            Vec2(-B_top / 2, H)
        )
        path = Line(Vec3(0, 0, 0), Vec3(0, 0, H))
        anchor_body = Sweep(section, path)

        # 承台
        base = translate(0, 0, -base_h) * scale(base_w, base_w, base_h) * Cube()

        # 索孔：用红色小圆柱表示（不做布尔减，避免不稳定）
        hole_r = hole_d / 2
        holes = None
        start_x = -(hole_cols - 1) * hole_s / 2
        start_z = H / 2 - (hole_rows - 1) * hole_s / 2
        for r in range(hole_rows):
            z = start_z + r * hole_s
            for c in range(hole_cols):
                x = start_x + c * hole_s
                h_cyl = Cylinder(hole_r, B_top + 100)
                h_cyl = translate(x, -B_top / 2 - 50, z) * h_cyl
                h_cyl.color(1, 0, 0)
                if holes is None:
                    holes = h_cyl
                else:
                    holes = holes + h_cyl

        if holes is not None:
            self['索缆锚锭'] = anchor_body + base + holes
        else:
            self['索缆锚锭'] = anchor_body + base


if __name__ == "__main__":
    FinalGeometry = 索缆锚锭()
    place(FinalGeometry)
