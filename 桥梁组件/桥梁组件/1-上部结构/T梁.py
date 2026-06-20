from pyp3d import *
from math import atan

class T梁(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['长'] = Attr(3000, obvious=True)

        self['底板宽'] = Attr(60, obvious=True)
        self['底板高'] = Attr(35, obvious=True)

        self['右翼缘宽'] = Attr(30, obvious=True)
        self['左翼缘宽'] = Attr(30, obvious=True)
        self['顶右宽'] = Attr(60, obvious=False)
        self['腹板宽'] = Attr(20, obvious=True)

        self['总高'] = Attr(250, obvious=True)

        self['T梁'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):

        L=self['长']
        DW=self['底板宽']
        DH=self['底板高']
        TZW=self['右翼缘宽']
        TZW2=self['左翼缘宽']
        TYW=self['顶右宽']
        TH=self['腹板宽']
        H=self['总高']





        DB = translate(-DW/2, 0, 0) * scale(DW, L, DH) * Cube()

        Z = translate(-TH/2, 0,2*DH-10 ) * scale(TH, L, H-60) * Cube()




        Z1 = translate(-TYW+120+TH/2,0,2*DH-10+H-60-8.5-4 -3.5) * scale(TZW, L, 16) * Cube()
        Z11 = rotate(Vec3(0,0,0),pi) *translate(-TYW-TH/2,0,2*DH-10+H-60-8.5-4 -3.5) * scale(-TZW2, L, 16) * Cube()




        # 描述截面
        EQ = Section(Vec2(16/2,-L/2), Vec2(16/2,L/2),Vec2(-16/2,L/2), Vec2(-16/2,-L/2))
        EQ1 = Section(Vec2((16+9)/2,-L/2), Vec2((16+9)/2,L/2),Vec2(-(16+9)/2,L/2), Vec2(-(16+9)/2,-L/2))
        loft1 = translate(-TH/2,L/2,2*DH-10+H-60-8.5-4)*rotate(Vec3(0,1,0), 0.5*pi) * Loft(EQ1, translate(-4.5,0,-TYW) * EQ)


        DQ1 = mirror_yoz() * (loft1 )




        ZX = Section(Vec2(DW/2,-L/2), Vec2(DW/2,L/2),Vec2(-DW/2,L/2), Vec2(-DW/2,-L/2))
        ZS = Section(Vec2(DW/2-20,-L/2), Vec2(DW/2-20,L/2),Vec2(-DW/2+20,L/2), Vec2(-DW/2+20,-L/2))
        loft = translate(0,L/2,DH)* Loft(ZX, translate(0,0,DH-10) * ZS)


        hou = 15
        zy = 52.5
        j = 720
        start = zy
        end = L - zy - hou
        span = end - start
        if 2640 <= L <= 3360:
            count = 5
        else:
            count = 5 + max(0, int((L - 3360) // j)+1)
        if count < 2:
            count = 2
        if count == 1:
            gap = 0
        else:
            gap = span / (count - 1)

        ww_array = []
        ww1_array = []
        if TZW2 == TZW:
            for i in range(count):
                x = start + i * gap
                ww_array.append(translate(0, x - start, 0) * translate(10, 52.5, 10) * scale(TZW+TYW, 15, H-10) * Cube())
                ww1_array.append(translate(0, x - start, 0) * rotate(Vec3(0,0,1), pi) * translate(10, -67.5, 10) * scale(TZW2+TYW, 15, H-10) * Cube())
        elif TZW2 < TZW:
            for i in range(count):
                x = start + i * gap           
                ww1_array.append(translate(0, x - start, 0) * rotate(Vec3(0,0,1), pi) * translate(10, -67.5, 10) * scale(TZW2+TYW, 15, H-10) * Cube())
        else:
            for i in range(count):
                x = start + i * gap
                ww_array.append(translate(0, x - start, 0) * translate(10, 52.5, 10) * scale(TZW+TYW, 15, H-10) * Cube())            
        ww = Combine(*ww_array)
        ww1 = Combine(*ww1_array)
    

        self['T梁'] = loft1 + DQ1 + loft + DB + Z + Z1 + Z11 + ww + ww1
if __name__ == "__main__":
    FinalGeometry = T梁()
    place(FinalGeometry)