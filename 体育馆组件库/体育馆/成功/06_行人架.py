from pyp3d import *

class 行人架(Component):
    def __init__(self):
        Component.__init__(self)
        self['两侧柱子长'] = Attr(4911.51, obvious=True)
        self['两侧柱子宽'] = Attr(4911.51, obvious=True)
        self['两侧柱子高'] = Attr(6397.64,obvious = True)
        self['管半径'] = Attr(30, obvious=True)
        self['管高'] = Attr(731.69, obvious=True)
        self['总长度'] = Attr(188309.52, obvious=True)
        self['行人架宽'] = Attr(1771.65, obvious=True)
        self['外厚度'] = Attr(295.28,obvious = True)
        self['内厚度'] = Attr(49.21,obvious = True)

        self['行人架'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['总长度']
        H = self['两侧柱子高']
        l = self['两侧柱子长']
        w = self['两侧柱子宽']
        R = self['管半径']
        high = self['管高']
        W = self['行人架宽']
        W1 = W/6
        W2 = W/6*4
        B = self['内厚度']
        C = self['外厚度']
        D = 100
        N = L-2*l
        h = H/5*2
        
        sec_zhu = Section(Vec2(0,0),Vec2(l,0),Vec2(l,w),Vec2(0,w),Vec2(0,0))
        zhu_unit = Loft(sec_zhu,trans(0,0,H)*sec_zhu)
        zhu = Combine(zhu_unit,trans(L-2*l,0,0)*zhu_unit)

        sec_lumian = Section(Vec2(0,0),Vec2(L-2*l,0),Vec2(L-2*l,W2),Vec2(0,W2),Vec2(0,0))
        lumian_unit = Loft(sec_lumian,trans(0,0,B)*sec_lumian)
        lumian = trans(l,w/2-W2/2,h-B)*lumian_unit

        sec_wai = Section(Vec2(0,0),Vec2(L-2*l,0),Vec2(L-2*l,W1),Vec2(0,W1),Vec2(0,0))
        wai_unit = Loft(sec_wai,trans(0,0,C)*sec_wai)
        wai = Combine(trans(l,0,H-C)*wai_unit,trans(l,w-C,H-C)*wai_unit,
                      trans(l,w/2-W2/2-W1,h-C)*wai_unit,trans(l,w/2+W2/2,h-C)*wai_unit)
        
        sec_dx = Section(Vec2(0,0),Vec2(D,0),Vec2(N/30/2,W/2-D/2),Vec2(N/30-D,0),
                         Vec2(N/30,0),Vec2(N/60+D/2,W/2),Vec2(N/30,W),Vec2(N/30-D,W),
                         Vec2(N/60,W/2+D/2),Vec2(D,W),Vec2(0,W),Vec2(N/60-D/2,W/2),Vec2(0,0))
        dx_unit = Loft(sec_dx,trans(0,0,B)*sec_dx)

        sec_tx = Section(Vec2(0,0),Vec2(D,0),Vec2(N/30/2,w/2-D/2),Vec2(N/30-D,0),
                         Vec2(N/30,0),Vec2(N/60+D/2,w/2),Vec2(N/30,w),Vec2(N/30-D,w),
                         Vec2(N/60,w/2+D/2),Vec2(D,w),Vec2(0,w),Vec2(N/60-D/2,w/2),Vec2(0,0))
        tx_unit = Loft(sec_tx,trans(0,0,B)*sec_tx)

        sec_under = Section(Vec2(0,0),Vec2(D,0),Vec2(D,D),Vec2(0,D),Vec2(0,0))
        xf_unit = Loft(sec_under,trans(-N/30,W/2-w/2,H-h)*sec_under)+Loft(sec_under,trans(N/30,W/2-w/2,H-h)*sec_under)
        xb_unit = Loft(sec_under,trans(-N/30,w/2-W/2,H-h)*sec_under)+Loft(sec_under,trans(N/30,w/2-W/2,H-h)*sec_under)
    
        g1 = Cone(Vec3(0,0,0),Vec3(0,0,high),R,R)
        g2 = Cone(Vec3(0,0,0),Vec3(L-2*l,0,0),R,R)
        g_heng = Combine(trans(l,w/2-W2/2-W1+R,h+high+B)*g2,trans(l,w/2+W2/2+W1-R,h+high+B)*g2)
        gs_unit = Combine(trans(0,R,0)*g1,trans(0,W-R,0)*g1)

        g30 = []
        g15 = []
        for i in range(30):
            sec = trans(N/30*i,0,h)*Combine(trans(0,-W1,-B*2)*dx_unit,trans(0,-W1,B*2)*gs_unit,trans(0,W2/2-w/2,H-h-D*2)*tx_unit)
            g30.append(sec)
        g_30 = trans(l,w/2-W2/2,0)*Combine(*g30)
        for i in range(15):
            sec = trans(N/15*i,0,h)*Combine(trans(l+N/30,w/2-W2/2-W1,0)*xf_unit,trans(l+N/30,w/2+W2/2+W1-D,0)*xb_unit)
            g15.append(sec)
        g_15 = Combine(*g15)
       
        self['行人架'] = zhu + wai + lumian + g_30 + g_heng + g_15

if __name__ == "__main__":
    FinalGeometry = 行人架()
    FinalGeometry.replace()
    place(FinalGeometry)