# -*- coding: utf-8 -*-
"""
索塔锚块 — 性能优化版

优化说明：
- 底柱由 N=64 手工多边形截面 Loft 改为解析圆锥 Cone，7×2 根柱由循环内
  重复 Loft + 逐个合并改为一次基准几何 + Array 实例化排布。
- 装配合并由 +（布尔并）改为 Combine（并列）。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import * 


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 索塔锚块(Component):
    def __init__(self):
        Component.__init__(self)
        # 核心尺寸（单位：cm，对照三视图标注1:1还原）
        self['锚块总长'] = Attr(5450, obvious=True)
        self['锚块总高'] = Attr(2039, obvious=True)
        self['锚块宽度'] = Attr(1200, obvious=True)
        self['承台长度'] = Attr(5680, obvious = True)
        self['承台宽度'] = Attr(1600, obvious = True)
        self['承台高度'] = Attr(400,obvious = True)
        self['底柱半径'] = Attr(170, obvious = True)
        self['底柱高度'] = Attr(1000, obvious = True)
        self['索塔'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['锚块总长']
        H = self['锚块总高']
        W = self['锚块宽度']
        CL = self['承台长度']
        CH = self['承台高度']
        CW = self['承台宽度']
        R = self['底柱半径']
        DH = self['底柱高度']
        # 解析圆锥替代 64 边形 Loft，一次基准 + Array 排布两排柱
        col = Cone(Vec3(0, 0, 0), Vec3(0, 0, DH), R, R)
        offsets = []
        for i in range(7):
            offsets.append(Vec3(290-R/2+i*850, 250+R/2, 0))
            offsets.append(Vec3(290-R/2+i*850, -250-R/2, 0))
        alld = _arr(col, offsets)

        CT = translate(0,-CW/2,DH)*scale(CL,CW,CH)*Cube()

        MDP = Section(Vec2(50,0),Vec2(50+L,0),Vec2(50+L,1250),
                      Vec2(4863,2039),Vec2(3863,2039),Vec2(50,1300))
        section = rotate(Vec3(1,0,0),0.5*pi) * MDP
        line = Line(Vec3(0,0,0),Vec3(0,W,0))
        MD = translate(0,-W/2,DH+CH)*Sweep(section, line)
        self["索塔"] = Combine(alld, CT, MD)
if __name__ == "__main__":
    FinalGeometry = 索塔锚块()
    place(FinalGeometry)
