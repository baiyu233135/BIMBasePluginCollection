from pyp3d import *

class 大屏及支架(Component):
    def __init__(self):
        Component.__init__(self)
        self['面板长'] = Attr(9153.54, obvious=True)
        self['面板宽'] = Attr(4378.62, obvious=True)
        self['背支架高'] = Attr(4921.26,obvious = True)
        self['背支架长'] = Attr(3921.05,obvious = True)
        self['厚度'] = Attr(492.13, obvious=True)
        self['截面边长'] = Attr(300,obvious = True)

        self['大屏及支架'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['面板长']
        W = self['面板宽']
        B = self['截面边长']
        H = self['厚度']
        high = self['背支架高']
        long = self['背支架长']
        m = rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(L,0),Vec2(L,W),Vec2(0,W),Vec2(0,0))
        mian = Loft(m,trans(0,H,0)*m)
        under = Section(Vec2(0,0),Vec2(B,0),Vec2(B,B),Vec2(0,B),Vec2(0,0))
        u_xw = Combine(Loft(under,trans(L-B,0,high)*under),trans(L-B,0,0)*Loft(under,trans(B-L,0,high)*under))
        u_xx_unit = Loft(under,trans(0,long,high)*under)
        u_xx = Combine(u_xx_unit,trans(L/2-B,0,0)*u_xx_unit,trans(L-B,0,0)*u_xx_unit)
        u_xs_unit = Loft(under,trans(0,0,high)*under)
        u_xs = Combine(u_xs_unit,trans(L/2-B,0,0)*u_xs_unit,trans(L-B,0,0)*u_xs_unit)


        self['大屏及支架'] = Combine(mian,trans(0,H,0)*u_xw,trans(0,H,0)*u_xx,trans(0,H,0)*u_xs)

if __name__ == "__main__":
    FinalGeometry = 大屏及支架()
    FinalGeometry.replace()
    place(FinalGeometry)