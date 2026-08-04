# -*- coding: utf-8 -*-
"""
投影测试用横隔板组件（简化版）

用途：
  供桥隧病害识别模块做 3D 投影测试。横隔板病害多出现在大桩号面/小桩号面，
  本组件简化为一块带预留孔的竖直板，便于在板面上测试病害阴影/点云投影。

参考：
  桥梁组件/桥梁组件/1-上部结构/T梁.py 中横隔板的构造思路
  数据参考源/桥隧数据源/ 中的横隔板病害照片

坐标系（BIMBase）：X 横向，Y 厚度方向，Z 高度方向
"""

from pyp3d import *


class 投影测试横隔板(Component):
    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数，单位 cm
        self['宽度'] = Attr(200.0, obvious=True)   # 沿 X 方向
        self['高度'] = Attr(160.0, obvious=True)   # 沿 Z 方向
        self['厚度'] = Attr(20.0, obvious=True)     # 沿 Y 方向
        self['预留孔宽'] = Attr(60.0, obvious=True)
        self['预留孔高'] = Attr(60.0, obvious=True)

        self['投影测试横隔板'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        W = self['宽度']
        H = self['高度']
        T = self['厚度']
        hw = self['预留孔宽']
        hh = self['预留孔高']

        # 主体竖直板：角点原点，X 从 0 到 W，Y 从 0 到 T，Z 从 0 到 H
        plate = scale(W, T, H) * Cube()

        # 居中预留孔（模拟翼缘板穿过区域），厚度方向稍大以保证完全穿透
        hole = translate((W - hw) / 2, -T * 0.1, (H - hh) / 2) * scale(hw, T * 1.2, hh) * Cube()
        body = plate - hole

        self['投影测试横隔板'] = body


if __name__ == "__main__":
    FinalGeometry = 投影测试横隔板()
    place(FinalGeometry)
