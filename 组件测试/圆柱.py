# -*- coding: utf-8 -*-
"""
圆柱参数化组件

可调参数：
- 半径 : 圆柱底面半径 (mm)
- 高度 : 圆柱的拉伸高度 (mm)
"""

from pyp3d import *
import math

class 圆柱(Component):
    """圆柱：底面为圆形，沿高度方向拉伸"""

    def __init__(self):
        Component.__init__(self)
        self['半径'] = Attr(50.0, obvious=True)
        self['高度'] = Attr(100.0, obvious=True)
        self['圆柱'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        r = self['半径']
        h = self['高度']
        # 圆形截面：用多边形逼近
        segments = 32
        points = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            points.append(Vec2(r * math.cos(angle), r * math.sin(angle)))
        section = Section(*points)
        path = Line(Vec3(0, 0, 0), Vec3(0, 0, h))
        self['圆柱'] = Sweep(section, path)


if __name__ == "__main__":
    FinalGeometry = 圆柱()
    place(FinalGeometry)
