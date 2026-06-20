from pyp3d import *
class 桥墩(Component):
    def __init__(self):
        Component.__init__(self)
        self['墩柱高'] = Attr(1700, obvious=True)
        self['桩基径'] = Attr(110, obvious=False)

        self['盖梁宽度'] = Attr(1220, obvious=True)
        self['盖梁厚度'] = Attr(230, obvious=True)
        self['盖梁高'] = Attr(95, obvious=True)

        self['档墙长'] = Attr(25, obvious=False)
        self['档墙高'] = Attr(60, obvious=True)

        self['支座垫石长'] = Attr(100, obvious=True)
        self['支座垫石宽'] = Attr(100, obvious=True)
        self['支座垫石高'] = Attr(10, obvious=True)
        self['间距'] = Attr(250, obvious=False)
        self['系梁高'] = Attr(200, obvious=True)

        self['桥墩'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        DZH = self['墩柱高']

        W = self['盖梁厚度']
        L = self['盖梁宽度']
        TH = self['盖梁高']
        
        DL = self['档墙长']
        DH = self['档墙高']

        ZL = self['支座垫石长']
        ZW = self['支座垫石宽']
        zZH = self['支座垫石高']
        D = self['间距']

        TH1 = self['系梁高']

        R = self['桩基径']

        #承台
        box = rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(0,0),Vec2(115,-85),Vec2(L-115,-85),Vec2(L,0),Vec2(L,DH+TH),Vec2(L-DL,DH+TH),Vec2(L-DL,TH),Vec2(DL,TH),Vec2(DL,DH+TH),Vec2(0,DH+TH))
        line = Line(Vec3(0,0,0),Vec3(0,W,0))
        box_1 = Sweep(box,line)

        #支座
        box2 = Box(Vec3(32.5,W/2-ZW/2,TH),Vec3(32.5,W/2-ZW/2,TH+zZH),Vec3(1,0,0),Vec3(0,1,0),ZL,ZW,ZL,ZW)
        start = 32.5
        end = L - 132.5
        span = end - start
        num = int(span // D) + 1
        real_span = (num - 1) * D
        offset = (span - real_span) / 2
        temp = Combine()
        for i in range(num):
            x = start + offset + i * D
            temp = Combine(temp, trans(x - start, 0, 0) * box2)
        all = Combine(box_1, temp)
        
        #墩柱
        cone = Cone(Vec3(235,W/2,-85),Vec3(235,W/2,-DZH-85),R,R)
        temp2 = translation(L-470,0,0) * cone

        #系梁
        box3 = Box(Vec3(290,W/2-R+30,0),Vec3(290,W/2-R+30,-TH1),Vec3(1,0,0),Vec3(0,1,0),L-290-290,2*R-60,L-290-290,2*R-60)
        temp3 = Combine()
        if DZH > 1500:
            seg = int(DZH / 1500)
            pos = DZH / (seg+1)
            for i in range(seg):
                temp3 = Combine(temp3, trans(0,0,-(i+1) * pos) * box3)
        total = Combine(cone,temp2,temp3)

        self['桥墩'] = all + total
        
if __name__ == "__main__":
    FinalGeometry = 桥墩()
    place(FinalGeometry)