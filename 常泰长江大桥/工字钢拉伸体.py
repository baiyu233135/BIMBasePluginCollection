from pyp3d import *

class 工字钢(Component):
    def __init__(self):
        Component.__init__(self)
        self['总宽度'] = Attr(2200, obvious=True)
        self['总高度'] = Attr(2200, obvious=True)
        self['厚度'] = Attr(10, obvious=True)
        self['长度'] = Attr(34500, obvious=True)
        self['工字钢'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        B = self['总宽度']
        H = self['总高度']
        T = self['厚度']
        L = self['长度']
        
        section = Section(Vec2(0,0),Vec2(B,0),Vec2(B,T),Vec2(B/2+T/2,T),Vec2(B/2+T/2,H-T),Vec2(B,H-T),Vec2(B,H),
                          Vec2(0,H),Vec2(0,H-T),Vec2(B/2-T/2,H-T),Vec2(B/2-T/2,T),Vec2(0,T),Vec2(0,0))
        path = Line(Vec3(0, 0, 0), Vec3(0, 0, L))
        solid = Sweep(section, path)
        solid = rotate(Vec3(1, 0, 0), pi/2) * solid
        self['工字钢'] = solid

if __name__ == "__main__":
    FinalGeometry = 工字钢()
    FinalGeometry.replace()
    place(FinalGeometry)