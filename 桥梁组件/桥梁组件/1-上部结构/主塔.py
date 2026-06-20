from pyp3d import *
from math import atan

class 主塔(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['主塔支座长'] = Attr(1450, obvious=True)
        self['主塔支座宽'] = Attr(1700, obvious=True)
        self['主塔支座高'] = Attr(200, obvious=True)

        self['主塔柱宽'] = Attr(850, obvious=True)
        self['主塔下柱厚度'] = Attr(1100, obvious=True)
        self['主塔下柱高度'] = Attr(7090, obvious=True)

        self['主塔上柱厚度'] = Attr(750, obvious=True)
        self['主塔上柱高度'] = Attr(6800, obvious=True)

        self['主塔中柱高度'] = Attr(6350, obvious=True)

        self['下横梁高'] = Attr(700, obvious=False)
        self['下横梁长'] = Attr(3360, obvious=True)
        self['下横梁宽'] = Attr(750, obvious=False)

        self['支柱高'] = Attr(600, obvious=False)

        self['主塔'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):


        ZZL=self['主塔支座长']
        ZZW=self['主塔支座宽']
        ZZH=self['主塔支座高']


        ZXH=self['主塔下柱高度']
        ZXL=self['主塔柱宽']
        ZXW=self['主塔下柱厚度']
        ZH=self['主塔中柱高度']
        ZSH=self['主塔上柱高度']
        ZSW=self['主塔上柱厚度']

        QL=self['下横梁长']
        QW=self['下横梁宽']
        QH=self['下横梁高']


        zH=self['支柱高']







        # 主塔支座
        ZZX = Section(Vec2(ZZL/2,-ZZW/2), Vec2(ZZL/2,ZZW/2),Vec2(-ZZL/2,ZZW/2), Vec2(-ZZL/2,-ZZW/2))
        ZZS = Section(Vec2(ZZL/2-100,-ZZW/2+200), Vec2(ZZL/2-100,ZZW/2-200),Vec2(-ZZL/2+100,ZZW/2-200), Vec2(-ZZL/2+100,-ZZW/2+200))
        loft = translate(0,0,-ZZH)* Loft(ZZX, translate(0,0,ZZH) * ZZS)
        # 主塔下部
        ZXX = Section(Vec2(ZXL/2,-ZXW/2), Vec2(ZXL/2,ZXW/2),Vec2(-ZXL/2,ZXW/2), Vec2(-ZXL/2,-ZXW/2))
        ZXS = Section(Vec2(ZXL/2-100,-ZXW/2+92.3), Vec2(ZXL/2-100,ZXW/2-92.3),Vec2(-ZXL/2+100,ZXW/2-92.3), Vec2(-ZXL/2+100,-ZXW/2+92.3))
        loft1 = Loft(ZXX, translate(7090/9.407,0,ZXH) * ZXS)

        ZS = Section(Vec2(ZXL/2-100-25,-ZSW/2), Vec2(ZXL/2-100-25,ZSW/2),Vec2(-ZXL/2+100+25,ZSW/2), Vec2(-ZXL/2+100+25,-ZSW/2))
        loft2 = translate(7090/9.407,0,ZXH)* Loft(ZXS, translate(-6350/10.16,0,ZH) * ZS)

        loft3 = translate(7090/9.407-6350/10.16,0,ZXH+ZH)* Loft(ZS, translate(0,0,ZSH-300) * ZS)

        ZS1 = Section(Vec2(ZXL/2-100-25,-ZSW/2), Vec2(ZXL/2-100-25,ZSW/2),Vec2(-ZXL/2+100+25+100,ZSW/2), Vec2(-ZXL/2+100+25+100,-ZSW/2))
        ZS2 = Section(Vec2(50,-ZSW/2), Vec2(50,ZSW/2),Vec2(-50,ZSW/2), Vec2(-50,-ZSW/2))
        loft4 = translate(7090/9.407-6350/10.16,0,ZXH+ZH+ZSH-300)* Loft(ZS1, translate(ZXL/2-175,0,300) * ZS2)

        zzz=translate(QL/2-528.65,0,0)*( loft + loft1 + loft2 + loft3 + loft4)
        body1 = mirror_yoz()*zzz



        QM = translate(-QL/2, -QW/2, ZXH-200) * scale(QL,QW, QH) * Cube()

        zM = translate(-(QL-1250)/2, -ZSW/2, ZXH+ZH-250) * scale(QL-1250,ZSW, zH) * Cube()
  
  



        self['主塔'] =body1 + zzz + QM + zM
if __name__ == "__main__":
    FinalGeometry = 主塔()
    place(FinalGeometry)