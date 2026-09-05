from pyp3d import *

class 体育馆外墙有门(Component):
    def __init__(self):
        Component.__init__(self)
        self['底宽'] = Attr(2238.76, obvious=True)
        self['顶宽'] = Attr(3112.79, obvious=True)
        self['高度'] = Attr(24073.92,obvious = True)
        self['长度'] = Attr(14566.93, obvious=True)
        self['门高'] = Attr(2952.76,obvious = True)
        self['门宽'] = Attr(5905.51,obvious = True)

        self['体育馆外墙有门'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']/2
        H = self['高度']
        DW = self['底宽']
        TW = self['顶宽']
        high = self['门高']
        wide = self['门宽']
        R = TW/3112.79*4600
        mid_x = R/4600*2482
        mid_y = R/4600*3550
        mid_l = TW/3112.79*7712.79
        under1 = Section(Vec2(0,0),Vec2(mid_l,0),Vec2(mid_l,R),
                        Arc(Vec2(mid_l-TW,R),Vec2(mid_x,mid_y),Vec2(0,0)),
                        Vec2(0,0))
        under2 = Section(Vec2(0,0),Vec2(DW,0),Vec2(DW,H-R),Vec2(DW-TW-R,H-R),Vec2(0,0))
        mian1 = trans(DW-mid_l,0,H-R)*rotate(Vec3(1,0,0),pi/2)*under1
        mian2 = rotate(Vec3(1,0,0),pi/2)*under2
        cut_mian = Section(Vec2(0,0),Vec2(high,0),Vec2(high,wide),Vec2(0,wide),Vec2(0,0))
        cut = trans(-R,L/2-wide/2,high)*rotate(Vec3(0,1,0),pi/2)*Loft(cut_mian,trans(0,0,TW+R)*cut_mian)
        down = Loft(mian2,trans(0,L,0)*mian2)
        up = Loft(mian1,trans(0,L,0)*mian1)
        rdown = down - cut
       
        self['体育馆外墙有门'] = Combine(up,rdown)

if __name__ == "__main__":
    FinalGeometry = 体育馆外墙有门()
    FinalGeometry.replace()
    place(FinalGeometry)