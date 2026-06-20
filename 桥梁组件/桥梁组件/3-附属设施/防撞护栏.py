from pyp3d import *
from math import atan

class 防撞护栏(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['默认长度'] = Attr(100, obvious=True)
        self['底宽'] = Attr(50, obvious=True)
        self['顶宽'] = Attr(25, obvious=True)
        self['上端高'] = Attr(46, obvious=True)
        self['下端高'] = Attr(54, obvious=True)

        self['防撞护栏'] = Attr(None, show=True)
        self.replace()
    @export
    def replace(self):
        L=self['默认长度']
        XW=self['底宽']
        SW=self['顶宽']
        SH=self['上端高']
        XH=self['下端高']
        D = scale(L, XW, 2/3*XH) * Cube()

        EQ = Section(Vec2(XW/2,-L/2), Vec2(XW/2,L/2),Vec2(-XW/2,L/2), Vec2(-XW/2,-L/2))
        EQ1 = Section(Vec2((XW-15)/2,-L/2), Vec2((XW-15)/2,L/2),Vec2(-(XW-15)/2,L/2), Vec2(-(XW-15)/2,-L/2))
        loft1 = translate(L/2,XW/2, 2/3*XH)*rotate(Vec3(0,0,1), 0.5*pi) *Loft(EQ, translate(-7.5,0,1/3*XH) * EQ1)

        Q = translate(SW/2,0, 0)*Section(Vec2(SW/2,-L/2), Vec2(SW/2,L/2),Vec2(-SW/2,L/2), Vec2(-SW/2,-L/2))
        loft = translate(L/2,17.5,XH)*rotate(Vec3(0,0,1), 0.5*pi) *Loft(translate(XW/2-7.5-17.5,0, 0)*EQ1, translate(-5-12.5,0,SH) * Q)



        self['防撞护栏'] =  D + loft1 + loft
if __name__ == "__main__":
    FinalGeometry = 防撞护栏()
    TwoPointPlace.linearize(FinalGeometry, '默认长度')
    place(FinalGeometry)