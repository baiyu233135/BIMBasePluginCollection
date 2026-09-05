from pyp3d import *

class 直段上看台(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(23334.54, obvious=True)
        self['宽度'] = Attr(14763.78, obvious=True)
        self['高度'] = Attr(11112.21,obvious = True)
        self['隔板宽'] = Attr(98.43, obvious=True)
        self['隔板高'] = Attr(1102.36,obvious = True)
        self['中部通道宽'] = Attr(1968.50,obvious = True)
        self['中部通道高'] = Attr(2795.28,obvious = True)

        self['直段上看台'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['高度']
        W = self['宽度']
        w = self['隔板宽']
        high = self['隔板高']
        h = 393.7
        dl = L/23334.54*18110.2
        zw = self['中部通道宽']
        zh = self['中部通道高']
        lt = []
        for i in range(23):
            sec = trans(0, (H-h)/23*i, 0) * Section(Vec2(0,0), Vec2(L-dl/23*i,0), Vec2(L-dl/23*i,(H-h)/23), Vec2(0,(H-h)/23), Vec2(0,0))
            lt.append(rotate(Vec3(1,0,0), pi/2) * Loft(sec, trans(0,0,W)*sec))
        louti = Combine(*lt)

        gb_sec = Section(Vec2(0,0),Vec2(w,0),Vec2(w,-W),Vec2(0,-W),Vec2(0,0))
        gb = trans(L-w,0,0)*Loft(gb_sec,trans(0,0,high)*gb_sec)
        gb_all = Combine(gb)

        pt_sec = Section(Vec2(0,0),Vec2(L-dl-w,0),Vec2(L-dl-w,-W),Vec2(0,-W),Vec2(0,0))
        pt = trans(-L+dl+w)*Loft(pt_sec,trans(0,0,H-h)*pt_sec)

        cmid_sec = Section(Vec2(0,0),Vec2(dl,0),Vec2(dl,zw),Vec2(0,zw),Vec2(0,0))
        cmid = Loft(cmid_sec,trans(0,0,zh)*cmid_sec)
        cmid_end = trans(0,-W/2-zw/2,h+dl/23*5)*cmid

        self['直段上看台'] = louti + gb_all + pt

if __name__ == '__main__':
    FinalGeometry = 直段上看台()
    FinalGeometry.replace()
    place(FinalGeometry)