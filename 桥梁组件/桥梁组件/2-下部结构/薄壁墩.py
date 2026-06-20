from pyp3d import *

class 薄壁墩(Component):
    def __init__(self):
        Component.__init__(self)
        self['构件类型'] = Attr('下部结构',obvious=True,readonly = True, group='构件分类')
        self['构件名称'] = Attr('薄壁墩',obvious=True,readonly = True,group='构件分类')

        self['柱高度'] = Attr(5330, obvious = True)
        self['柱宽度'] = Attr(600, obvious = True)
        self['柱厚度'] = Attr(400, obvious = True)

        self['承台高度'] = Attr(350, obvious = True)
        self['承台长度'] = Attr(800, obvious = True)
        self['承台宽度']  = Attr(790, obvious = True)

        self['桩基半径'] = Attr(100, obvious = True)
        self['桩基高度'] = Attr(5000, obvious = True)

        self['薄壁墩']  = Attr(None,show=True)
        self.replace()
    @export
    def replace(self):
        #承台
        ch = self['承台高度']
        cl = self['承台长度']
        cw = self['承台宽度']
        box3 = Box(Vec3(-cl/2,-cw/2,0),Vec3(-cl/2,-cw/2,ch),Vec3(1,0,0),Vec3(0,1,0),cl,cw,cl,cw)
        h = self['柱高度']
        l = self['柱宽度']
        w = self['柱厚度']
        #圆角曲率30
        cr = 30
        box1 = Box(Vec3(-l/2+cr,-w/2,ch),Vec3(-l/2+cr,-w/2,ch + h),Vec3(1,0,0),Vec3(0,1,0),l-2*cr,w,l-2*cr,w)
        box2 = Box(Vec3(-l/2,-w/2+cr,ch),Vec3(-l/2,-w/2+cr,ch + h),Vec3(1,0,0),Vec3(0,1,0),l,w-2*cr,l,w-2*cr)
        cone1 = Cone(Vec3(-l/2+cr,-w/2+cr,ch),Vec3(-l/2+cr,-w/2+cr,ch +h),cr,cr)
        cone2 = translation(l-2*cr,0,0) * cone1
        cone3 = translation(0,w-2*cr,0) * cone1
        cone4 = translation(l-2*cr,w-2*cr,0) * cone1
        section = unite(box1,box2,cone1,cone2,cone3,cone4)
        #桩生成
        r = self['桩基半径']
        rl = self['桩基高度']
        rd = 160
        x_gap = 480
        y_gap = 470
        # 四角桩
        pile_positions = [
            (-cl/2+rd, -cw/2+rd),
            (cl/2-rd, -cw/2+rd),
            (-cl/2+rd, cw/2-rd),
            (cl/2-rd, cw/2-rd)
        ]
        pile_count = 4
        # x/y方向自动布置，承台长或宽不足间距则不生成
        x_count = int((cl - 2*rd) // x_gap) + 1 if (cl - 2*rd) >= x_gap else 0
        y_count = int((cw - 2*rd) // y_gap) + 1 if (cw - 2*rd) >= y_gap else 0
        def is_duplicate(x, y, positions, min_dist):
            for px, py in positions:
                if ((x-px)**2 + (y-py)**2)**0.5 < min_dist:
                    return True
            return False
        for i in range(x_count):
            x = -cl/2 + rd + i * x_gap
            for j in range(y_count):
                y = -cw/2 + rd + j * y_gap
                # 已有桩位置（含四角），距离小于桩径则跳过
                if is_duplicate(x, y, pile_positions, r):
                    continue
                pile_positions.append((x, y))
                pile_count += 1
        temp_pile = Combine()
        for x, y in pile_positions:
            pile = Cone(Vec3(x, y, 0), Vec3(x, y, -rl), r, r)
            temp_pile = Combine(temp_pile, pile)

        #连接部分
        c = 485*2
        k = 500
        box = Box(Vec3(cl/2,-250,0),Vec3(cl/2,-250,ch),Vec3(1,0,0),Vec3(0,1,0),c,k,c,k)

        all = Combine(box, box3, section, temp_pile)
        #镜像
        mil = translation(cl+c,0,0) * Combine(box3, section, temp_pile)
        total = Combine(all + mil)

        self['承台体积'] = Attr((((ch*cl*cw)*2+c*k*ch))*(10**-6),obvious = False,readonly = True, group='全局参数')
        self['桩基体积'] = Attr(((r*r*pi*rl)*2*pile_count)*(10**-6),obvious = False,readonly = True, group='全局参数')
        self[f'总体积'] = Attr(self['承台体积']+self['桩基体积'],obvious = True,readonly = True, group='全局参数')
        self['薄壁墩'] = total
        
if __name__ == "__main__":
    Final_Geometry = 薄壁墩()
    place(Final_Geometry)