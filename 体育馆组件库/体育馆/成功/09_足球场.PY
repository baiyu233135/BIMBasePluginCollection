from pyp3d import *

class 足球场(Component):
    def __init__(self):
        Component.__init__(self)
        self['草皮长'] = Attr(105039.38, obvious=True)
        self['草皮宽'] = Attr(74549.09, obvious=True)
        self['场长'] = Attr(99147.57,obvious = True)
        self['场宽'] = Attr(67590.83, obvious=True)
        self['线厚度'] = Attr(10, obvious=True)
        self['角杆半径'] = Attr(30, obvious=True)
        self['角杆高'] = Attr(600, obvious=True)

        self['足球场'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['场长']
        W = self['场宽']
        l = self['草皮长']
        w = self['草皮宽']
        H = self['线厚度']
        R = self['角杆半径']
        high = self['角杆高']

        DR = 453.68/2
        MR_O = 17285.4/2
        R_I = 17091.68/2
        x3 = L/99147.57*10355.44
        N = 64
        circle_mro = [
            Vec2(MR_O * cos(2 * pi * i / N), MR_O * sin(2 * pi * i / N))
            for i in range(N)
        ]
        sec_mro = Section(*circle_mro)
        circle_ri = [
            Vec2(R_I * cos(2 * pi * i / N), R_I * sin(2 * pi * i / N))
            for i in range(N)
        ]
        sec_ri = Section(*circle_ri)
        circle_middle = Loft(sec_mro,trans(0,0,H+10)*sec_mro)-Loft(sec_ri,trans(0,0,H+10)*sec_ri)
        circle_out = Cone(Vec3(0,0,0),Vec3(0,0,H+10),DR,DR)

        outcir_all = Combine(trans(l/2-L/2+x3,w/2,0)*circle_out,trans(l/2+L/2-x3,w/2,0)*circle_out)
        g = Cone(Vec3(0,0,0),Vec3(0,0,H+high),R,R)

        ql = L/99147.57*7828.13
        qh = 2712.19
        qw = W/67590.83*2410.16
        x1 = L/99147.57*5185.61
        y1 = W/67590.83*18176.4
        x2 = L/99147.57*15556.87
        y2 = W/67590.83*40015.58

        y_arc = W/67590.83*14346.50
        x_arc = L/99147.57*3553.11
        A = 100.98
        cao_sec = Section(Vec2(0,0),Vec2(l/20,0),Vec2(l/20,w),Vec2(0,w),Vec2(0,0))
        cao1 = Loft(cao_sec,trans(0,0,H)*cao_sec)
        cao2 = Loft(cao_sec,trans(0,0,H)*cao_sec)
        cao_q = cao1.color(0,0.4,0,1)
        cao_s = cao2.color(0,0.6,0,1)
        cao_unit = []
        for i in range(20):
            if(i%2==0):
                cao_unit.append(trans(i*l/20,0,0)*cao_q)
            else:
                cao_unit.append(trans(i*l/20,0,0)*cao_s)
        cao_all = Combine(*cao_unit)

        kuai_sec = rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(qw,0),Vec2(qw,qh),Vec2(0,qh),Vec2(0,0))
        cmen_sec = rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(qw-25,0),Vec2(qw-25,qh-25),Vec2(0,qh-25),Vec2(0,0))
        cmen = trans(25,25,0)*Loft(cmen_sec,trans(0,ql-50,0)*cmen_sec)
        kuai = Loft(kuai_sec,trans(0,ql,0)*kuai_sec)
        men = kuai - cmen
        men_all = Combine(trans(l/2-L/2-qw,w/2-ql/2,H)*men,trans(l/2+L/2,w/2-ql/2,H)*men)

        outk_sec = Section(Vec2(0,0),Vec2(L,0),Vec2(L,W),Vec2(0,W),Vec2(0,0))
        ink_sec = Section(Vec2(0,0),Vec2(L-2*A,0),Vec2(L-2*A,W-2*A),Vec2(0,W-2*A),Vec2(0,0))
        outk = Loft(outk_sec,trans(0,0,H+10)*outk_sec)
        ink = Loft(ink_sec,trans(0,0,H+10)*ink_sec)
        kuang = outk-trans(A,A,0)*ink

        zh1kuai_sec = Section(Vec2(0,0),Vec2(x1,0),Vec2(x1,y1),Vec2(0,y1),Vec2(0,0))
        czh1_sec = Section(Vec2(0,0),Vec2(x1-2*A,0),Vec2(x1-2*A,y1-2*A),Vec2(0,y1-2*A),Vec2(0,0))
        zh1kuai = Loft(zh1kuai_sec,trans(0,0,H+10)*zh1kuai_sec)
        czh1 = Loft(czh1_sec,trans(0,0,H+10)*czh1_sec)
        zh1 = zh1kuai - trans(A,A,0)*czh1
        zh1_all = Combine(trans(l/2-L/2,w/2-y1/2,0)*zh1,trans(l/2+L/2-x1,w/2-y1/2,0)*zh1)

        midkuai_sec = Section(Vec2(0,0),Vec2(x2,0),Vec2(x2,y2),Vec2(0,y2),Vec2(0,0))
        cmid_sec =  Section(Vec2(0,0),Vec2(x2-2*A,0),Vec2(x2-2*A,y2-2*A),Vec2(0,y2-2*A),Vec2(0,0))
        midkuai = Loft(midkuai_sec,trans(0,0,H+10)*midkuai_sec)
        cmid = Loft(cmid_sec,trans(0,0,H+10)*cmid_sec)
        mid = midkuai - trans(A,A,0)*cmid
        mid_all = Combine(trans(l/2-L/2,w/2-y2/2,0)*mid,trans(l/2+L/2-x2,w/2-y2/2,0)*mid)

        arc_sec_left = Section(Vec2(0,0),Arc(Vec2(0,0),Vec2(x_arc,y_arc/2),Vec2(0,y_arc)),
                          Vec2(0,y_arc),Vec2(0,y_arc-A),
                          Arc(Vec2(0,y_arc-A),Vec2(x_arc-A,y_arc/2),Vec2(0,A)),Vec2(0,0))
        arc_left = Loft(arc_sec_left,trans(0,0,H+10)*arc_sec_left)
        arc_sec_right =Section(Vec2(0,0),Arc(Vec2(0,0),Vec2(-x_arc,y_arc/2),Vec2(0,y_arc)),
                          Vec2(0,y_arc),Vec2(0,y_arc-A),
                          Arc(Vec2(0,y_arc-A),Vec2(-x_arc+A,y_arc/2),Vec2(0,A)),Vec2(0,0))
        arc_right = Loft(arc_sec_right,trans(0,0,H+10)*arc_sec_right)
        arc_all = Combine(trans(l/2-L/2+x2,w/2-y_arc/2,0)*arc_left,trans(l/2+L/2-x2,w/2-y_arc/2,0)*arc_right)

        mid_line_sec = Section(Vec2(0,0),Vec2(A,0),Vec2(A,W),Vec2(0,W),Vec2(0,0))
        mid_line = Loft(mid_line_sec,trans(0,0,H+10)*mid_line_sec)

        line_all = Combine(trans(l/2-L/2,w/2-W/2,0)*kuang,zh1_all,mid_all,arc_all,
                           trans(l/2-A/2,w/2-W/2,0)*mid_line,trans(l/2,w/2,0)*circle_middle,
                           outcir_all)
        
        qi = Combine(trans(l/2-L/2,w/2-W/2,0)*g,trans(l/2+L/2,w/2-W/2,0)*g,
                     trans(l/2-L/2,w/2+W/2,0)*g,trans(l/2+L/2,w/2+W/2,0)*g)

        self['足球场'] = Combine(cao_all,men_all,line_all,qi)

if __name__ == "__main__":
    FinalGeometry = 足球场()
    FinalGeometry.replace()
    place(FinalGeometry)