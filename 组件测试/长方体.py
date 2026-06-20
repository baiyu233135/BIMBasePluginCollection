# -*- coding: utf-8 -*-
"""
长方体参数化组件

可调参数：
- 长度 : 长方体X方向长度 (mm)
- 宽度 : 长方体Y方向宽度 (mm)
- 高度 : 长方体Z方向高度 (mm)
"""

from pyp3d import *

class 长方体(Component):
    """长方体：长宽高三维尺寸可调的立方体"""

    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(200.0, obvious=True)
        self['宽度'] = Attr(100.0, obvious=True)
        self['高度'] = Attr(150.0, obvious=True)
        self['长方体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        W = self['宽度']
        H = self['高度']
        self['长方体'] = scale(L, W, H) * Cube()


if __name__ == "__main__":
    FinalGeometry = 长方体()
    place(FinalGeometry)
