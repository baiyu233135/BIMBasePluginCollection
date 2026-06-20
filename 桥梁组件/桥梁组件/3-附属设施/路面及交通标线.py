from pyp3d import *

class 路面及交通标线(Component):
    def __init__(self):
        Component.__init__(self)
        self['中央分隔带宽度'] = Attr(150,obvious = True)
        self['路缘带宽度'] = Attr(50,obvious = True)
        self['单车道宽度'] = Attr(375,obvious = True)
        self['应急车道宽度'] = Attr(350,obvious = True)
        self['单侧车道数初始值'] = Attr(2,obvious = True)
        self['路面厚度初始值'] = Attr(10,obvious = True)
        self['路面长'] = Attr(2000,obvious = False)
        self['路面及交通标线'] = Attr(None,show = True)
        self.replace()
    @export
    def replace(self):
        #标线宽20,厚1;路面厚10
        BD = 20
        BH = 1
        RH = self['路面厚度初始值']
        RC = self['路面长']
        lineBlack = Line(Vec3(0,0,0),Vec3(0,0,RH))
        lineWhite = Line(Vec3(0,0,0),Vec3(0,0,BH))
        #应急车道
        yjd = self['应急车道宽度']
        yj = Section(Vec2(0,0),Vec2(yjd-BD/2,0),Vec2(yjd-BD/2,RC),Vec2(0,RC))
        yjRoad = Sweep(yj,lineBlack).color(0,0,0,1)
        #主车道侧标线
        RD = self['单车道宽度']
        RM = self['单侧车道数初始值']
        bx = Section(Vec2(0,0),Vec2(BD,0),Vec2(BD,RC),Vec2(0,RC))
        bx1 = Sweep(bx,lineWhite)
        bx1Road = trans(yjd-BD/2,0,RH) * bx1
        lin = Line(Vec3(0,0,0),Vec3(0,0,RH))
        ro = trans(yjd-BD/2,0,0) * Sweep(bx,lin).color(0,0,0,1)
        bxroad = Combine(bx1Road , ro)
        bx2Road = trans((yjd+RM*RD)-BD/2-(yjd-BD/2),0,0) * bxroad
        #主车道路面
        z = Section(Vec2(0,0),Vec2(RD*RM-BD,0),Vec2(RD*RM-BD,RC),Vec2(0,RC))
        zr = Sweep(z,lineBlack).color(0,0,0,1)
        zroad = trans(yjd+BD/2) * zr
        #主车道虚标线
        dash_sec = Section(Vec2(0,0), Vec2(BD,0), Vec2(BD,200), Vec2(0,200))
        dash_unit = Sweep(dash_sec, lineWhite)
        
        main_road_width = RD * RM - BD
        
        dashed_lines = []
        for i in range(1, RM):
            x_off = (i * main_road_width / RM) - BD/2
            y_center = 100
            while y_center < RC:
                # 计算本段虚标线实际长度
                dash_length = min(200, RC - y_center + 100)
                dash_sec = Section(Vec2(0,0), Vec2(BD,0), Vec2(BD,dash_length), Vec2(0,dash_length))
                dash_unit = Sweep(dash_sec, lineWhite)
                dash = trans(x_off, y_center - 100, 0) * dash_unit
                dashed_lines.append(dash)
                y_center += 600
        x = unite(dashed_lines)
        xx = trans(yjd+BD/2,0,RH) * x

        line = Line(Vec3(0,0,0),Vec3(0,0,RH))
        xu = Sweep(dash_sec,line)

        dash_all = []
        for i in range(1, RM):
            x_off = (i * main_road_width / RM) - BD/2
            y_center = 100
            while y_center < RC:
                dash_length = min(200, RC - y_center + 100)
                dash_sec = Section(Vec2(0,0), Vec2(BD,0), Vec2(BD,dash_length), Vec2(0,dash_length))
                xu = Sweep(dash_sec, line)
                dash = trans(x_off, y_center - 100, 0) * xu
                dash_all.append(dash)
                y_center += 600
        a = unite(dash_all)
        aa = trans(yjd+BD/2,0,RH) * a
        
        road = (zroad - aa).color(0,0,0,1)
        cb = Combine(road,xx)

        l = self['路缘带宽度']
        last = Section(Vec2(0,0),Vec2(l-BD/2,0),Vec2(l-BD/2,RC),Vec2(0,RC))
        last1 = Sweep(last,lineBlack).color(0,0,0,1)
        last2 = trans(yjd+RD*RM+BD/2,0,0) * last1
        total = Combine(yjRoad,bxroad,bx2Road,cb,last2)

        zfd = self['中央分隔带宽度']
        mil = mirror(trans(yjd+RD*RM+l+zfd/2,0,0) * rotz(0)) * total
        totally = Combine(total,mil)
        self['路面及交通标线'] = rotate(Vec3(0,0,1),-0.5*pi) * totally

if __name__ == "__main__":
    FinalGeometry = 路面及交通标线()
    TwoPointPlace.linearize(FinalGeometry,'路面长')
    place(FinalGeometry)        



