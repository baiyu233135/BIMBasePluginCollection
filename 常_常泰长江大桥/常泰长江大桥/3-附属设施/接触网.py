# -*- coding: utf-8 -*-
"""
接触网 — 性能优化版

优化说明：
- 8 种圆形截面全部弃用 N=64 手工多边形 Section+Loft，改用解析圆锥 Cone
  （等半径即圆柱，弹簧节用两端不同半径的圆锥），由内核统一剖分，
  数据量从每截面 64 点×2 降为 2 个点 + 半径，且更光滑。
- 弹簧 10 节堆叠、电线杆整排复制改用 Array 实例化排布，替代逐个 + / Combine。
- 装配位置、可调参数与外观均不变（解析圆更光滑属视觉提升）。
"""
from pyp3d import *
import math


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 接触网(Component):
    def __init__(self):
        Component.__init__(self)
        self['电线杆半径'] = Attr(150,obvious = True)
        self['电线杆高'] = Attr(6000,obvious = True)
        self['电线杆间隔'] = Attr(50000,obvious = True)

        self['上柱半径'] = Attr(40,obvious = True)
        self['上柱高'] = Attr(800,obvious = True)

        self['侧柱半径'] = Attr(40,obvious = True) 
        self['侧柱长'] = Attr(1000,obvious = True)
        self['侧径长'] = Attr(900,obvious = True)

        self['侧三角长'] = Attr(1800,obvious = True)
        self['侧三角高'] = Attr(500,obvious = True)
        self['侧三角半径'] = Attr(40,obvious = True)

        self['绝缘子长'] = Attr(300,obvious = True)
        self['绝缘子短半径'] = Attr(50,obvious = True)
        self['绝缘子长半径'] = Attr(100,obvious = True)

        self['短管半径'] = Attr(5,obvious = False)
        self['短管长'] = Attr(320,obvious = False)

        self['电线长'] = Attr(400000,obvious = True)
        self['电线半径'] = Attr(10,obvious = True)

        self['接触网'] = Attr(None,show = True)

        self.replace()

    @export
    def replace(self):
        R1 = self['电线杆半径']
        R2 = self['上柱半径']
        R3 = self['侧柱半径']
        R4 = self['侧三角半径']
        R5 = self['绝缘子长半径']
        R6 = self['绝缘子短半径']
        R7 = self['电线半径']
        R8 = self['短管半径']

        down_column_high = self['电线杆高']
        up_column_high = self['上柱高']
        left_column_long = self['侧柱长']
        left = self['侧径长']
        # 侧柱侧挂点（绝缘子弹簧/电线）差值跟随侧柱长：挂点 = 侧柱长 + 侧径长 - 1000，
        # 默认参数下 1000 + 900 - 1000 = 900 与原几何一致；侧柱长增减多少挂点同步增减，
        # 与三角侧（杆、线同用侧三角长）的联动行为一致
        hang = max(left_column_long + left - 1000, 0)
        left_triangle_long = self['侧三角长']
        left_triangle_high = self['侧三角高']
        string_long = self['绝缘子长']
        short = self['短管长']
        line_long = self['电线长']
        x = self['电线杆间隔']

        # 主干、上柱（解析圆锥，替代 64 边形 Loft）
        down_column = Cone(Vec3(0, 0, 0), Vec3(0, 0, down_column_high), R1, R1)
        up_column = Cone(Vec3(0, 0, down_column_high),
                         Vec3(0, 0, down_column_high + up_column_high), R2, R2)

        # 弹簧单元：两节变径圆锥（矮-高 + 高-矮）
        seg = string_long / 20.0
        string_unit = Combine(
            Cone(Vec3(0, 0, 0), Vec3(0, 0, seg), R6, R5),
            trans(0, 0, seg) * Cone(Vec3(0, 0, 0), Vec3(0, 0, seg), R5, R6))
        # 弹簧：Array 实例化排布 10 节
        string = _arr(string_unit,
                      [Vec3(0, 0, i * string_long / 10.0) for i in range(10)])
        # 弹簧尾部短管
        string_vertical = Cone(Vec3(0, 0, 0), Vec3(0, 0, short + R3), R8, R8)
        string_left = Combine(string, string_vertical)
        string_1 = trans(0, -hang, down_column_high - R3 * 3 - short) * string_left
        string_2 = trans(0, left_triangle_long / 4, down_column_high - R4) * \
                   rotate(Vec3(1, 0, 0), -pi / 2) * string
        string_3 = trans(0, left_triangle_long / 4 - R1 - 50,
                         down_column_high - left_triangle_high - R4 + left_triangle_high / 4) * \
                   rotate(Vec3(1, 0, 0),
                          -pi / 2 + math.atan2(left_triangle_high, left_triangle_long)) * string
        string_all = Combine(string_1, string_2, string_3)

        # 侧柱（横担）
        left_column = trans(0, 0, down_column_high - R3 * 2) * \
                      rotate(Vec3(1, 0, 0), pi / 2) * \
                      Cone(Vec3(0, 0, 0), Vec3(0, 0, left_column_long + R1), R3, R3)

        # 侧三角（上、下两根斜杆）
        tri_len = math.sqrt(left_triangle_high ** 2 + left_triangle_long ** 2)
        triangle_down = trans(0, -R1 - 50, down_column_high - left_triangle_high - R4) * \
                        rotate(Vec3(1, 0, 0),
                               -pi / 2 + math.atan2(left_triangle_high, left_triangle_long)) * \
                        Cone(Vec3(0, 0, 0), Vec3(0, 0, tri_len), R4, R4)
        triangle_up = trans(0, 0, down_column_high - R4) * \
                      rotate(Vec3(1, 0, 0), -pi / 2) * \
                      Cone(Vec3(0, 0, 0), Vec3(0, 0, left_triangle_long), R4, R4)
        triangle = Combine(triangle_up, triangle_down)

        # 电线
        line = rotate(Vec3(0, 1, 0), pi / 2) * \
               Cone(Vec3(0, 0, 0), Vec3(0, 0, line_long), R7, R7)
        line1 = trans(0, left_triangle_long, down_column_high - R4) * line
        line2 = trans(0, -R1 - 50, down_column_high - left_triangle_high - R4) * line
        line3 = trans(0, 0, down_column_high + up_column_high) * line
        line4 = trans(0, -hang, down_column_high - R3 * 3 - short) * line
        line_all = Combine(line1, line2, line3, line4)

        # 单根电线杆
        pole = Combine(down_column, up_column, left_column, string_all, triangle)

        # 整排电线杆：Array 实例化（间隔防除零）
        spacing = x if x > 0 else 1
        number = int(line_long // spacing) + 1
        poles = _arr(pole, [Vec3(spacing * i, 0, 0) for i in range(number)])

        self['接触网'] = Combine(line_all, poles)

if __name__ == "__main__":
    FinalGeometry = 接触网()
    TwoPointPlace.linearize(FinalGeometry,'电线长')
    place(FinalGeometry)
