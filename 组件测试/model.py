# -*- coding: utf-8 -*-
"""
直角三棱柱参数化组件

可调参数：
- 直角边1 (a) : 直角三角形的一条直角边 (mm)
- 直角边2 (b) : 直角三角形的另一条直角边 (mm)
- 高度 (h)    : 三棱柱的拉伸高度 (mm)
"""

from pyp3d import *

class 直角三棱柱(Component):
    """直角三棱柱：底面为直角三角形，沿高度方向拉伸"""

    def __init__(self):
        Component.__init__(self)
        # 定义各个参数及其默认值
        self['直角边1'] = Attr(100.0, obvious=True)
        self['直角边2'] = Attr(100.0, obvious=True)
        self['高度'] = Attr(200.0, obvious=True)
        self['直角三棱柱'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        """根据当前参数重新生成几何体"""
        # 设置变量，同时调用参数（简化书写过程）
        a = self['直角边1']
        b = self['直角边2']
        h = self['高度']

        # 直角三角形截面：三个顶点
        section = Section(
            Vec2(0, 0),
            Vec2(a, 0),
            Vec2(0, b)
        )

        # 沿 Z 轴拉伸
        path = Line(Vec3(0, 0, 0), Vec3(0, 0, h))

        self['直角三棱柱'] = Sweep(section, path)


# 输出模型
if __name__ == "__main__":
    FinalGeometry = 直角三棱柱()
    place(FinalGeometry)
