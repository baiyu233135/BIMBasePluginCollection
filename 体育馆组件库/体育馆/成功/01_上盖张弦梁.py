from pyp3d import *

class 上盖张弦梁(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(94154.76, obvious=True)
        self['高度'] = Attr(8432.03, obvious=True)
        self['截面长'] = Attr(482.37, obvious=True)
        self['截面宽'] = Attr(492.13, obvious=True)

        self['上盖张弦梁'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['高度']
        JL = self['截面长']
        JW = self['截面宽']
        unit_long = L/94154.76*59649.79/10
        start = L/94154.79*(94154.76-55886.79)
        unit_1 = H/8432.03*4234.92
        unit_2 = H/8432.03*5332.66
        unit_3 = H/8432.03*6268.79
        unit_4 = H/8432.03*6953.95
        unit_5 = H/8432.03*7357.44
        unit_6 = H/8432.03*7447.78
        unit = [unit_1,unit_2,unit_3,unit_4,unit_5,unit_6]

        Up_midhigh = H/8432.03*2195.45
        Up_midlong =  L/94154.76*15903.04
        Up_midahigh =  H/8432.03*2686.89

        a =  L/94154.76*5604.47

        OUT_Section = Section(Vec2(0,0),Vec2(L,0),Vec2(L,JW),Vec2(a,JW),
                              Arc(Vec2(a,JW),Vec2(Up_midlong,Up_midhigh),Vec2(L,H-JW)),
                              Vec2(L,H),Arc(Vec2(L,H),Vec2(Up_midlong,Up_midahigh),Vec2(0,0)))
        out_Section = rotate(Vec3(1,0,0),pi/2)*OUT_Section
        
        under = trans(start,0,JW)*Section(Vec2(0,0),Vec2(JW,0),Vec2(JW,JW),Vec2(0,JW),Vec2(0,0))
        xie = []
        for i in range(5):
            xie.append(Loft(trans(unit_long*2*i)*under,trans(unit_long*2*i-unit_long,0,unit[i])*under))
            xie.append(Loft(trans(unit_long*2*i)*under,trans(unit_long*i*2+unit_long,0,unit[i+1])*under))
        xie_all = Combine(*xie)

        self['上盖张弦梁'] = Combine(xie_all,out_Section)

if __name__ == "__main__":
    FinalGeometry = 上盖张弦梁()
    FinalGeometry.replace()
    place(FinalGeometry)