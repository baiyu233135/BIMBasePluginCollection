from pyp3d import *

class 外栏杆(Component):
    def __init__(self):
        Component.__init__(self)
        self['管半径'] = Attr(30, obvious=True)
        self['管高'] = Attr(731.69, obvious=True)
        self['长度'] = Attr(22492.38,obvious = True)

        self['外栏杆'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        L = self['长度']
        H = self['管高']
        R = self['管半径']
        g1 = Cone(Vec3(0,0,0),Vec3(0,0,H),R,R)
        g2 = Cone(Vec3(0,0,0),Vec3(L,0,0),R,R)
        gh = []
        for i in range(11):
            sec = trans(i*L/10,0,0)*g1
            gh.append(sec)
        g_h = Combine(*gh)
        g_l = Combine(trans(0,0,H/2)*g2,trans(0,0,H)*g2)

        self['外栏杆'] = g_h + g_l

if __name__ == "__main__":
    FinalGeometry = 外栏杆()
    FinalGeometry.replace()
    place(FinalGeometry)