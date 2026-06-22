# -*- coding: utf-8 -*-
"""
直线布置接口

在场景中生成一条直线段，作为后续沿线布置的参考路径。
"""

from pyp3d import *


class 直线(Component):
    """参数化直线段"""

    def __init__(self):
        Component.__init__(self)
        self['起点X'] = Attr(0.0, obvious=True)
        self['起点Y'] = Attr(0.0, obvious=True)
        self['起点Z'] = Attr(0.0, obvious=True)
        self['终点X'] = Attr(1000.0, obvious=True)
        self['终点Y'] = Attr(0.0, obvious=True)
        self['终点Z'] = Attr(0.0, obvious=True)
        self['直线'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        p1 = Vec3(self['起点X'], self['起点Y'], self['起点Z'])
        p2 = Vec3(self['终点X'], self['终点Y'], self['终点Z'])
        self['直线'] = Line(p1, p2)


if __name__ == "__main__":
    FinalGeometry = 直线()
    place(FinalGeometry)
