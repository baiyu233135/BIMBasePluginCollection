from pyp3d import *
class 斜拉索(Component):
    def __init__(self):
        Component.__init__(self)

        self['斜拉索数量'] = Attr(20, obvious=True)
        self['斜拉索半径'] = Attr(21, obvious=True)
        self['竖向距离'] = Attr(6910, obvious=True)
        self['横向距离'] = Attr(1600, obvious=True)
        self['竖向间距'] = Attr(250, obvious=True)
        self['横向间距'] = Attr(1200, obvious=True)
        self['斜拉索'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        x = self['斜拉索数量']
        R = self['斜拉索半径']
        HJL = self['竖向距离'] 
        SJL = self['横向距离'] 
        SJ = self['竖向间距']
        HJ = self['横向间距']

        N = 64  # 圆的分段数
        pts = [Vec2(R * cos(2 * pi * i / N), R * sin(2 * pi * i / N)) for i in range(N)]
        cables = []
        for i in range(x):
            xp = translation(-(x-1-i) * HJ,0,HJL) * Section(*pts)
            zp = translation(SJL + R,0,-(x-1-i)*SJ) * rotate(Vec3(0,1,0),-0.5*pi) * Section(*pts)
            cables.append(Loft(xp, zp))
        self['斜拉索'] = translation(-SJL-21,0,HJL) *rotate(Vec3(1,0,0), pi) *Combine(*cables)
if __name__ == "__main__":    
    FinalGeometry = 斜拉索()
    place(FinalGeometry)