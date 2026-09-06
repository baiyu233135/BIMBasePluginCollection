from pyp3d import * 
class 被插板(Component):

    def __init__(self):
        Component.__init__(self) 
        self['长度'] = Attr(10000,obvious = True)
        self['宽度'] = Attr(1000,obvious = True)
        self['高度'] = Attr(500,obvious = True)
        self['凹槽长度'] = Attr(100,obvious = True)
        self['凹槽宽度'] = Attr(600,obvious = True)
        self['凹槽深度'] = Attr(500,obvious = True)
        self['凹槽间隔'] = Attr(400,obvious = True)
        self['凹槽排数'] = Attr('1',obvious = True)   # 字符串型,避免面板显示 mm 后缀
        self['排列间距'] = Attr(0,obvious = True)   # 数字型(带 mm 单位),中心距;0=所有排重叠到板中心
        
        self['被插板'] = Attr(None,show = True)
        self.replace()

    @export

    def replace(self):
        L = self['长度']
        W = self['宽度']
        H = self['高度']
        l = self['凹槽长度']
        w = self['凹槽宽度']
        h = self['凹槽深度']
        long = self['凹槽间隔']
        # 凹槽排数为字符串型,容错解析为正整数(非法输入回退 1)
        try:
            n = max(1, int(float(str(self['凹槽排数']).strip())))
        except (TypeError, ValueError):
            n = 1

        # 排列间距(中心距):字面含义,0=所有排重叠到板中心;非法输入按 0 处理
        try:
            gap = float(str(self['排列间距']).strip())
        except (TypeError, ValueError):
            gap = 0
        pitch = max(gap, 0)

        # 超界整体缩放:只缩放凹槽开口(长×宽,保持比例),深度不随排列参数变化,
        # 仅在深度超过板厚时钳到板厚(通槽)
        # 宽度向:n≥2 且排距>0 时槽宽 ≤ 排距(防并槽);单排/重叠排仅防超出板边
        # 长度向:槽长 ≤ 间隔
        w_max = pitch if (n >= 2 and pitch > 0) else W
        s = 1.0
        if w > 0:
            s = min(s, 0.9 * w_max / w)
        if l > 0:
            s = min(s, 0.9 * long / l)
        l, w = l * s, w * s
        h = min(h, H)
        if n >= 2 and pitch > 0:
            max_span = W - w                          # 最外两排中心距上限(两端留槽宽)
            if (n - 1) * pitch > max_span:
                pitch = max(max_span / (n - 1), 1)    # 排距超出板宽时压缩到能放下
                if w > 0.9 * pitch:                   # 压缩后排距变小,开口再缩一次防并槽
                    s2 = 0.9 * pitch / w
                    l, w = l * s2, w * s2

        sec_long = Section(Vec2(0,0),Vec2(L,0),Vec2(L,W),Vec2(0,W))
        Long = Sweep(sec_long, Line(Vec3(0,0,0), Vec3(0,0,H)))
        sec_short = Section(Vec2(-l/2,-w/2),Vec2(l/2,-w/2),Vec2(l/2,w/2),Vec2(-l/2,w/2))
        short_base = Sweep(sec_short, Line(Vec3(0,0,0), Vec3(0,0,h)))
        line = L - 2 * long              # 两端留空后的可用长度
        x = max(1, int(line // long))    # 每排凹槽个数
        if x % 2 == 0:                   # 偶数：中心两侧 ±long/2 起排
            offsets = [long/2 + long*i for i in range(x//2)]
            offsets += [-o for o in offsets]
        else:                            # 奇数：中心一个，两侧 ±long 起排
            offsets = [0] + [long*i for i in range(1, x//2 + 1)]
            offsets += [-o for o in offsets[1:]]
        short = []
        for j in range(n):               # 排组整体居中:排中心 = 板宽中心 + (j-(n-1)/2)×排距
            yc = W / 2 + (j - (n - 1) / 2.0) * pitch
            row_unit = trans(L/2, yc, 0) * short_base
            for dx in offsets:
                short.append(trans(dx, 0, 0) * row_unit)
        Short = Combine(*short)
        try:
            result = Long - Short        # pyp3d 布尔减不稳定，失败时退化为整板
            if result is None:
                raise ValueError('boolean subtraction returned None')
        except Exception:
            result = Long

        self['被插板'] = result

if __name__ == "__main__":
    FinalGeometry = 被插板()
    
    place(FinalGeometry)
