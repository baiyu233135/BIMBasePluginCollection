# -*- coding: utf-8 -*-
"""
投影测试用墩柱组件（简化版）

用途：
  供桥隧病害识别模块做 3D 投影测试。墩柱病害多出现在柱身侧面，
  本组件简化为圆柱或方柱，便于在柱面测试病害阴影/点云投影。

参考：
  桥梁组件/桥梁组件/2-下部结构/柱式桥墩.py
  数据参考源/桥隧数据源/ 中的墩柱病害照片

坐标系（BIMBase）：X 横向，Y 横向，Z 高度方向
"""

from pyp3d import *


class 投影测试墩柱(Component):
    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数，单位 cm
        self['柱径'] = Attr(120.0, obvious=True)    # 圆柱直径
        self['柱高'] = Attr(800.0, obvious=True)
        self['截面形式'] = Attr(0, obvious=True)    # 0=圆柱，1=方柱

        self['投影测试墩柱'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        D = self['柱径']
        H = self['柱高']
        section_type = int(self['截面形式'])

        if section_type == 1:
            # 方柱：角点原点，从 (0,0,0) 到 (D,D,H)
            body = scale(D, D, H) * Cube()
        else:
            # 圆柱：底面圆心在 (0,0,0)，向上延伸 H
            r = D / 2
            body = Cone(Vec3(0, 0, 0), Vec3(0, 0, H), r, r)

        self['投影测试墩柱'] = body


if __name__ == "__main__":
    FinalGeometry = 投影测试墩柱()
    place(FinalGeometry)
