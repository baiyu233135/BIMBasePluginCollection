# -*- coding: utf-8 -*-
"""
正方体参数化组件

可调参数：
- 边长 : 正方体的边长 (mm)
"""

from pyp3d import *

class 正方体(Component):
    """正方体：长宽高相等的立方体"""

    def __init__(self):
        Component.__init__(self)
        self['边长'] = Attr(100.0, obvious=True)
        self['正方体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        a = self['边长']
        self['正方体'] = scale(a, a, a) * Cube()


if __name__ == "__main__":
    FinalGeometry = 正方体()
    place(FinalGeometry)
