from pyp3d import *

class 外楼梯(Component):
    def __init__(self):
        Component.__init__(self)
        self['管半径'] = Attr(30, obvious=True)
        self['长度'] = Attr(6397.64, obvious=True)
        self['宽度'] = Attr(6929.14,obvious = True)
        self['高度'] = Attr(3001.97, obvious=True)
        self['管高'] = Attr(731.69,obvious = True)

        self['外楼梯'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['高度']
        W = self['宽度']
        High = self['管高']
        R = self['管半径']
        long = L/6397.64*2460
        mid_long = L-2*long
        high = H/3001.97*1476
        g1 = Cone(Vec3(0,0,0),Vec3(0,0,High),R,R)
        g2 = Cone(Vec3(0,0,0),Vec3(L/6397.64*2583.57,0,-H/3001.97*1527.59),R,R)
        g3 = Cone(Vec3(0,0,0),Vec3(mid_long,0,0),R,R)
        mian1 = []
        for i in range(10):
            sec = trans(0, high/10*i, 0) * Section(Vec2(0,0), Vec2(L-long/10*i,0), Vec2(L-long/10*i,high/10), Vec2(0,high/10), Vec2(0,0))
            mian1.append(rotate(Vec3(1,0,0), pi/2) * Loft(sec, trans(0,0,W)*sec))
        mian2 = []
        for i in range(10):
            sec = trans(0, high/10*i, 0) * Section(Vec2(0,0), Vec2(long/10*(10-i),0), Vec2(long/10*(10-i),high/10), Vec2(0,high/10), Vec2(0,0))
            mian2.append(rotate(Vec3(1,0,0), pi/2) * Loft(sec, trans(0,0,W)*sec))
        ti = Combine(*(mian1 + trans(0,0,high)*mian2))
        guan_high = Combine(trans(-50,-50,H)*g1,trans(-50,50-W,H)*g1,trans(long+100,-50,H/2)*g1,trans(long+100,50-W,H/2)*g1,trans(L-long-100,-50,H/2)*g1,trans(L-long-100,50-W,H/2)*g1,trans(L,-50,0)*g1,trans(L,50-W,0)*g1)
        guan_heng = Combine(trans(long,-50,H/2+High-10)*g3,trans(long,50-W,H/2+High-10)*g3) 
        guan_xie = Combine(trans(-50,-50,H+High)*g2,trans(-50,50-W,H+High)*g2,trans(L-long-50,-50,H/2+High)*g2,trans(L-long-50,50-W,H/2+High)*g2)
        self['外楼梯'] = ti + guan_high + guan_heng+guan_xie

if __name__ == '__main__':
    FinalGeometry = 外楼梯()
    FinalGeometry.replace()
    place(FinalGeometry)
