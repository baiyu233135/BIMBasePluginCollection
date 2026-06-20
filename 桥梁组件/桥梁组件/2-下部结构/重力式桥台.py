from pyp3d import *
from math import atan

class 重力式桥台(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['桥台宽度'] = Attr(2900, obvious=True)
        self['上背宽'] = Attr(502, obvious=False)
        self['上背高'] = Attr(355, obvious=True)

        self['下背宽'] = Attr(100, obvious=False)
        self['下背高'] = Attr(530, obvious=True)

        self['台帽高'] = Attr(80, obvious=True)
        self['台帽宽'] = Attr(448, obvious=True)


        self['右下底长'] = Attr(363, obvious=False)
        self['右上底长'] = Attr(75, obvious=False)
        self['右宽'] = Attr(935, obvious=False)


        self['挡墙高'] = Attr(75, obvious=False)
        self['挡墙长'] = Attr(78, obvious=False)
        self['挡墙间隔'] = Attr(2138, obvious=False)


        self['重力式桥台'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):


        BL=self['桥台宽度']
        SBW=self['上背宽']
        SBH=self['上背高']
        XBW=self['下背宽']
        XBH=self['下背高']
        TW = self['台帽宽']
        TH = self['台帽高']

        YDL = self['右下底长']
        YSL = self['右上底长']
        H = SBH+XBH+TH
        YW = TW+487


        section1 = translate(0, BL/2, 0) *Section(Vec2(0,-YDL), Vec2(0, 0), Vec2(H, 0), Vec2(H, -YSL))
        Ybody = translate(0, 0,0) *rotate(Vec3(0,0,1), 1.5*pi) * rotate(Vec3(0,1,0), -0.5*pi) * Loft(section1, translate(0,0,YW)*section1)
    


        SB = translate(-BL/2,0,XBH) * scale(BL,SBW, SBH+TH) * Cube()
        XB = translate(-BL/2,0,0) * scale(BL,XBW, XBH) * Cube()
        TM = translate(-BL/2,502,XBH) * scale(BL,TW, TH) * Cube()

        interval = 250  # 固定间隔
        n = max(5, int(((BL-363.14)/2 - 1) // interval) + 1)
        Q_array = []
        for i in range(max(0, n-1)):
            Q_array.append(
                translate(1450/2, 502+158 + i*interval, XBH+TH) * scale(100, 100, 20) * Cube()
            )
        Q = translate(1320/2-150/2-25, 0, 0) * rotate(Vec3(0,0,1), 0.5*pi) * Combine(*Q_array)




        interval = 1100  # 固定间隔
        n = max(1, int(((BL) - 1) // interval) - 2)

        XZ_array = []
        XZ1_array = []
        SZ_array = []
        SZ1_array = []

        for i in range(n):
            x_pos = 1500/2 + i*interval
            if x_pos > BL/2-525-26:
                break  # 超出BL/2则不再添加
            # XZ
            XZ_array.append(
                translate(x_pos, 100, 0) * scale(200, TW+203, XBH-100) * Cube()
            )
            # XZ1
            x1_pos = 520/2 + i*interval
            if x1_pos > BL/2-525-26:
                continue  # 超出BL/2则不再添加
            XZ1_array.append(
                translate(x1_pos, 100, 0) * scale(80, TW+203, XBH-100) * Cube()
            )
            # SZ
            se = translate(x_pos, 100, XBH-100) * Section(Vec2(0, TW+203), Vec2(0, 0), Vec2(200, 0), Vec2(200, TW+203))
            se1 = translate(1450/2 + i*interval, 100, XBH-100) * Section(Vec2(0, TW+203), Vec2(0, 0), Vec2(250, 0), Vec2(250, TW+203))
            if x_pos <= BL/2:
                SZ_array.append(Loft(se, translate(0, 0, 100) * se1))
            # SZ1
            Xe = translate(x1_pos, 100, XBH-100) * Section(Vec2(0, TW+203), Vec2(0, 0), Vec2(80, 0), Vec2(80, TW+203))
            Xe1 = translate(470/2 + i*interval, 100, XBH-100) * Section(Vec2(0, TW+203), Vec2(0, 0), Vec2(130, 0), Vec2(130, TW+203))
            if x1_pos <= BL/2:
                SZ1_array.append(Loft(Xe, translate(0, 0, 100) * Xe1))

        XZ = Combine(*XZ_array)
        XZ1 = Combine(*XZ1_array)
        SZ = Combine(*SZ_array)
        SZ1 = Combine(*SZ1_array)

        ww = XZ1 + SZ1
        ww1 = XZ + SZ
    

        DQ1 = mirror_yoz() * ( Ybody+ww+ww1 +Q)

        self['重力式桥台'] =   SB + XB + TM + DQ1 + Ybody +ww +ww1 + Q
if __name__ == "__main__":
    FinalGeometry = 重力式桥台()
    place(FinalGeometry)