from pyp3d import *

class 中部桁架(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(35442.83, obvious=True)
        self['左侧高度'] = Attr(1092.52, obvious=True)
        self['右侧高度'] = Attr(3061.02, obvious=True)
        self['截面边长'] = Attr(400, obvious=True)

        self['中部桁架'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        LH = self['左侧高度']
        RH = self['右侧高度']
        B = self['截面边长']
        mid_x = L/35442.83*17401.85
        mid_y = LH/1092.52*2271.24
        out_sec = Section(Vec2(0,0),Vec2(L,0),Vec2(L,B),Vec2(B,B),Vec2(LH-B,B),
                          Arc(Vec2(LH-B,B),Vec2(mid_x,mid_y),Vec2(L,RH-B)),Vec2(L,RH),
                          Arc(Vec2(L,RH),Vec2(mid_x,mid_y+B),Vec2(0,LH)),Vec2(0,0))
        out_main = rotate(Vec3(1,0,0),pi/2)*Loft(out_sec,trans(0,0,B)*out_sec)

        under = Section(Vec2(0,0),Vec2(B,0),Vec2(B,B),Vec2(0,B),Vec2(0,0))
        x1 = (RH+LH)/(1092.52+3061.02)
        unit_h1 = x1*1000
        unit_h2 = x1*1697.96
        unit_h3 = x1*2050.52
        unit_h4 = x1*2322.63
        unit_h5 = x1*2511.52
        unit_h6 = x1*2661.02
        unit_long = (L-B)/10
        unit = [unit_h1,unit_h2,unit_h3,unit_h4,unit_h5,unit_h6]
        xie = []
        for i in range(5):
            if i <=3:
                xie.append(Loft(trans(unit_long*2*(i+1),0,0)*under,trans(unit_long*2*(i+1)-unit_long,0,unit[i])*under))
                xie.append(Loft(trans(unit_long*2*(i+1),0,0)*under,trans(unit_long*(i+1)*2+unit_long,0,unit[i+1])*under))
            else:
                xie.append(Loft(trans(unit_long*2*(i+1))*under,trans(unit_long*2*(i+1)-unit_long,0,unit[i])*under))
        xie_all = trans(0,-B,B)*Combine(*xie)

        self['中部桁架'] = Combine(out_main,xie_all) 

if __name__ == "__main__":
    FinalGeometry = 中部桁架()
    FinalGeometry.replace()
    place(FinalGeometry)