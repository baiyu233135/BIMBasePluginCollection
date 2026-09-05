from pyp3d import * 
class 铁轨(Component):

    def __init__(self):
        Component.__init__(self) 
        self['长度'] = Attr(10000,obvious = True)
        self['宽度'] = Attr(1000,obvious = True)
        self['高度'] = Attr(500,obvious = True)
        self['轨枕高度'] = Attr(50,obvious = True)
        self['轨枕长度'] = Attr(100,obvious = True)
        self['轨枕间隔'] = Attr(300,obvious = True)
        
        self['铁轨'] = Attr(None,show = True)
        self.replace()

    @export

    def replace(self):
        L = self['长度']
        W = self['宽度']
        H = self['高度']
        l = self['轨枕长度']
        h = self['轨枕高度']
        long = self['轨枕间隔']
        R = 50
        cone = Cone(Vec3(0,0,0),Vec3(l,0,0),R,R)
        sec_dian = Section(Vec2(0,0),Vec2(l,0),Vec2(l,150),Vec2(0,150),Vec2(0,0))
        dian = Loft(sec_dian,trans(0,0,H/50)*sec_dian)
        zhen = Combine(trans(0,100+R*2,0)*cone,cone,trans(0,R,0)*dian)
        x = (L-l)//(l+long)
        gz = []
        for i in range(x+1):
            gz.append(trans(i*(l+long),W/4-R-150/2,H)*zhen)
            gz.append(trans(i*(l+long),W/4*3-R-150/2,H)*zhen)
        all_gz = Combine(*gz)

        sec_gui = rotate(Vec3(0,0,1),pi/2)*rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(46.83,0),Vec2(46.83,12),Vec2(5.36,16.67),Vec2(5.36,66.67),
                          Vec2(20.4,70.67),Vec2(20.4,93.66),Vec2(-20.4,93.66),Vec2(-20.4,70.67),
                          Vec2(-5.36,66.67),Vec2(-5.36,16.67),Vec2(-46.83,12),Vec2(-46.83,0),Vec2(0,0))
        gui = Loft(sec_gui,trans(L,0,0)*sec_gui)

        sec_d = Section(Vec2(0,0),Vec2(L,0),Vec2(L,W),Vec2(0,W),Vec2(0,0))
        di = Loft(sec_d,trans(0,0,H)*sec_d)

        gui_all = Combine(trans(0,W/2/2,H/50*51)*gui,trans(0,W/4*3,H/50*51)*gui)

        self['铁轨'] = Combine(di,gui_all,all_gz)

if __name__ == "__main__":
    FinalGeometry = 铁轨()
    place(FinalGeometry)
