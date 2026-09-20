# -*- coding: utf-8 -*-
"""
椭圆墩柱 — 性能优化版

优化说明：
- 两端圆柱由 N=64 手工多边形截面 Loft 改为解析圆锥 Cone，更省更光滑。
- 装配合并由 +（布尔并）改为 Combine（并列）。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import *

class 扩大基础(Component):
    def __init__(self):
        Component.__init__(self)
        self['底长(m)'] = Attr(152800,obvious = True)
        self['底宽(m)'] = Attr(57800,obvious = True)
        self['底高'] = Attr(42000,obvious = True)
        self['上长'] = Attr(122000,obvious = True)
        self['上宽'] = Attr(42000,obvious = True)
        self['上高'] = Attr(30000,obvious = True)
        self['扩大基础'] = Attr(None, show=True)

        self.replace()
    @export
    def replace(self):
        DL = self['底长(m)']
        DW = self['底宽(m)']
        DH = self['底高']
        GL = self['上长']
        GW = self['上宽']
        GH = self['上高']

        # ===== 底部 =====
        R = DW / 2

        # 左侧圆柱（圆心在x=R处），解析圆锥替代 64 边形 Loft
        D1 = trans(R,R,0)*Cone(Vec3(0, 0, 0), Vec3(0, 0, DH), R, R)

        # 右侧圆柱（圆心在x=DL+R处）
        D2 = trans(DL, 0, 0) * D1

        # 中间长方体（刚好连接两个圆柱）
        D = trans(R, 0, 0) * scale(DL, DW, DH) * Cube()

        dibu = Combine(D1, D2, D)

        # ===== 顶部 =====
        R2 = GW / 2
        
        # 顶部左侧圆柱
        G1 = trans(DL/2-GL/2+R,R, DH) * Cone(Vec3(0, 0, 0), Vec3(0, 0, GH), R2, R2)

        # 顶部右侧圆柱
        G2 = trans(GL, 0, 0) * G1

        # 顶部中间长方体
        G = trans(DL/2+R-GL/2,R-R2, DH) * scale(GL, GW, GH) * Cube()

        shbu = Combine(G, G1, G2)
        self['扩大基础'] = Combine(dibu, shbu)

if __name__ == "__main__":
    FinalGeometry = 扩大基础()
    FinalGeometry.replace()
    place(FinalGeometry)
