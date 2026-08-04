# -*- coding: utf-8 -*-
"""
投影测试用湿接缝组件（简化版）

用途：
  供桥隧病害识别模块做 3D 投影测试。湿接缝病害多出现在接缝顶面、侧面，
  本组件简化为一块带倒角的长条块，便于在顶面和侧面测试病害投影。

参考：
  桥梁组件/桥梁组件/1-上部结构/湿接缝.py
  数据参考源/桥隧数据源/ 中的湿接缝病害照片

坐标系（BIMBase）：X 横向（接缝宽度方向），Y 梁长方向，Z 高度方向
"""

from pyp3d import *


class 投影测试湿接缝(Component):
    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数，单位 cm
        self['长度'] = Attr(3000.0, obvious=True)   # 沿 Y 方向
        self['顶宽'] = Attr(50.0, obvious=True)     # 沿 X 方向
        self['底宽'] = Attr(30.0, obvious=True)
        self['高度'] = Attr(80.0, obvious=True)     # 沿 Z 方向

        self['投影测试湿接缝'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        top_w = self['顶宽']
        bottom_w = self['底宽']
        H = self['高度']

        # 梯形截面，沿 Y 方向拉伸
        half_top = top_w / 2
        half_bottom = bottom_w / 2
        section = Section(
            Vec2(-half_bottom, 0),
            Vec2(half_bottom, 0),
            Vec2(half_top, H),
            Vec2(-half_top, H),
        )
        path = Line(Vec3(0, -L / 2, 0), Vec3(0, L / 2, 0))
        body = Sweep(section, path)

        self['投影测试湿接缝'] = body


if __name__ == "__main__":
    FinalGeometry = 投影测试湿接缝()
    place(FinalGeometry)
