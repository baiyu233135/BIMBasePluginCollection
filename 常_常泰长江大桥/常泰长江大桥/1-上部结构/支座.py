# -*- coding: utf-8 -*-
"""
支座 — 性能优化版

优化说明：
- 螺丝由 N=64 手工多边形截面 Loft 改为解析圆锥 Cone（R=20mm 小半径收益最大）。
- 8 组耳板/螺丝单元由循环逐个 Combine 改为 Array 实例化排布。
- 装配合并由 +（布尔并）改为 Combine（并列），不做无谓布尔。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import *
import math


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 支座(Component):
    def __init__(self):
        Component.__init__(self)
        self['上部平台长'] = Attr(1500,obvious = True)
        self['上部平台宽'] = Attr(1600,obvious = True)
        self['上部平台高'] = Attr(80,obvious = True)

        self['上中链接长'] = Attr(900,obvious = True)
        self['上中链接宽'] = Attr(1340,obvious = True)
        self['上中链接高'] = Attr(200,obvious = True)

        self['中部长'] = Attr(1340,obvious = True) 
        self['中部宽'] = Attr(1340,obvious = True)
        self['中部高'] = Attr(400,obvious = True)

        self['下部平台长'] = Attr(2860,obvious = True)
        self['下部平台宽'] = Attr(1730,obvious = True)
        self['下部平台高'] = Attr(150,obvious = True)

        self['螺丝长'] = Attr(200,obvious = True)
        self['螺丝半径'] = Attr(20,obvious = True)
        
        self['支座'] = Attr(None,show = True)

        self.replace()

    @export
    def replace(self):
        up_up_long = self['上部平台长']
        up_up_wide = self['上部平台宽']
        up_up_high = self['上部平台高']
        up_down_long = self['上中链接长']
        up_down_wide = self['上中链接宽']
        up_down_high = self['上中链接高']
        down_up_long = self['中部长']
        down_up_wide = self['中部宽']
        down_up_high = self['中部高']
        down_down_long = self['下部平台长']
        down_down_wide = self['下部平台宽']
        down_down_high = self['下部平台高']
        R1 = self['螺丝半径']
        screw = self['螺丝长']
        # 解析圆锥替代 64 边形 Loft
        screw_cone = Cone(Vec3(0, 0, 0), Vec3(0, 0, screw), R1, R1)
        unit = Section(Vec2(15,0),Vec2(55,0),Vec2(70,15),Vec2(70,55),Vec2(55,70),
                       Vec2(15,70),Vec2(0,55),Vec2(0,15),Vec2(15,0))
        up_up_platform = scale(up_up_long,up_up_wide,up_up_high)*Cube()
        unit_up = Loft(unit,trans(0,0,up_up_high+20)*unit)
        position = [(30,30),(120,30),(up_up_long-190,30),(up_up_long-100,30),
                    (30,up_up_wide-100),(120,up_up_wide-100),(up_up_long-190,up_up_wide-100),(up_up_long-100,up_up_wide-100)]
        up_arr = _arr(unit_up, [Vec3(px, py, -10) for (px, py) in position])
        up_up = trans(down_down_long/2-up_up_long/2,down_down_wide/2-up_up_wide/2,down_down_high+down_up_high+up_down_high)*Combine(up_up_platform, up_arr)

        up_down_platform = scale(up_down_long,up_down_wide,up_down_high)*Cube()
        up_down = trans(down_down_long/2-up_down_long/2,down_down_wide/2-up_down_wide/2,down_down_high+down_up_high)*up_down_platform

        down_up_platform = scale(down_up_long,down_up_wide,down_up_high)*Cube()
        down_up = trans(down_down_long/2-down_up_long/2,down_down_wide/2-down_up_wide/2,down_down_high)*down_up_platform

        down_down_platform = scale(down_down_long,down_down_wide,down_down_high)*Cube()
        unit_down = Combine(Loft(unit,trans(0,0,down_down_high+40)*unit),
                            trans(35,35,-screw)*screw_cone)
        position_down = [(down_down_long/2860*105,down_down_wide/173*10),
                         (down_down_long/2860*105+down_down_long/286*86,down_down_wide/173*10),
                         (down_down_long/2860*105+down_down_long/286*86*2,down_down_wide/173*10),
                         (down_down_long/2860*105+down_down_long/286*86*3,down_down_wide/173*10),
                         (down_down_long/2860*105,down_down_wide/173*163),
                         (down_down_long/2860*105+down_down_long/286*86,down_down_wide/173*163),
                         (down_down_long/2860*105+down_down_long/286*86*2,down_down_wide/173*163),
                         (down_down_long/2860*105+down_down_long/286*86*3,down_down_wide/173*163)]
        down_arr = _arr(unit_down, [Vec3(px, py, -20) for (px, py) in position_down])
        down_down = Combine(down_down_platform, down_arr)

        self['支座'] = Combine(down_up, down_down, up_up, up_down)

if __name__ == "__main__":
    FinalGeometry = 支座()
    place(FinalGeometry)
