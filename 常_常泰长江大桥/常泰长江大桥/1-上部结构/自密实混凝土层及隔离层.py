# -*- coding: utf-8 -*-
"""
自密实混凝土层及隔离层 — 性能优化版

优化说明：
- 底板"整板减底壳"布尔减改为两段直接拉伸成型（0~10 灰色底层 + 10~H 上层），
  结果一致且规避 pyp3d 布尔不稳定问题。
- 凸起由循环逐个变换合并改为 Array 实例化排布。
- 可调参数、几何位置与外观均不变；凸起间隔为 0 时加防除零保护。
"""
from pyp3d import *


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 自密实混凝土层及隔离层(Component):

    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(10000,obvious = True)
        self['宽度'] = Attr(2500,obvious = True)
        self['高度'] = Attr(200,obvious = True)
        self['凸起长度'] = Attr(700,obvious = True)
        self['凸起宽度'] = Attr(1400,obvious = True)
        self['凸起高度'] = Attr(200,obvious = True)
        self['凸起间隔'] = Attr(3000,obvious = True)

        self['自密实混凝土层及隔离层'] = Attr(None,show = True)
        self.replace()

    @export

    def replace(self):
        L = self['长度']
        W = self['宽度']
        H = self['高度']
        l = self['凸起长度']
        w = self['凸起宽度']
        h = self['凸起高度']
        long = self['凸起间隔']

        # 超界整体缩放:单排居中,凸起开口(长×宽)保持比例;凸起高度不缩放
        # 宽度向:凸起宽 ≤ 板宽;长度向:凸起长 ≤ 间隔
        s = 1.0
        if w > 0:
            s = min(s, 0.9 * W / w)
        if l > 0:
            s = min(s, 0.9 * long / l)
        l, w = l * s, w * s

        # 底板:底部 10mm 灰色层 + 上层(双色区分)，两段直接拉伸，不做布尔
        sec_long = Section(Vec2(0,0),Vec2(L,0),Vec2(L,W),Vec2(0,W))
        base_h = min(10, H)                    # 板厚不足 10 时整板即底层
        base10 = Sweep(sec_long, Line(Vec3(0,0,0), Vec3(0,0,base_h))).color(0.4,0.4,0.4,1)
        long_parts = [base10]
        if H > base_h:
            long_parts.append(Sweep(sec_long, Line(Vec3(0,0,base_h), Vec3(0,0,H))))
        Long = Combine(*long_parts)

        # 凸起:沿板宽中心单排,顶面与板底贴合(z 从 -h 到 0,不再悬空)
        sec_short = Section(Vec2(-l/2,-w/2),Vec2(l/2,-w/2),Vec2(l/2,w/2),Vec2(-l/2,w/2))
        bump_base = Sweep(sec_short, Line(Vec3(0,0,0), Vec3(0,0,h)))
        spacing = long if long > 0 else 1      # 防除零
        line = L - 2 * spacing             # 两端留空后的可用长度
        x = max(1, int(line // spacing))   # 凸起个数
        if x % 2 == 0:                   # 偶数：中心两侧 ±long/2 起排
            offsets = [spacing/2 + spacing*i for i in range(x//2)]
            offsets += [-o for o in offsets]
        else:                            # 奇数：中心一个，两侧 ±long 起排
            offsets = [0] + [spacing*i for i in range(1, x//2 + 1)]
            offsets += [-o for o in offsets[1:]]
        row_unit = trans(L/2, W/2, -h) * bump_base
        Short = _arr(row_unit, [Vec3(dx, 0, 0) for dx in offsets])

        self['自密实混凝土层及隔离层'] = Combine(Long, Short)

if __name__ == "__main__":
    FinalGeometry = 自密实混凝土层及隔离层()
    place(FinalGeometry)
