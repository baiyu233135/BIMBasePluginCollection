from pyp3d import *
import math

class 新泽西护栏(Component):
    def __init__(self):
        Component.__init__(self)
        self['下宽'] = Attr(500, obvious = True)
        self['下高'] = Attr(500, obvious = True)
        self['上宽'] = Attr(200, obvious = True) 
        self['上高'] =Attr(600,obvious = True)
        self['长度'] =Attr(100,obvious = True)

        self['新泽西护栏'] = Attr(None, show = True)
        
        self.replace()

    @export
    def replace(self):
        down_wide = self['下宽']
        down_high = self['下高']
        up_wide = self['上宽']
        up_high = self['上高']
        L = self['长度']

        a = Section(Vec2(0,0),Vec2(down_high,0),Vec2(down_high+up_high,down_wide/2-up_wide/2),
                    Vec2(down_high+up_high,down_wide/2+up_wide/2),Vec2(down_high,down_wide),
                    Vec2(0,down_wide),Vec2(0,0))
        mian = rotate(Vec3(0,1,0),-pi/2)*a
        all = Loft(mian,trans(L,0,0)*mian)

        self['新泽西护栏'] = all

if __name__ == "__main__":
    FinalGeometry = 新泽西护栏()
    TwoPointPlace.linearize(FinalGeometry, '长度')
    place(FinalGeometry)