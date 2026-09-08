# -*- coding: utf-8 -*-
"""
方圆钢柱 — 性能优化版

优化说明：
- 圆柱由 N=64 手工多边形截面 Loft 改为解析圆锥 Cone，更省更光滑。
- 装配合并由 +（布尔并）改为 Combine（并列）。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import *

class 方圆钢柱(Component):
    def __init__(self):
        Component.__init__(self)
        self['方长'] = Attr(2000, obvious = True)
        self['方宽'] = Attr(2000, obvious = True)
        self['方高'] = Attr(50,obvious = True)
        self['柱半径'] = Attr(750, obvious = True)
        self['柱高'] = Attr(500, obvious = True) 
        
        self['方圆钢柱'] = Attr(None, show = True)
        
        self.replace()

    @export
    def replace(self):
        R = self['柱半径']
        L = self['方长']
        W = self['方宽']
        FH = self['方高']
        ZH = self['柱高']

        # 解析圆锥替代 64 边形 Loft
        ZHU = trans(L/2,W/2,FH)*Cone(Vec3(0, 0, 0), Vec3(0, 0, ZH), R, R)

        DG1 = scale(L,W,FH)*Cube()
        DG = Combine(trans(0,0,0)*DG1, trans(0,0,FH+ZH)*DG1)

        self['方圆钢柱'] = Combine(DG, ZHU)

if __name__ == "__main__":
    FinalGeometry = 方圆钢柱()
    FinalGeometry.replace()
    place(FinalGeometry)
