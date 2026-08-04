# -*- coding: utf-8 -*-
"""
投影测试用 T 梁组件（简化版）

用途：
  供桥隧病害识别模块做 3D 投影测试。病害多出现在梁底、翼缘板、腹板等表面，
  本组件保留这些关键表面，同时参数精简，便于快速布置和修改。

参考：
  桥梁组件/桥梁组件/1-上部结构/T梁.py
  数据参考源/桥隧数据源/T梁照片/

坐标系（BIMBase）：X 横向，Y 梁长方向，Z 高度方向
"""

from pyp3d import *


class 投影测试T梁(Component):
    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数，单位 cm
        self['梁长'] = Attr(3000.0, obvious=True)
        self['底板宽'] = Attr(80.0, obvious=True)
        self['底板高'] = Attr(25.0, obvious=True)
        self['腹板宽'] = Attr(20.0, obvious=True)
        self['翼缘宽'] = Attr(200.0, obvious=True)
        self['翼缘高'] = Attr(20.0, obvious=True)
        self['总高'] = Attr(160.0, obvious=True)

        self['投影测试T梁'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['梁长']
        dw = self['底板宽']
        dh = self['底板高']
        tw = self['腹板宽']
        fw = self['翼缘宽']
        fh = self['翼缘高']
        H = self['总高']

        web_h = H - dh - fh

        # 梁底（底板）：X/Y 居中，Z 从 0 到 dh
        bottom = translate(-dw / 2, -L / 2, 0) * scale(dw, L, dh) * Cube()

        # 腹板：X/Y 居中，Z 从 dh 到 dh+web_h
        web = translate(-tw / 2, -L / 2, dh) * scale(tw, L, web_h) * Cube()

        # 顶翼缘：X/Y 居中，Z 从 dh+web_h 到 H
        flange = translate(-fw / 2, -L / 2, dh + web_h) * scale(fw, L, fh) * Cube()

        self['投影测试T梁'] = bottom + web + flange


if __name__ == "__main__":
    FinalGeometry = 投影测试T梁()
    place(FinalGeometry)
