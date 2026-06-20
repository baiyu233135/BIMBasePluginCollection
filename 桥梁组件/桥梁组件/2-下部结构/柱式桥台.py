from pyp3d import *
class 柱式桥台(Component):
    def __init__(self):
        Component.__init__(self)
        self['桥台长'] = Attr(1250, obvious = True)
        self['桥台宽'] = Attr(160, obvious = True)
        self['桥台高'] = Attr(170, obvious = True)
        self['桩基半径'] = Attr(90, obvious = True)
        self['桩基长度'] = Attr(2200, obvious = True)
        self['背墙宽'] = Attr(60, obvious = True)
        self['背墙高'] = Attr(170+280, obvious = True)
        self['支座垫石长'] = Attr(100, obvious = False)
        self['支座垫石宽'] = Attr(100, obvious = False)
        self['支座垫石高'] = Attr(20, obvious = False)
        self['耳墙长'] = Attr(350, obvious = True)
        self['耳墙宽'] = Attr(50, obvious = True)
        self['耳墙高'] = Attr(458, obvious = True)
        self['柱式桥台'] = Attr(None, show = True)
        self.replace()
    @export
    def replace(self):
        CTC = self['桥台长']
        CTK = self['桥台宽']
        CTG = self['桥台高']

        ZJR = self['桩基半径']
        ZJG = self['桩基长度']

        BQK = self['背墙宽']
        BQG = self['背墙高']

        ZZC = self['支座垫石长']
        ZZK = self['支座垫石宽']
        ZZG = self['支座垫石高']

        EQC = self['耳墙长']
        EQK = self['耳墙宽']
        EQG = self['耳墙高']

        #承台
        box = Box(Vec3(0,0,0),Vec3(0,0,CTG),Vec3(1,0,0),Vec3(0,1,0),CTC,CTK,CTC,CTK)
        #挡土块
        #BIG
        BIG_H = 100
        BIG_Len = 160
        BIG_Wid = 30
        box2 =Box(Vec3(0,0,CTG),Vec3(0,0,CTG+BIG_H),Vec3(1,0,0),Vec3(0,1,0),BIG_Wid,CTK,BIG_Wid,CTK)
        total = Combine(box2)#box3)
        #支座垫石布置，首尾支座到承台边距离相同，间距严格为250，布置不超出承台，承台长1250时只有5个支座
        box4 = Box(Vec3(0,CTK/2 -24,CTG),Vec3(0,CTK/2 -24,CTG+ZZG),Vec3(1,0,0),Vec3(0,1,0),ZZK,ZZC,ZZK,ZZC)
        D = 250
        start = 0
        end = CTC
        usable_span = end - start
        # 计算最大可布置支座数，保证间距不变且不超出承台
        n = int((usable_span - ZZK) // D) + 1
        # 特殊处理：承台长为1250时，强制5个支座
        if abs(CTC - 1250) < 1e-3:
            n = 5
        # 实际布置总跨度
        total_span = D * (n - 1)
        # 首尾到边距离
        edge_offset = (usable_span - total_span - ZZK) / 2
        temp = Combine()
        for i in range(n):
            a = start + edge_offset + i * D
            temp = Combine(temp, trans(a, 0, 0) * box4)
        total = Combine(total, temp)
        last2= translation(Vec3(CTC-30,0,0)) * box2
        #背墙
        box5 = rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(0,0),Vec2(BQK,0),Vec2(BQK,BQG),Vec2(0,BQG),Vec2(0,BQG-28),Vec2(-30,BQG-28),Vec2(-30,BQG-58),Vec2(0,BQG-88))
        box5_5 = translation(50,CTK + BQK,0) * rotate(Vec3(0,0,1),-0.5*pi) * box5
        line = Line(Vec3(50,CTK,0),Vec3(CTC-50,CTK,0))
        box6 = Sweep(box5_5,line)
        #耳墙
        box7 = rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(0,0),Vec2(BQK,0),Vec2(BQK,EQG),Vec2(-EQC+BQK,EQG),Vec2(-EQC+BQK,EQG-50))
        box7_7= translation(0,CTK+BQK,0) *rotate(Vec3(0,0,1),-0.5*pi) * box7
        line2 = Line(Vec3(0,CTK,0),Vec3(EQK,CTK,0))
        box8 = Sweep(box7_7,line2)
        box8_8 = translation(CTC-50,0,0) * box8
        totally = Combine(box8,box8_8)
        #桩基
        ZJ = Cone(Vec3(255,CTK/2 + 24,0),Vec3(255,CTK/2 + 24,-ZJG),ZJR,ZJR)

        ZJ2 = trans(CTC-255-255,0,0) * ZJ

        zhizuo = temp+box+total+last2+box6+totally+ZJ+ZJ2

        self['柱式桥台'] = zhizuo
        
if __name__ == "__main__":
    FinalGeometry = 柱式桥台()
    place(FinalGeometry)

        