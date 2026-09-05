from pyp3d import *

class 边屋盖(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(94154.76, obvious=True)
        self['宽度'] = Attr(45414.79,obvious = True)
        self['高度'] = Attr(2391.73, obvious=True)
        self['厚度'] = Attr(590.55, obvious=True)

        self['边屋盖'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['高度']
        W = self['宽度']
        M = self['厚度']
        unit_w1 = W/45414.79*1466.63
        unit_w2 = W/45414.79*6297.22
        unit_w3 = W/45414.79*40109.57
        unit_w4 = W/45414.79*45414.78

        MAN = Section(Vec2(0,M/2),Vec2(unit_w1,0),Vec2(unit_w2,0),Vec2(unit_w3,H-M),
                      Vec2(unit_w4,H-M),Vec2(unit_w4,H),Vec2(unit_w3,H),Vec2(unit_w2,M),
                      Vec2(unit_w1,M),Vec2(0,M/2))
        All_1 = rotate(Vec3(1,0,0),pi/2)*MAN
        All_2 = Loft(All_1,trans(0,L,0)*All_1)
        cut_long1 = L/94154.76*55411.25
        cut_long2 = L/94154.76*72014.75
        cut_long3 = L/94154.76*89219.56
        cut_high1 =W/45414.79*37034.32
        cut_high2 =W/45414.79*19446.81
        cut_high3 =W/45414.79*3416.39
        cut_down1 = Section(Vec2(0,0),Vec2(cut_high1,0),Vec2(cut_high2,L-cut_long3),Vec2(0,0))
        cut_down2 = Section(Vec2(0,0),Vec2(cut_high2,L-cut_long3),Vec2(cut_high3,L-cut_long2),Vec2(0,0))
        cut_down3 = Section(Vec2(0,0),Vec2(cut_high3,L-cut_long2),Vec2(0,L-cut_long1),Vec2(0,0))
        cut_1 = Loft(cut_down1,trans(0,0,H)*cut_down1)
        cut_2 = Loft(cut_down2,trans(0,0,H)*cut_down2)
        cut_3 = Loft(cut_down3,trans(0,0,H)*cut_down3)
        cut = Combine(cut_1,cut_2,cut_3)
        All = All_2 - cut 

        self['边屋盖'] = All

if __name__ == "__main__":
    FinalGeometry = 边屋盖()
    FinalGeometry.replace()
    place(FinalGeometry)