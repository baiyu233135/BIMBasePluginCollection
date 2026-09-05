from pyp3d import *

class 体育馆外墙斜(Component):
    def __init__(self):
        Component.__init__(self)
        self['底宽'] = Attr(2238.76, obvious=True)
        self['顶宽'] = Attr(3112.79, obvious=True)
        self['高度'] = Attr(24073.92,obvious = True)


        self['体育馆外墙斜'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        H = self['高度']
        DW = self['底宽']
        TW = self['顶宽']
        R = TW/3112.79*4600
        mid_x = R/4600*2482
        mid_y = R/4600*3550
        under = Section(Vec2(0,0),
                        Vec2(DW,0),
                        Vec2(TW+R,H-R),                        
                        Arc(Vec2(TW+R,H-R),Vec2(TW+mid_x,H-R+mid_y),Vec2(TW-DW,H)),
                        Vec2(0,H),
                        Vec2(0,0))
        mian1 = rotate(Vec3(0,0,1),pi/2)*rotate(Vec3(1,0,0),pi/2)*under
        mian2 = trans(-6520.14,0,0)*mian1
        mian21 = trans(-6520.14,0,0)*rotate(Vec3(0,0,1),pi/6)*mian1
        mian3 = trans(-24107.65,-4935.21,0)*rotate(Vec3(0,0,1),pi/6)*mian1
        mian31 = trans(-24107.65,-4935.21,0)*rotate(Vec3(0,0,1),pi/6*2)*mian1
        mian4 = trans(-40083.05,-22080.96,0)*rotate(Vec3(0,0,1),pi/6*2)*mian1
        mian41 = trans(-40083.05,-22080.96,0)*rotate(Vec3(0,0,1),pi/6*3)*mian1
        mian5 = trans(-43554.46,-38743.51,0)*rotate(Vec3(0,0,1),pi/6*3)*mian1
        mian51 = trans(-43554.46,-38743.51,0)*rotate(Vec3(0,0,1),pi/6*3)*mian1
        mian6 = trans(-43554.46,-42481.53,0)*rotate(Vec3(0,0,1),pi/6*3)*mian1
        kuaix = []
        for i in range(4):
            sec = Loft(rotate(Vec3(0,0,1),pi/6*i)*mian1,rotate(Vec3(0,0,1),pi/6*(i+1))*mian1)
            kuaix.append(sec)
        kuai21 = trans(-6520.14,0,0)*kuaix[0]
        kuai31 = trans(-24107.65,-4935.21,0)*kuaix[1]
        kuai41 = trans(-40083.05,-22080.96,0)*kuaix[2]
        kuai51 = trans(-43554.46,-38743.51,0)*kuaix[3]
        mian = [mian1,mian2,mian21,mian3,mian31,mian4,mian41,mian5,mian51,mian6]
        kuai = []
        for i in range(9):
            if i % 2 == 0:
                kuai.append(Loft(mian[i],mian[i+1]))
        all = Combine(*kuai)

        self['体育馆外墙斜'] = Combine(all,kuai21,kuai31,kuai41,kuai51)

if __name__ == "__main__":
    FinalGeometry = 体育馆外墙斜()
    FinalGeometry.replace()
    place(FinalGeometry)