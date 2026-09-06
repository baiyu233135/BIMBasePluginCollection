from pyp3d import *
class 凸插板(Component):

    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(10000,obvious = True)
        self['宽度'] = Attr(1000,obvious = True)
        self['高度'] = Attr(500,obvious = True)
        self['凸起长度'] = Attr(100,obvious = True)
        self['凸起宽度'] = Attr(600,obvious = True)
        self['凸起高度'] = Attr(500,obvious = True)
        self['凸起间隔'] = Attr(400,obvious = True)

        self['凸插板'] = Attr(None,show = True)
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

        # 底板:底部 10mm 灰色层 + 上层(双色区分)
        sec_long = Section(Vec2(0,0),Vec2(L,0),Vec2(L,W),Vec2(0,W))
        plate = Sweep(sec_long, Line(Vec3(0,0,0), Vec3(0,0,H)))
        base10 = Sweep(sec_long, Line(Vec3(0,0,0), Vec3(0,0,10))).color(0.4,0.4,0.4,1)
        try:
            upper = plate - base10         # pyp3d 布尔减不稳定,失败时退化为整板
            if upper is None:
                raise ValueError('boolean subtraction returned None')
        except Exception:
            upper = plate
        Long = Combine(base10, upper)

        # 凸起:沿板宽中心单排,顶面与板底贴合(z 从 -h 到 0,不再悬空)
        sec_short = Section(Vec2(-l/2,-w/2),Vec2(l/2,-w/2),Vec2(l/2,w/2),Vec2(-l/2,w/2))
        bump_base = Sweep(sec_short, Line(Vec3(0,0,0), Vec3(0,0,h)))
        line = L - 2 * long              # 两端留空后的可用长度
        x = max(1, int(line // long))    # 凸起个数
        if x % 2 == 0:                   # 偶数：中心两侧 ±long/2 起排
            offsets = [long/2 + long*i for i in range(x//2)]
            offsets += [-o for o in offsets]
        else:                            # 奇数：中心一个，两侧 ±long 起排
            offsets = [0] + [long*i for i in range(1, x//2 + 1)]
            offsets += [-o for o in offsets[1:]]
        bumps = []
        row_unit = trans(L/2, W/2, -h) * bump_base
        for dx in offsets:
            bumps.append(trans(dx, 0, 0) * row_unit)
        Short = Combine(*bumps)

        self['凸插板'] = Combine(Long, Short)

if __name__ == "__main__":
    FinalGeometry = 凸插板()
    place(FinalGeometry)
