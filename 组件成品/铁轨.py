from pyp3d import * 
class 铁轨(Component):

    def __init__(self):
        Component.__init__(self) 
        self['长度'] = Attr(10000,obvious = True)
        self['宽度'] = Attr(2500,obvious = True)
        self['高度'] = Attr(200,obvious = True)
        self['轨枕高度'] = Attr(10,obvious = True)
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
        dl = 5575
        y = int(L//(dl+long))

        R = 130
        cone = Cone(Vec3(0,0,0),Vec3(l,0,0),R,R)
        sec_dian = Section(Vec2(0,0),Vec2(l,0),Vec2(l,l+R),Vec2(0,l+R),Vec2(0,0))
        dian = Loft(sec_dian,trans(0,0,h)*sec_dian)
        zhen = Combine(trans(0,100+R*2,0)*cone,cone,trans(0,R/2,0)*dian)
        gz = []
        for i in range(int((L+(y+1)*25)//(l+long)+1)):
            gz.append(trans(i*(l+long),W/4-R-150/2,H)*zhen)
            gz.append(trans(i*(l+long),W/4-R-150/2,H/50*51)*dian)
            gz.append(trans(i*(l+long),W/4*3-R-150/2,H)*zhen)
        all_gz = Combine(*gz)

        sec_gui = rotate(Vec3(0,0,1),pi/2)*rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(46.83,0),Vec2(46.83,12),Vec2(5.36,16.67),Vec2(5.36,66.67),
                          Vec2(20.4,70.67),Vec2(20.4,93.66),Vec2(-20.4,93.66),Vec2(-20.4,70.67),
                          Vec2(-5.36,66.67),Vec2(-5.36,16.67),Vec2(-46.83,12),Vec2(-46.83,0),Vec2(0,0))
        gui = Loft(sec_gui,trans(L+(y+1)*25,0,0)*sec_gui)

        sec_d = Section(Vec2(0,0),Vec2(dl,0),Vec2(dl,W),Vec2(0,W),Vec2(0,0))
        di = Loft(sec_d,trans(0,0,H)*sec_d)
        sec_la = Section(Vec2(0,0),Vec2(L-dl*y,0),Vec2(L-dl*y,W),Vec2(0,W),Vec2(0,0))
        la = Loft(sec_la,trans(0,0,H)*sec_la)
        
        gui_all = Combine(trans(0,W/2/2-25,H/50*51)*gui,trans(0,W/4*3-25,H/50*51)*gui)
        all = Combine(di) 
        all_all = []
        for i in range(int(y)):
            all_all.append(trans(i*(dl+25),0,0)*all)
        allla = trans(y*(dl+25),0,0)*Combine(la)
        
        allin = Combine(*all_all,allla)

        self['铁轨'] = Combine(allin,gui_all,all_gz)

if __name__ == "__main__":
    FinalGeometry = 铁轨()
    TwoPointPlace.linearize(FinalGeometry, '长度')
    place(FinalGeometry)
