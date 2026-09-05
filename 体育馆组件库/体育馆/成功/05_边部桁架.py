from pyp3d import *

class 边部桁架(Component):
    def __init__(self):
        Component.__init__(self)
        self['横截面边长'] = Attr(196.85, obvious=True)
        self['高度'] = Attr(1409.85, obvious=True)
        self['架子间距'] = Attr(1377.95,obvious = True)
        self['长度'] = Attr(35396.43, obvious=True)

        self['边部桁架'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['高度']
        B = self['横截面边长']
        K = self['架子间距']
        long1 = L/35396.43*33860.14
        long2 = L/35396.43*28297.35
        high = H /1409.85 * 618.01
        under = Section(Vec2(0,0),Vec2(B,0),Vec2(B,B),Vec2(0,B),Vec2(0,0))
        unit_pillar11 = Loft(under,trans(K,long2/6*1/2,H)*under)
        unit_pillar12 = Loft(under,trans(K,-long2/6*1/2,H)*under)
        unit_pillar13 = Loft(under,trans(-K,long2/6*1/2,H)*under)
        unit_pillar14 = Loft(under,trans(-K,-long2/6*1/2,H)*under)
        unit_pillar1 = Combine(unit_pillar11,unit_pillar12,unit_pillar13,unit_pillar14)
        unit_pillar21 = Loft(under,trans(K,(long1-long2)/2,H+high)*under)
        unit_pillar22 = Loft(under,trans(K,-(long1-long2)/2,H+high)*under)
        unit_pillar23 = Loft(under,trans(-K,(long1-long2)/2,H+high)*under)
        unit_pillar24 = Loft(under,trans(-K,-(long1-long2)/2,H+high)*under)
        unit_pillar2 =trans(0,long2,-high)*Combine(unit_pillar21,unit_pillar22,unit_pillar23,unit_pillar24)
        under1 = rotate(Vec3(1,0,0),pi/2)*under
        pillar3 = trans(0,long2/12*11,0)*Loft(under1,trans(0,L/35396.43*7999,-H/1409.85*2027)*under1)

        unit_pillar = unit_pillar1
        pillar1_unit =rotate(Vec3(1,0,0),pi/2)*Loft(under,trans(0,0,-long1)*under)
        pillar1 = Combine(trans(-K,-long2/12,H)*pillar1_unit,trans(K,-long2/12,H)*pillar1_unit)
        pillar2 = trans(0,-long2/12,0)*rotate(Vec3(1,0,0),pi/2)*Loft(under,trans(0,0,-long2)*under)
        for i in range(5):
            i = i + 1
            unit_pillar = Combine(unit_pillar,trans(0,long2/6*i-B,0)*unit_pillar1)

        pillar = pillar1 + unit_pillar + pillar1 + pillar2 + unit_pillar2 + pillar3
        self['边部桁架'] = pillar

if __name__ == "__main__":
    FinalGeometry = 边部桁架()
    FinalGeometry.replace()
    place(FinalGeometry)