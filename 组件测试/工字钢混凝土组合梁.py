from pyp3d import *
from math import atan

class 工字钢混凝土组合梁(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为mm
        self['主纵梁长度'] = Attr(9400, obvious=True)
        self['主纵梁顶板宽'] = Attr(90, obvious=True)
        self['主纵梁顶板厚度'] = Attr(3.6, obvious=True)
        self['主纵梁底板宽'] = Attr(150, obvious=True)
        self['主纵梁底板厚度'] = Attr(8, obvious=True)
        self['主纵梁腹板厚度'] = Attr(3.6, obvious=True)
        self['主纵梁梁高'] = Attr(280, obvious=True)


        self['横梁长'] = Attr(2800, obvious=True)
        self['横梁顶板宽'] = Attr(70, obvious=False)
        self['横梁顶板厚度'] = Attr(2.4, obvious=True)
        self['横梁底板宽'] = Attr(70, obvious=True)
        self['横梁底板厚度'] = Attr(2.4, obvious=True)
        self['横梁腹板厚度'] = Attr(1.4, obvious=True)
        self['横梁梁高'] = Attr(280, obvious=True)


        self['小纵梁顶板宽'] = Attr(40, obvious=True)
        self['小纵梁顶板厚度'] = Attr(1.6, obvious=True)
        self['小纵梁底板宽'] = Attr(25, obvious=True)
        self['小纵梁底板厚度'] = Attr(1.6, obvious=True)
        self['小纵梁腹板厚度'] = Attr(1.2, obvious=True)
        self['小纵梁梁高'] = Attr(38.5, obvious=True)

        self['混凝土板厚度'] = Attr(26, obvious=True)


        self['工字钢混凝土组合梁'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L=self['主纵梁长度']
        ZDBW=self['主纵梁顶板宽']
        ZDBH=self['主纵梁顶板厚度']
        ZDBW2=self['主纵梁底板宽']
        ZDBH2=self['主纵梁底板厚度']
        ZFBW=self['主纵梁腹板厚度']
        ZFBH=self['主纵梁梁高']

        HL = self['横梁长']
        HDBW = self['横梁顶板宽']
        HDBH = self['横梁顶板厚度']
        HDBW2 = self['横梁底板宽']
        HDBH2 = self['横梁底板厚度']
        HFBW = self['横梁腹板厚度']
        HFBH = self['横梁梁高']


        SDBW = self['小纵梁顶板宽']
        SDBH = self['小纵梁顶板厚度']
        SDBW2 = self['小纵梁底板宽']
        SDBH2 = self['小纵梁底板厚度']
        SFBW = self['小纵梁腹板厚度']
        SFBH = self['小纵梁梁高']

        HNT=self['混凝土板厚度']


        ZDB =  translate(-ZDBW/2,0,ZFBH-ZDBH) *scale(ZDBW, L, ZDBH) * Cube()
        ZDB2 =  translate(-ZDBW2/2,0,0) *scale(ZDBW2, L, ZDBH2) * Cube()
        ZDB3 =  translate(-ZFBW/2,0,0) *scale(ZFBW, L, ZFBH) * Cube()

        LM = rotate(Vec3(1,0,0),0.5*pi)*Section(Vec2(0,0),
                                                Vec2((ZDBW-ZFBW)/2,0),
                                                Vec2((ZDBW-ZFBW)/2,38.6),
                                                Vec2((ZDBW-ZFBW)/2-13.2,42.2),
                                                Vec2((ZDBW-ZFBW)/2-13.2,ZFBH-ZDBH-ZDBH2),
                                                Vec2(0,ZFBH-ZDBH-ZDBH2))
        NLM= rotate(Vec3(0,0,1),-0.5*pi)*LM
        tline2 = Line(Vec3(0,0,0),Vec3(3.6,0,0))
        sweep = translate(-ZFBW/2,0,ZFBH-ZDBH) *rotate(Vec3(1,0,0),pi)*rotate(Vec3(0,0,1),-0.5*pi)*Sweep(NLM,tline2)
        sweep1 = mirror_yoz() * sweep

        # 计算数量，保证首尾都能放下
        n = max(1, int(L // 200))

        sweep_array = []
        for i in range(n):
            sweep_array.append(
                translate(0, i*200, 0) * sweep
            )
            sweep_array.append(
                translate(0, i*200, 0) * sweep1
            )
        # 末尾再加一个
        sweep_array.append(translate(0, L-3.6, 0) * sweep)
        sweep_array.append(translate(0, L-3.6, 0) * sweep1)
        all_sweep = Combine(*sweep_array)
        ZZL=translate(HL/2+ZDBW/2,-HDBW2/2, 0) *(ZDB2 + ZDB3 + ZDB + all_sweep)  #主纵梁
        ZZL1 = mirror_yoz() * ZZL



        

        HDB =  translate(-HDBW/2,0,HFBH-HDBH) *scale(HDBW, HL, HDBH) * Cube()
        HDB2 =  translate(-HDBW2/2,0,0) *scale(HDBW2, HL, HDBH2) * Cube()
        HDB3 =  translate(-HFBW/2,0,0) *scale(HFBW, HL, HFBH) * Cube()

        HLM = rotate(Vec3(1,0,0),0.5*pi)*Section(Vec2(0,0),
                                                 Vec2((HDBW-HFBW)/2,0),
                                                 Vec2((HDBW-HFBW)/2,35),
                                                 Vec2((HDBW-HFBW)/2-18.3,37.4),
                                                 Vec2((HDBW-HFBW)/2-18.3,HFBH-HDBH-HDBH2),
                                                 Vec2(0,HFBH-HDBH-HDBH2))
        HNLM= rotate(Vec3(0,0,1),-0.5*pi)*HLM
        Htline2 = Line(Vec3(0,0,0),Vec3(14,0,0))
        Hsweep = translate(-HFBW/2,0,HFBH-HDBH) *rotate(Vec3(1,0,0),pi)*rotate(Vec3(0,0,1),-0.5*pi)*Sweep(HNLM,Htline2)
        Hsweep1 = mirror_yoz() * Hsweep

        # 计算数量，保证首尾都能放下
        interval = 180
        n = max(1, int((HL - 1) // interval) + 1)
        center = HL / 2

        Hsweep_array = []
        # 中间的图形
        Hsweep_array.append(translate(0, center, 0) * Hsweep)
        Hsweep_array.append(translate(0, center, 0) * Hsweep1)

        # 向两侧对称复制
        for i in range(1, n):
            offset = i * interval
            # 右侧
            if center + offset <= HL:
                Hsweep_array.append(translate(0, center + offset, 0) * Hsweep)
                Hsweep_array.append(translate(0, center + offset, 0) * Hsweep1)
            # 左侧
            if center - offset >= 0:
                Hsweep_array.append(translate(0, center - offset, 0) * Hsweep)
                Hsweep_array.append(translate(0, center - offset, 0) * Hsweep1)

        Hall_sweep = translate(0, -0.7, 0) *Combine(*Hsweep_array)
        HHL = rotate(Vec3(0,0,1),0.5*pi)*translate(0, -HL/2, 0) *(HDB2 + HDB3 + HDB + Hall_sweep ) # 横梁


        inw = 370
        n = max(1, int(L // inw))

        HHL_array = []
        for i in range(n):
            HHL_array.append(
                translate(0, i*inw, 0) * HHL
            )
        HHL_array.append(translate(0, (L)-HDBW2, 0) * HHL)

        HHL1 = Combine(*HHL_array)


        SDB =  translate(-SDBW/2,0,SFBH-SDBH) *scale(SDBW, L-2*HDBW, SDBH) * Cube()
        SDB2 =  translate(-SDBW2/2,0,0) *scale(SDBW2, L-2*HDBW, SDBH2) * Cube()
        SDB3 =  translate(-SFBW/2,0,0) *scale(SFBW, L-2*HDBW, SFBH) * Cube()

        SZL=translate(0,HDBW/2,ZFBH-SFBH) *(SDB2 + SDB3 + SDB )



        GB =  translate(-HL/2,HDBW/2,ZFBH) *scale(HL, L-2*HDBW, HNT) * Cube()




        result = HHL + ZZL + ZZL1 + HHL1 + SZL + GB
        # result = scale(0.1, 0.1, 0.1) * result
        self['工字钢混凝土组合梁'] = result
if __name__ == "__main__":
    FinalGeometry = 工字钢混凝土组合梁()
    place(FinalGeometry)








