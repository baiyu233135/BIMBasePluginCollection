# -*- coding: utf-8 -*-
"""
曲线布置接口

在场景中生成一条圆弧曲线，作为后续沿线布置的参考路径。
"""

from pyp3d import *
from math import cos, sin, pi


class 曲线(Component):
    """参数化圆弧曲线"""

    def __init__(self):
        Component.__init__(self)
        self['圆心X'] = Attr(0.0, obvious=True)
        self['圆心Y'] = Attr(0.0, obvious=True)
        self['圆心Z'] = Attr(0.0, obvious=True)
        self['半径'] = Attr(1000.0, obvious=True)
        self['起始角'] = Attr(0.0, obvious=True)
        self['终止角'] = Attr(90.0, obvious=True)
        self['分段数'] = Attr(64, obvious=True)
        self['曲线'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        cx = self['圆心X']
        cy = self['圆心Y']
        cz = self['圆心Z']
        R = self['半径']
        a1 = self['起始角'] * pi / 180.0
        a2 = self['终止角'] * pi / 180.0
        n = int(self['分段数'])
        if n < 2:
            n = 2

        pts = []
        for i in range(n + 1):
            t = i / n
            a = a1 + (a2 - a1) * t
            x = cx + R * cos(a)
            y = cy + R * sin(a)
            pts.append(Vec3(x, y, cz))

        parts = []
        for i in range(n):
            parts.append(Line(pts[i], pts[i + 1]))

        self['曲线'] = Combine(*parts)


if __name__ == "__main__":
    FinalGeometry = 曲线()
    place(FinalGeometry)
