from pyp3d import *

class 体育馆外墙无门(Component):
    def __init__(self):
        Component.__init__(self)
        self['底宽'] = Attr(2238.76, obvious=True)
        self['顶宽'] = Attr(3112.79, obvious=True)
        self['高度'] = Attr(24073.92,obvious = True)
        self['长度'] = Attr(14566.93, obvious=True)

        self['体育馆外墙无门'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']/2
        H = self['高度']
        DW = self['底宽']
        TW = self['顶宽']
        R = TW/3112.79*4600
        mid_x = R/4600*2482
        mid_y = R/4600*3550
        under = Section(Vec2(0,0),Vec2(DW,0),Vec2(DW,H),Vec2(DW-TW,H),
                        Arc(Vec2(DW-TW,H),Vec2(-mid_x,H-R+mid_y),Vec2(DW-TW-R,H-R)),
                        Vec2(DW-TW-R,H-R),Vec2(0,0))
        mian = rotate(Vec3(1,0,0),pi/2)*under
        all = Loft(mian,trans(0,L,0)*mian)
       
        self['体育馆外墙无门'] = all

if __name__ == "__main__":
    FinalGeometry = 体育馆外墙无门()
    FinalGeometry.replace()
    place(FinalGeometry)