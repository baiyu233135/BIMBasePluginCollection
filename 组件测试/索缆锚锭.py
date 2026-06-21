# -*- coding: utf-8 -*-
"""
索缆锚锭参数化组件

可调参数（单位：mm，与 PDF 图纸 cm 数值对应）：
- 锚碇高度 : 锚碇主体总高度
- 锚碇底宽 : 锚碇底部宽度（X 方向）
- 锚碇顶宽 : 锚碇顶部宽度（X 方向）
- 锚碇厚度 : 锚碇沿 Y 方向长度
- 承台长   : 承台 X 方向长度
- 承台宽   : 承台 Y 方向宽度
- 承台高   : 承台 Z 方向高度
- 索孔排数 : 索孔沿高度方向排数
- 每排索孔数 : 每排索孔数量
- 索孔直径 : 索孔直径
- 索孔水平间距 : 同排索孔中心间距
- 索孔竖向间距 : 排与排中心间距

参考：数据参考源/索缆锚锭，引桥桥墩.pdf 第1页（索缆锚锭构造图）
"""

from pyp3d import *

class 索缆锚锭(Component):
    """索缆锚锭：上窄下宽的锚碇主体 + 底部承台 + 索孔"""

    def __init__(self):
        Component.__init__(self)
        self['锚碇高度'] = Attr(2200.0, obvious=True)
        self['锚碇底宽'] = Attr(2200.0, obvious=True)
        self['锚碇顶宽'] = Attr(1000.0, obvious=True)
        self['锚碇厚度'] = Attr(1000.0, obvious=True)
        self['承台长'] = Attr(2200.0, obvious=True)
        self['承台宽'] = Attr(1600.0, obvious=True)
        self['承台高'] = Attr(850.0, obvious=True)
        self['索孔排数'] = Attr(2, obvious=True)
        self['每排索孔数'] = Attr(4, obvious=True)
        self['索孔直径'] = Attr(200.0, obvious=True)
        self['索孔水平间距'] = Attr(200.0, obvious=True)
        self['索孔竖向间距'] = Attr(200.0, obvious=True)
        self['索缆锚锭'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        H = self['锚碇高度']
        B_bottom = self['锚碇底宽']
        B_top = self['锚碇顶宽']
        T = self['锚碇厚度']
        base_l = self['承台长']
        base_w = self['承台宽']
        base_h = self['承台高']
        hole_rows = int(self['索孔排数'])
        hole_cols = int(self['每排索孔数'])
        hole_d = self['索孔直径']
        hole_sx = self['索孔水平间距']
        hole_sz = self['索孔竖向间距']

        # 锚碇主体：梯形截面在 XZ 平面，沿 Y 轴拉伸
        section = Section(
            Vec2(-B_bottom / 2, 0),
            Vec2(B_bottom / 2, 0),
            Vec2(B_top / 2, H),
            Vec2(-B_top / 2, H)
        )
        path = Line(Vec3(0, -T / 2, 0), Vec3(0, T / 2, 0))
        anchor_body = Sweep(section, path)

        # 承台：底部矩形，顶面与锚碇底面齐平（z=0）
        base = translate(-base_l / 2, -base_w / 2, -base_h) * scale(base_l, base_w, base_h) * Cube()

        # 索孔：沿 Y 轴贯穿锚碇主体的圆柱孔（用红色显示，便于识别）
        hole_r = hole_d / 2
        holes = None
        start_x = -(hole_cols - 1) * hole_sx / 2
        start_z = H / 2 - (hole_rows - 1) * hole_sz / 2
        for r in range(hole_rows):
            z = start_z + r * hole_sz
            for c in range(hole_cols):
                x = start_x + c * hole_sx
                h_cyl = Cone(Vec3(x, -T / 2 - 50, z), Vec3(x, T / 2 + 50, z), hole_r, hole_r)
                h_cyl.color(1, 0, 0)
                if holes is None:
                    holes = h_cyl
                else:
                    holes = Combine(holes, h_cyl)

        if holes is not None:
            self['索缆锚锭'] = Combine(anchor_body, base, holes)
        else:
            self['索缆锚锭'] = Combine(anchor_body, base)


if __name__ == "__main__":
    FinalGeometry = 索缆锚锭()
    place(FinalGeometry)
