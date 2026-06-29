# -*- coding: utf-8 -*-
"""
引桥桥墩参数化组件（精简参数版）

参考：数据参考源/引桥桥墩/引桥桥墩.dwg

保留用户可交互调整的核心外轮廓参数，其余细部尺寸固定为图纸默认值。

坐标系（BIMBase）：X 横向，Y 深度，Z 高度
"""

from pyp3d import *


class 引桥桥墩(Component):
    """引桥桥墩：带斜边和凸起的盖梁 + 双墩柱 + 多根系梁"""

    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数（在属性面板可交互修改）
        self['盖梁总长'] = Attr(1930.0, obvious=True)
        self['盖梁总高'] = Attr(300.0, obvious=True)
        self['盖梁宽'] = Attr(300.0, obvious=True)
        self['墩柱直径'] = Attr(250.0, obvious=True)
        self['墩柱间距'] = Attr(1140.0, obvious=True)
        self['墩高'] = Attr(1200.0, obvious=True)
        self['系梁根数'] = Attr(2, obvious=True)
        self['引桥桥墩'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        cap_l = self['盖梁总长']
        cap_h = self['盖梁总高']
        cap_w = self['盖梁宽']
        col_d = self['墩柱直径']
        col_s = self['墩柱间距']
        col_h = self['墩高']
        tie_n = int(self['系梁根数'])

        # 细部尺寸固定为图纸默认值
        boss_w = 30.0
        boss_h = 50.0
        cap_bottom_w = 1390.0
        chamfer_h = 120.0
        tie_w = 200.0
        tie_h = 200.0
        tie_start = 200.0
        tie_step = 500.0
        # 系梁长随墩柱间距自动适配，保证与两圆柱墩柱相连接
        tie_l = max(col_s - col_d, 100.0)

        half_l = cap_l / 2
        half_bottom = cap_bottom_w / 2
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
        section = rotate(Vec3(1, 0, 0), 0.5 * pi) * (outer - inner)
        path = Line(Vec3(0, -cap_w / 2, 0), Vec3(0, cap_w / 2, 0))
        cap = translate(0, 0, col_h) * Sweep(section, path)

        # 墩柱（2根，圆柱）
        col_r = col_d / 2
        col1 = translate(-col_s / 2, 0, col_h / 2) * Cone(Vec3(0, 0, -col_h / 2), Vec3(0, 0, col_h / 2), col_r, col_r)
        col2 = translate(col_s / 2, 0, col_h / 2) * Cone(Vec3(0, 0, -col_h / 2), Vec3(0, 0, col_h / 2), col_r, col_r)

        # 系梁
        ties = None
        if tie_n > 0 and col_h > 0:
            for i in range(tie_n):
                z_top = col_h - tie_start - i * tie_step
                z = z_top - tie_h / 2
                if z < 0:
                    z = 0
                tie = translate(0, 0, z + tie_h / 2) * Cone(Vec3(-tie_l / 2, 0, 0), Vec3(tie_l / 2, 0, 0), tie_h / 2, tie_h / 2)
                if ties is None:
                    ties = tie
                else:
                    ties = Combine(ties, tie)

        parts = [cap, col1, col2]
        if ties is not None:
            parts.append(ties)
        self['引桥桥墩'] = Combine(*parts)


if __name__ == "__main__":
    FinalGeometry = 引桥桥墩()
    place(FinalGeometry)
