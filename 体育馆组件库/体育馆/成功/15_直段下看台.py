from pyp3d import *

class 直段下看台(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(17076.77, obvious=True)
        self['宽度'] = Attr(14763.78, obvious=True)
        self['高度'] = Attr(5954.72,obvious = True)
        self['隔板宽'] = Attr(98.43, obvious=True)
        self['隔板高'] = Attr(688.98,obvious = True)

        self['直段下看台'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['高度']
        W = self['宽度']
        w = self['隔板宽']
        high = self['隔板高']
        h = 49.21
        dl = L/17076.77*16535.4
        mid_w = W/14763.78*1476.38
        lt = []
        for i in range(21):
            sec = trans(0, (H-h)/21*i, 0) * Section(Vec2(0,0), Vec2(L-dl/21*i,0), Vec2(L-dl/21*i,(H-h)/21), Vec2(0,(H-h)/21), Vec2(0,0))
            lt.append(rotate(Vec3(1,0,0), pi/2) * Loft(sec, trans(0,0,W)*sec))
        louti = Combine(*lt)

        gb_sec = Section(Vec2(0,0),Vec2(w,0),Vec2(w,-W/2+mid_w/2),Vec2(0,-W/2+mid_w/2),Vec2(0,0))
        gb = trans(L-w,0,0)*Loft(gb_sec,trans(0,0,high)*gb_sec)
        gb_all = Combine(gb,trans(0,-W/2-mid_w/2,0)*gb)

        pt_sec = Section(Vec2(0,0),Vec2(L-dl-w,0),Vec2(L-dl-w,-W),Vec2(0,-W),Vec2(0,0))
        pt = trans(-L+dl+w)*Loft(pt_sec,trans(0,0,H)*pt_sec)

        self['直段下看台'] = louti + gb_all + pt

if __name__ == '__main__':
    FinalGeometry = 直段下看台()
    FinalGeometry.replace()
    place(FinalGeometry)