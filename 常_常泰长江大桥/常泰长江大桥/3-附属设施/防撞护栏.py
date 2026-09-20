from pyp3d import *
from math import atan

class 防撞护栏(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为mm
        self['默认长度'] = Attr(2409200, obvious=True)
        self['底宽'] = Attr(500, obvious=True)
        self['顶宽'] = Attr(250, obvious=True)
        self['总高'] = Attr(1000, obvious=True)

        self['防撞护栏'] = Attr(None, show=True)
        self.replace()
    @export
    def replace(self):
        L=self['默认长度']
        XW=self['底宽']
        SW=self['顶宽']
        H=self['总高']
        SH=0.46*H
        XH=0.54*H
        D = scale(L, XW, 2/3*XH) * Cube()

        EQ = Section(Vec2(XW/2,-L/2), Vec2(XW/2,L/2),Vec2(-XW/2,L/2), Vec2(-XW/2,-L/2))
        EQ1 = Section(Vec2(0.7*XW/2,-L/2), Vec2(0.7*XW/2,L/2),Vec2(-0.7*XW/2,L/2), Vec2(-0.7*XW/2,-L/2))
        loft1 = translate(L/2,XW/2, 2/3*XH)*rotate(Vec3(0,0,1), 0.5*pi) *Loft(EQ, translate(-0.15*XW,0,1/3*XH) * EQ1)

        Q = translate(SW/2,0, 0)*Section(Vec2(SW/2,-L/2), Vec2(SW/2,L/2),Vec2(-SW/2,L/2), Vec2(-SW/2,-L/2))
        loft = translate(L/2,0.35*XW,XH)*rotate(Vec3(0,0,1), 0.5*pi) *Loft(translate(0,0, 0)*EQ1, translate(-0.35*XW,0,SH) * Q)



        self['防撞护栏'] =  D + loft1 + loft
if __name__ == "__main__":
    FinalGeometry = 防撞护栏()
    TwoPointPlace.linearize(FinalGeometry, '默认长度')
    place(FinalGeometry)
