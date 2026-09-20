from pyp3d import *

class 门式桥墩(Component):
    def __init__(self):
        Component.__init__(self)
        self['底面长'] = Attr(14000, obvious = True)
        self['底面宽'] = Attr(12000, obvious = True)
        self['顶面长'] = Attr(12000, obvious = True)
        self['顶面宽'] = Attr(10000, obvious = True)
        self['柱高'] = Attr(50000, obvious = True)
        self['垫石长'] =Attr(4000,obvious = True)
        self['垫石宽'] =Attr(4000,obvious = True)
        self['垫石高'] =Attr(800,obvious = True)
        self['系梁长'] =Attr(35000,obvious = True)
        self['系梁宽'] =Attr(4000,obvious = True)
        self['系梁高'] =Attr(4000,obvious = True)

        self['门式桥墩'] = Attr(None, show = True)
        
        self.replace()

    @export
    def replace(self):
        BL = self['底面长']
        BW = self['底面宽']
        TL = self['顶面长']
        TW = self['顶面宽']
        H = self['柱高']
        DSL = self['垫石长']
        DSW = self['垫石宽']
        DSH = self['垫石高']
        JL = self['系梁长']
        JW = self['系梁宽']
        JH = self['系梁高']

        BD = BW/4
        TD = TL/4
        DM = Section(Vec2(BD-BL/2,-BW/2),Vec2(BL/2-BD,-BW/2),Vec2(BL/2,BD-BW/2),
                     Vec2(BL/2,BW/2-BD),Vec2(BL/2-BD,BW/2),Vec2(BD-BL/2,BW/2),
                     Vec2(-BL/2,BW/2-BD),Vec2(-BL/2,BD-BW/2),Vec2(BD-BL/2,-BW/2))
        TM = Section(Vec2(TD-TL/2,-TW/2),Vec2(TL/2-TD,-TW/2),Vec2(TL/2,TD-TW/2),
                     Vec2(TL/2,TW/2-TD),Vec2(TL/2-TD,TW/2),Vec2(TD-TL/2,TW/2),
                     Vec2(-TL/2,TW/2-TD),Vec2(-TL/2,TD-TW/2),Vec2(TD-TL/2,-TW/2))
        DS = trans(-DSL/2,-DSW/2,H)*scale(DSL,DSW,DSH)*Cube()
        ZH1 = Combine(Loft(DM,trans(0,0,H)*TM), DS)
        ZH2 = trans(JL+TL,0,0)*ZH1
        ZH = Combine(ZH1, ZH2)
        
        JI = trans(TL/2,-JW/2,H-JH)*scale(JL,JW,JH)*Cube()

        self['门式桥墩'] = Combine(ZH, JI)

if __name__ == "__main__":
    FinalGeometry = 门式桥墩()
    FinalGeometry.replace()
    place(FinalGeometry)