from pyp3d import * 
class 隧道(Component):

    def __init__(self):
        Component.__init__(self) 
        self['二次衬砌厚度'] = Attr(350,obvious = True)
        self['隧道净宽'] = Attr(10000,obvious = True)
        self['拱仰厚度'] = Attr(5000,obvious = True)
        self['隧道长度'] = Attr(50000,obvious = True)
        self['底部高度'] = Attr(800,obvious = True)
        
        self['隧道'] = Attr(None,show = True)
        self.replace()

    @export

    def replace(self):
        W = self['隧道净宽']
        H = self['拱仰厚度']
        w = self['二次衬砌厚度']
        h = self['底部高度']
        L = self['隧道长度']
        R = 10
        Z = Cone(Vec3(0,0,0),Vec3(0,0,L),R,R)
        sec_un = Section(Vec2(W/2,0),Vec2(W/2+w,0),
                         Arc(Vec2(W/2+w,0),Vec2(0,-h-w),Vec2(-W/2-w,0)),
                         Vec2(-W/2-w,0),Vec2(-W/2,0),
                         Arc(Vec2(-W/2,0),Vec2(0,-h),Vec2(W/2,0)))
        un = Loft(sec_un,trans(0,0,L)*sec_un)
        sec_top = Section(Vec2(W/2,0),Vec2(W/2+w,0),
                          Arc(Vec2(W/2+w,0),Vec2(0,H+w),Vec2(-W/2-w,0)),
                          Vec2(-W/2-w,0),Vec2(-W/2,0),
                          Arc(Vec2(W/2,0),Vec2(0,H),Vec2(-W/2,0)),)
        top = Loft(sec_top,trans(0,0,L)*sec_top)
        wai = Combine(un,top)
        x1 = 1000
        h1 =H/5000*200
        b1 = W/2/5000*1029.7
        b2 = W/10000*1033.9
        b3 = W/10000*540.6
        h2 = h/800*292.7
        sec_dun1= Section(Vec2(-W/2+x1,0),Vec2(-W/2+x1,h1),Vec2(-W/2+x1-b1,h1),
                          Arc(Vec2(-W/2+x1-b1,h1),Vec2(-W/2+x1-b2,h1/2),Vec2(-W/2,0)),
                          Vec2(-W/2,0),Arc(Vec2(-W/2,0),Vec2(-W/2+x1-b3,-h2/2),Vec2(-W/2+x1,-h2)),
                          Vec2(-W/2+x1,-h2),Vec2(-W/2+x1,0))
        dun1 = Loft(sec_dun1,trans(0,0,L)*sec_dun1)
        sec_dun2 = Section(Vec2(W/2-x1,0),Vec2(W/2-x1,h1),Vec2(W/2-x1+b1,h1),
                          Arc(Vec2(W/2-x1+b1,h1),Vec2(W/2-x1+b2,h1/2),Vec2(W/2,0)),
                          Vec2(W/2,0),Arc(Vec2(W/2,0),Vec2(W/2-x1+b3,-h2/2),Vec2(W/2-x1,-h2)),
                          Vec2(W/2-x1,-h2),Vec2(W/2-x1,0))
        dun2 = Loft(sec_dun2,trans(0,0,L)*sec_dun2)
        cut = scale(300,300,L)*Cube()
        all_cut = Combine(trans(W/2-x1/2-150,h1-310,0)*cut,trans(-W/2+x1/2-150,h1-310,0)*cut)
        dun = Combine(dun1,dun2)
        all_dun = dun-all_cut

        sec_lu = Section(Vec2(-W/2+x1,40),Vec2(-W/2+x1,-60),Vec2(W/2-x1,-60),Vec2(W/2-x1,40),Vec2(-W/2+x1,40))
        lumian = Loft(sec_lu,trans(0,0,L)*sec_lu)
        lu = lumian-trans(-W/2+x1+100,-10,0)*Z-trans(W/2-x1-100,-10,0)*Z
        luc = Combine(lu,all_dun,wai).color(0,0,0,1)

        sb = scale(W/10000*200,5,L)*Cube()
        all_sb = Combine(trans(W/2-x1-300,40,0)*sb,trans(-W/2+x1+150,40,0)*sb,trans(-100,40,0)*sb).color(1,1,1,1)  # 三条设备带:白色

        self['隧道'] = Combine(luc,all_sb)

if __name__ == "__main__":
    FinalGeometry = 隧道()
    place(FinalGeometry)