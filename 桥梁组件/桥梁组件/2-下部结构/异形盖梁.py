from pyp3d import *

class 盖梁(Component):
    def __init__(self):
        Component.__init__(self)
        self['盖梁长'] = Attr(1490,obvious = True)
        self['左右两侧高差'] = Attr(247.5, obvious = True)
        self['右侧高'] = Attr(350, obvious = True)
        self['左侧宽'] = Attr(145, obvious = True)
        self['右侧宽'] = Attr(355, obvious = True)
        self['支座垫石间距'] = Attr(250, obvious = True)
        self['盖梁'] = Attr(None,show = True)
        
        self.replace()
    @export
    def replace(self):
        zh = self['左右两侧高差']
        yh = self['右侧高']
        zw = self['左侧宽']
        yw = self['右侧宽']
        l = self['盖梁长']
        D = self['支座垫石间距']
        # 盖梁
        section = rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(-l/2+245,0),Vec2(-l/2,100),Vec2(-l/2,yh),Vec2(l/2,yh),Vec2(l/2,100),Vec2(l/2-280,100),Vec2(l/2-280-245,0))
        line = Line(Vec3(0,0,0),Vec3(0,yw,0))
        sweep = Sweep(section, line)

        ssection = trans(0,yw,0) * rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(-l/2+245,0),Vec2(-l/2,100),Vec2(-l/2,yh+zh),Vec2(l/2,yh+zh),Vec2(l/2,100),Vec2(l/2-280,100),Vec2(l/2-280-245,0))
        line2 = Line(Vec3(0,yw,0),Vec3(0,yw+zw,0))
        sweep2 = Sweep(ssection, line2)

        #支座垫石
        #大
        bianchang = 100
        bh = 20
        #小
        bianchang2 = 100
        box = Box(Vec3(0,0,0),Vec3(0,0,bh),Vec3(1,0,0),Vec3(0,1,0),bianchang,bianchang,bianchang,bianchang)
        box2 = Box(Vec3(0,0,0),Vec3(0,0,bh),Vec3(1,0,0),Vec3(0,1,0),bianchang2,bianchang2,bianchang2,bianchang2)

        if zh > 0:
            zzds = translation(-l/2+120-bianchang/2,90-bianchang/2,yh) * box
            x_start = l/2 - 150
            x_end = -l/2 + 290
            temp_zzds2 = Combine()
            x = x_start
            while x >= x_end:
                temp_zzds2 = Combine(temp_zzds2, translation(x-bianchang2/2, yw+zw-89.5-bianchang2/2, yh+zh) * box2)
                x -= D
        else:
            zzds = translation(-l/2+120-bianchang/2,(yw+zw)/2-bianchang/2,yh) * box
            temp_zzds2 = Combine()
        total = sweep + sweep2 + zzds + temp_zzds2

        #镜像
        mil = mirror(trans(l/2,0,0) * rotz(0)) *total
        self['盖梁'] =total + mil
        
if __name__ == "__main__":
    Final_Geometry = 盖梁()
    place(Final_Geometry)       