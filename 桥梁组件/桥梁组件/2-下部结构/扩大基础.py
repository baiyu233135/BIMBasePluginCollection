from pyp3d import *
from math import atan

class 扩大基础(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['扩大基础长'] = Attr(3100, obvious=True)
        self['上层板宽'] = Attr(1055, obvious=True)
        self['下层板宽'] = Attr(1155, obvious=True)
        self['上层板高'] = Attr(100, obvious=True)
        self['下层板高'] = Attr(100, obvious=True)


        self['扩大基础'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):


        ZZL=self['扩大基础长']
        ZZW=self['上层板宽']
        ZZH=self['上层板高']
        ZZW2=self['下层板宽']
        ZZH2=self['下层板高']



        ZSM = translate(-ZZL/2,-ZZW2/2,ZZH2) * scale(ZZL,ZZW, ZZH) * Cube()
        ZXM = translate(-ZZL/2,-ZZW2/2,0) * scale(ZZL,ZZW2, ZZH2) * Cube()


        self['扩大基础'] =  ZSM + ZXM
if __name__ == "__main__":
    FinalGeometry = 扩大基础()
    place(FinalGeometry)