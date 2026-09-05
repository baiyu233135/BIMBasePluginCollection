from pyp3d import *

class 中屋盖(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(93662.64, obvious=True)
        self['宽度'] = Attr(35442.83,obvious = True)
        self['厚度'] = Attr(875.99, obvious=True)
        self['底柱高'] = Attr(293.69,obvious = True)

        self['中屋盖'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        W = self['宽度']
        M = self['厚度']
        H = self['底柱高']
        mid_x1 = W/35442.83*22132.79
        mid_y1 = M/875.99*1812.77
        mid_x2 = W/35442.83*20323.29
        mid_y2 = M/875.99*2598.24
        long1 = L/93662.64*13310.24
        long2 = L/93662.64*81435.08
        end_y = H/875.99*2185.04
        under1 = Section(Vec2(0,0),Vec2(M,0),Vec2(M,H),
                         Arc(Vec2(M,H),Vec2(mid_x1,mid_y1),Vec2(W,end_y)),
                         Vec2(W,end_y),Vec2(W,end_y+M),
                         Arc(Vec2(W,end_y+M),Vec2(mid_x2,mid_y2),Vec2(0,M+H)),Vec2(0,0))
        section1 = rotate(Vec3(1,0,0),pi/2)*Loft(under1,trans(0,0,-long1)*under1)
        section2 = rotate(Vec3(1,0,0),pi/2)*Loft(under1,trans(0,0,-long2)*under1)
        all = section1 + trans(0,long1-(long1+long2-L),M)*section2

        self['中屋盖'] = all

if __name__ == "__main__":
    FinalGeometry = 中屋盖()
    FinalGeometry.replace()
    place(FinalGeometry)