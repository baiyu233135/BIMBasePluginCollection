from pyp3d import *

class 路面及交通标线(Component):
    def __init__(self):
        Component.__init__(self)
        self['中央分隔带宽度'] = Attr(1500,obvious = True)
        self['路缘带宽度'] = Attr(500,obvious = True)
        self['单车道宽度'] = Attr(3750,obvious = True)
        self['应急车道宽度'] = Attr(3500,obvious = True)
        self['单侧车道数初始值'] = Attr(2,obvious = True)    # ★ 标线数量计算：从这里读取车道数RM
        self['路面厚度初始值'] = Attr(100,obvious = True)
        self['路面长'] = Attr(20000,obvious = False)
        
        self['路面及交通标线'] = Attr(None,show = True)

        self.replace()

    @export
    def replace(self):
        #标线宽20,厚1;路面厚10
        BD = 200
        BH = 10
        RH = self['路面厚度初始值']
        #路面长经 TwoPointPlace 拉伸后可能为字符串，统一转数值并容错
        try:
            RC = float(self['路面长'])
        except (TypeError, ValueError):
            RC = 20000.0
        lineBlack = Line(Vec3(0,0,0),Vec3(0,0,RH))
        lineWhite = Line(Vec3(0,0,0),Vec3(0,0,BH))
        #应急车道
        yjd = self['应急车道宽度']
        yj = Section(Vec2(0,0),Vec2(yjd-BD/2,0),Vec2(yjd-BD/2,RC),Vec2(0,RC))
        yjRoad = Sweep(yj,lineBlack).color(0,0,0,1)
        #主车道侧标线
        RD = self['单车道宽度']
        RM = self['单侧车道数初始值']                      # ★ 标线数量计算：RM = 车道数
        #车道数除零/非法值保护
        try:
            RM = int(RM)
        except (TypeError, ValueError):
            RM = 2
        RM = max(RM, 1)
        bx = Section(Vec2(0,0),Vec2(BD,0),Vec2(BD,RC),Vec2(0,RC))
        bx1 = Sweep(bx,lineWhite)
        bx1Road = trans(yjd-BD/2,0,RH-BH) * bx1
        lin = Line(Vec3(0,0,0),Vec3(0,0,RH-BH))
        ro = trans(yjd-BD/2,0,0) * Sweep(bx,lin).color(0,0,0,1)
        bxroad = Combine(bx1Road , ro)
        bx2Road = trans((yjd+RM*RD)-BD/2-(yjd-BD/2),0,0) * bxroad   # ★ 标线数量计算：右侧车道标线平移
        #主车道路面
        z = Section(Vec2(0,0),Vec2(RD*RM-BD,0),Vec2(RD*RM-BD,RC),Vec2(0,RC))
        zr = Sweep(z,lineBlack).color(0,0,0,1)
        zroad = trans(yjd+BD/2) * zr
        #主车道虚标线：标准段(长2000)用 Array 实例化排布，末段非标单独处理；
        #不再对整条路面做巨型布尔减，黑底/白线薄片分层抬高约1mm贴在路面顶面避免 z-fighting
        DASH_L = 2000     #标准虚线段长
        DASH_C = 6000     #虚线中心距
        DASH_Y0 = 6100    #首段虚线中心
        main_road_width = RD * RM - BD                  # ★ 标线数量计算：主车道总宽
        lineThin = Line(Vec3(0,0,0),Vec3(0,0,1))        #1mm薄片拉伸线
        dash_sec = Section(Vec2(0,0), Vec2(BD,0), Vec2(BD,DASH_L), Vec2(0,DASH_L))
        dashBlackUnit = Sweep(dash_sec, lineThin).color(0,0,0,1)    #放入 Array 前先上色
        dashWhiteUnit = Sweep(dash_sec, lineThin)
        arrBlack = Array(dashBlackUnit)
        arrWhite = Array(dashWhiteUnit)
        extraBlack = []
        extraWhite = []
        n_std = 0                                       #标准虚线段数
        if RC - 1000 >= DASH_Y0:
            n_std = int((RC - 1000 - DASH_Y0) / DASH_C) + 1
        for i in range(1, RM):                          # ★ 标线数量计算：循环RM-1次生成车道分界线
            x_off = (i * main_road_width / RM) - BD/2
            for k in range(n_std):
                y0 = DASH_Y0 + DASH_C * k - 1000
                arrBlack.append(trans(x_off, y0, 0))
                arrWhite.append(trans(x_off, y0, 0))
            y_last = DASH_Y0 + DASH_C * n_std
            if y_last < RC:                             #末段长度不足2000的非标虚线
                plen = RC - y_last + 1000
                psec = Section(Vec2(0,0), Vec2(BD,0), Vec2(BD,plen), Vec2(0,plen))
                extraBlack.append(trans(x_off, y_last - 1000, 0) * Sweep(psec, lineThin).color(0,0,0,1))
                extraWhite.append(trans(x_off, y_last - 1000, 0) * Sweep(psec, lineThin))
        layers = [zroad]
        if n_std > 0 and RM > 1:
            layers.append(trans(yjd+BD/2,0,RH+1) * arrBlack)   #黑底虚线抬高1mm
            layers.append(trans(yjd+BD/2,0,RH+2) * arrWhite)   #白线再抬高1mm
        if extraBlack:
            layers.append(trans(yjd+BD/2,0,RH+1) * Combine(*extraBlack))
            layers.append(trans(yjd+BD/2,0,RH+2) * Combine(*extraWhite))
        cb = Combine(*layers)                           #路面+虚线叠层，无布尔

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
