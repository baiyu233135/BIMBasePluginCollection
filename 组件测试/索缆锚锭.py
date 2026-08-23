from pyp3d import * 

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
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
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
        N = 64
        i = 0
        circle_pts = [
            Vec2(R * cos(2 * pi * i / N), R * sin(2 * pi * i / N))
            for i in range(N)
        ]
        sec = Section(*circle_pts)
        columns = []
        for i in range(7):
            col1 = translate(290-R/2+i*850,250+R/2,0)*Loft(sec,translate(0,0,DH)*sec)
            col2 = translate(290-R/2+i*850,-250-R/2,0)*Loft(sec,translate(0,0,DH)*sec)
            col = col1 + col2
            columns.append(col)
        alld = Combine(*columns)

        CT = translate(0,-CW/2,DH)*scale(CL,CW,CH)*Cube()

        MDP = Section(Vec2(50,0),Vec2(50+L,0),Vec2(50+L,1250),
                      Vec2(4863,2039),Vec2(3863,2039),Vec2(50,1300))
        section = rotate(Vec3(1,0,0),0.5*pi) * MDP
        line = Line(Vec3(0,0,0),Vec3(0,W,0))
        MD = translate(0,-W/2,DH+CH)*Sweep(section, line)
        geom = alld + CT + MD
        try:
            # 整体上色（颜色为 "r,g,b[,a]" 字符串，pyp3d Attr 只能存标量/字符串）
            c = self['颜色'] if '颜色' in self else None
            if c:
                vals = [float(x) for x in str(c).split(',') if x.strip()]
                if len(vals) >= 3:
                    geom = geom.color(*vals)
        except Exception:
            pass
        self["索塔"] = geom
if __name__ == "__main__":
    FinalGeometry = 索塔锚块()
    place(FinalGeometry)