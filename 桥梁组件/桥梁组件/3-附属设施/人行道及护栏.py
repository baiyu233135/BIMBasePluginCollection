from pyp3d import *
class 人行道及护栏(Component):
    def __init__(self):
        Component.__init__(self)
        self['人行道长'] = Attr(700 , obvious = True)
        self['人行道宽'] = Attr(200  , obvious = True)
        self['柱子宽度'] = Attr(20 , obvious = True)
        self['柱子厚度'] = Attr(15  , obvious = True)
        self['柱子高度'] = Attr(120 , obvious = True)
        self['柱子间距'] = Attr(180 , obvious = True)
        self['圆管半径'] = Attr(5 , obvious = True)
        self['人行道及护栏'] = Attr(None, show = True)
        self.replace()
    @export
    def replace(self): 
        #人行道截面 200×15
        rc = self['人行道长']
        rk = self['人行道宽']
        sd = 15
        section = rotate(Vec3(1,0,0),0.5 * pi) * Section(Vec2(-rk/2,0),Vec2(-rk/2,-sd),Vec2(rk/2,-sd),Vec2(rk/2,0))
        line = Line(Vec3(0,0,0),Vec3(0,rc,0))
        sweep = Sweep(section,line)
        #桩顶 圆角曲率 r=桩宽/2
        zc = self['柱子宽度']
        zd = self['柱子厚度']
        zh = self['柱子高度']
        r = zd/2
        box = Box(Vec3(-rk/2,0,0),Vec3(-rk/2,0,zh-r),Vec3(1,0,0),Vec3(0,1,0),zd,zc,zd,zc)
        cone = Cone(Vec3(-rk/2+r,0,zh-r),Vec3(-rk/2+r,zc,zh-r),r,r)
        zhuang = unite(box,cone)
        #栏杆 底圆管距人行道面距离 ld=40 圆管间距30 
        lc = self['柱子间距']
        lr = self['圆管半径']
        ld = 40
        ll = 30
        lt = 20
        Cbotton = Cone(Vec3(-rk/2+zd/2,zc,ld),Vec3(-rk/2+zd/2,zc+lc,ld),lr,lr)
        Ctop = translation(0,0,zh-lt-ld) * Cbotton
        o = int((zh-lt-ld)/ll)
        p = (zh-lt-ld)/o
        temp = Combine()
        for i in range(o):
            temp = Combine(temp,trans(0,0,i * p) * Cbotton)
        #组合桩与栏杆:护栏
        all = Combine( temp , Ctop)
        #总：生成桩阵列
        op = lc + zc
        pile_positions = []
        i = 0
        while True:
            pos = i * op
            if pos + zc > rc:
                break
            pile_positions.append(pos)
            i += 1
        # 确保人行道尾部一定有桩（不超过人行道），若最后位置与尾部桩位置不符，则添加尾部桩
        if not pile_positions or abs((rc - zc) - pile_positions[-1]) > 1e-6:
            pile_positions.append(rc - zc)

        total = []
        for pos in pile_positions:
            total.append(translate(0, pos, 0) * zhuang)

        #生成护栏
        totally = []
        if len(pile_positions) >= 2:
            #前面完整间隔段采用原护栏配置
            for j in range(len(pile_positions) - 2):
                pos = pile_positions[j]
                totally.append(translate(0, pos, 0) * all)
            #最后一段若不足标准间隔则按比例缩放
            last_gap = pile_positions[-1] - pile_positions[-2]
            totally.append(translate(0, pile_positions[-2], 0) * scale(Vec3(1, last_gap/lc, 1)) * all)

        to = Combine(Combine(total)) + Combine(totally) + Combine(sweep) 
        self['人行道及护栏'] = rotate(Vec3(0,0,1),-0.5*pi) * to

if __name__ == "__main__":
    FinalGeometry = 人行道及护栏()
    TwoPointPlace.linearize(FinalGeometry,'人行道长')
    place(FinalGeometry)        