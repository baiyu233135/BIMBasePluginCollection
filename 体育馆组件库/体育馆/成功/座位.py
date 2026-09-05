from pyp3d import *

class 座位(Component):
    def __init__(self):
        Component.__init__(self)
        self['座位高度'] = Attr(100,obvious = True)
        self['座位宽度'] = Attr(50, obvious=True)
        self['间隔'] = Attr(10, obvious=True)
        self['座位个数'] = Attr('10', obvious=True)

        self['座位'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        W = self['间隔']
        H = self['座位高度']
        w = self['座位宽度']
        s1 = self['座位个数']
        result1 = 0
        for a in s1:
            result1 = result1 * 10 + (ord(a) - ord('0'))
        x1 = result1
        sec = Section(Vec2(0,0),Vec2(w,0),Vec2(w,10),Vec2(10,10),
                      Vec2(10,H),Vec2(0,H),Vec2(0,0))
        seat = rotate(Vec3(1,0,0),pi/2)*sec
        se = Loft(seat,trans(0,w,0)*seat)
        s = []
        for i in range(x1):
            s.append(trans(0,i*(W+w),0)* se)
        self['座位'] = Combine(*s)

if __name__ == '__main__':
    FinalGeometry = 座位()
    FinalGeometry.replace()
    place(FinalGeometry)
