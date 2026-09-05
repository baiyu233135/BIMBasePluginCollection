from pyp3d import *

class 无障碍坡道(Component):
    def __init__(self):
        Component.__init__(self)
        self['总长'] = Attr(14948.52, obvious=True)
        self['坡长'] = Attr(9852.36, obvious=True)
        self['高度'] = Attr(3149.61,obvious = True)
        self['管半径'] = Attr(30, obvious=True)
        self['管高'] = Attr(731.69,obvious = True)
        self['坡宽'] = Attr(4242.13,obvious = True)

        self['无障碍坡道'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['总长']
        long = self['坡长']
        H = self['高度']
        R = self['管半径']
        high = self['管高']
        W = self['坡宽']
        g1 = Cone(Vec3(0,0,0),Vec3(0,0,high),R,R)
        g2 = Cone(Vec3(0,0,0),Vec3(0,W,0),R,R)
        g3 = Cone(Vec3(0,0,0),Vec3(L-long,0,0),R,R)
        g4 = Cone(Vec3(long,0,0),Vec3(0,0,H),R,R)
        sec_mian = rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(L,0),Vec2(L-long,H),Vec2(0,H),Vec2(0,0))
        mian = Loft(sec_mian,trans(0,W,0)*sec_mian)
        g_hw = Combine(trans(50,W+50,H)*g1,trans(50,W/3*2+50,H)*g1,trans(50,W/3+50,H)*g1)
        g_hl = Combine(trans((L-long)/3,50,H)*g1,trans((L-long)/3*2,50,H)*g1)
        g_hx = Combine(trans(0,50,H)*g1,trans(long/5,50,H/5*4)*g1,trans(long/5*2,50,H/5*3)*g1,trans(long/5*3,50,H/5*2)*g1,trans(long/5*4,50,H/5)*g1,trans(long,50,0)*g1)
        g_h = Combine(g_hw,g_hl,trans(L-long,0,0)*g_hx)
        g_w = trans(50,0,H+high)*g2
        g_l = trans(0,50,H+high)*g3
        g_x = trans(L-long,50,high)*g4

        self['无障碍坡道'] = mian + g_h + g_w + g_x + g_l

if __name__ == "__main__":
    FinalGeometry = 无障碍坡道()
    FinalGeometry.replace()
    place(FinalGeometry)