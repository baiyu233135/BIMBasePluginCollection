# -*- coding: utf-8 -*-
"""
组装工字梁 — 性能优化版

优化说明：
- 整排梁由循环逐个 + 合并改为 Array 实例化排布。
- sqrt(XL²-SL²) 加负数开方保护（XL≤斜长投影为零时按 0 处理，不崩溃）。
- 数量字符串解析加容错（合法数字输入行为不变）。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import *
import math


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 侧面钢桁架(Component):
    def __init__(self):
        Component.__init__(self)
        self['竖长'] = Attr(10000, obvious = True)
        self['斜长'] = Attr(30000, obvious = True)
        self['数量'] = Attr("5", obvious = True) 
        self['截面长'] =Attr(1200,obvious = True)
        self['截面宽'] =Attr(1200,obvious = True)
        self['厚度'] =Attr(10,obvious = True)
        self['侧面钢桁架'] = Attr(None, show = True)
        
        self.replace()

    @export
    def replace(self):
        # 数量为字符串型，容错解析（非法输入回退默认值）
        try:
            x = int(float(str(self['数量']).strip()))
        except (TypeError, ValueError):
            x = 5
        x = max(x, 0)
        SL = self['竖长']
        XL = self['斜长']
        JL = self['截面长']
        JW = self['截面宽']
        H = self['厚度']
        jiemian1 = Section(Vec2(0,0),Vec2(JL,0),Vec2(JL,H),Vec2(JL/2+H/2,H),Vec2(JL/2+H/2,JW-H),
                           Vec2(JL,JW-H),Vec2(JL,JW),Vec2(0,JW),Vec2(0,JW-H),Vec2(JL/2-H/2,JW-H),
                           Vec2(JL/2-H/2,H),Vec2(0,H),Vec2(0,0))
        jiemian_1 = Loft(jiemian1,trans(0,0,SL)*jiemian1)
        jiemian_2 = Loft(jiemian1,trans(0,0,XL)*jiemian1)
        # 斜长必须不小于竖长，否则水平投影为负；加保护防负数开方/除零
        b = math.sqrt(max(XL**2 - SL**2, 0))
        b_safe = b if b > 0 else 1e-6
        jiemian = Combine(jiemian_1, rotate(Vec3(0,1,0),-math.atan(SL/b_safe)+pi/2)*jiemian_2)
        if x <= 0:
            self['侧面钢桁架'] = jiemian
        else:
            self['侧面钢桁架'] = _arr(jiemian, [Vec3(i*b, 0, 0) for i in range(x)])

if __name__ == "__main__":
    FinalGeometry = 侧面钢桁架()
    place(FinalGeometry)
