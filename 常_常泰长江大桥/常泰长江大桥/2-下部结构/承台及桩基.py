# -*- coding: utf-8 -*-
"""
多腿站台 — 性能优化版

优化说明：
- 圆柱由 N=64 手工多边形截面 Loft 改为解析圆锥 Cone，数据量大幅下降且更光滑。
- 圆柱阵列由循环内 Combine(DBH_all, ...) 的 O(n²) 嵌套改为 Array 实例化排布。
- 数量字符串解析改为 int 容错解析（合法数字输入行为不变）。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import *


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 承台及桩基(Component):
    def __init__(self):
        Component.__init__(self)
        self['承台长'] = Attr(23500, obvious = True)
        self['承台宽'] = Attr(55000, obvious = True)
        self['承台高'] = Attr(5000, obvious = True)
        self['横向圆柱数量'] = Attr("4", obvious = True) 
        self['纵向圆柱数量'] = Attr("9", obvious = True) 
        self['圆柱半径'] =Attr(1250,obvious = True)
        self['圆柱高度'] =Attr(118000,obvious = True)
        self['圆柱横向间距'] =Attr(6300,obvious = True)
        self['圆柱纵向间距'] =Attr(6300,obvious = True)

        self['承台及桩基'] = Attr(None, show = True)
        
        self.replace()

    @export
    def replace(self):
        # 数量为字符串型，容错解析（非法输入回退默认值）
        try:
            x1 = int(float(str(self['横向圆柱数量']).strip()))
        except (TypeError, ValueError):
            x1 = 4
        try:
            x2 = int(float(str(self['纵向圆柱数量']).strip()))
        except (TypeError, ValueError):
            x2 = 9
        x1 = max(x1, 0)
        x2 = max(x2, 0)

        R = self['圆柱半径']
        RH = self['圆柱高度']

        L = self['承台长']
        W = self['承台宽']
        H = self['承台高']

        HJ = self['圆柱横向间距']
        ZJ = self['圆柱纵向间距']

        CT = trans(0,0,RH)*scale(L,W,H)*Cube()

        # 解析圆锥替代 64 边形 Loft
        T = Cone(Vec3(0, 0, 0), Vec3(0, 0, RH), R, R)
        X = x1 // 2
        Y = x2 // 2
        if x1%2==0:
            if x2%2==0:
                A = L/2-HJ/2-HJ*(X-1)
                B = W/2-ZJ/2-ZJ*(Y-1)
            else:
                A = L/2-HJ/2-HJ*(X-1)
                B = W/2-ZJ*Y
        else:
            if x2%2==0:
                A = L/2-HJ*X
                B = W/2-ZJ/2-ZJ*(Y-1)
            else:
                A = L/2-HJ*X
                B = W/2-ZJ*Y

        # Array 实例化排布圆柱阵列
        offsets = [Vec3(A + HJ * i, B + ZJ * j, 0)
                   for i in range(x1) for j in range(x2)]
        parts = [CT]
        if offsets:
            parts.append(_arr(T, offsets))
        self['承台及桩基'] = Combine(*parts)

if __name__ == "__main__":
    FinalGeometry = 承台及桩基()
    FinalGeometry.replace()
    place(FinalGeometry)
