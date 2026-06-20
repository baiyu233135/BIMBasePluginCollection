# -*- coding: utf-8 -*-
"""
直角三棱柱参数化组件

可调参数：
- 直角边1 : 直角三角形的一条直角边 (mm)
- 直角边2 : 直角三角形的另一条直角边 (mm)
- 高度    : 三棱柱的拉伸高度 (mm)
"""

from pyp3d import *

class 直角三棱柱(Component):
    """直角三棱柱：底面为直角三角形，沿高度方向拉伸"""

    def __init__(self):
        Component.__init__(self)
        self['直角边1'] = Attr(100.0, obvious=True)
        self['直角边2'] = Attr(100.0, obvious=True)
        self['高度'] = Attr(200.0, obvious=True)
        self['直角三棱柱'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        a = self['直角边1']
        b = self['直角边2']
        h = self['高度']
        section = Section(Vec2(0, 0), Vec2(a, 0), Vec2(0, b))
        path = Line(Vec3(0, 0, 0), Vec3(0, 0, h))
        self['直角三棱柱'] = Sweep(section, path)


if __name__ == "__main__":
    FinalGeometry = 直角三棱柱()
    place(FinalGeometry)
