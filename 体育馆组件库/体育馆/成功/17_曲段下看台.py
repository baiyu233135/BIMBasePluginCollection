from pyp3d import *

class 曲段下看台(Component):
    def __init__(self):
        Component.__init__(self)
        self['宽度'] = Attr(33200.04,obvious = True)
        self['高度'] = Attr(5905.51, obvious=True)
        self['挡板宽'] = Attr(50, obvious=True)
        self['挡板高'] = Attr(1000, obvious=True)

        self['曲段下看台'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        H = self['高度']
        W = self['宽度']
        CW = W/33200.04*15846.46
        High = self['挡板高']
        w = self['挡板宽']
        l1 = 3403.77
        n = 21
        pts = []
        pts.append(Vec2(0, 0))            
        for i in range(n):
            pts.append(Vec2(-CW/20*i, H/21*(i+1)))   
            if i < n - 1:
                pts.append(Vec2(-CW/20*(i+1), H/21*(i+1)))  
        pts.append(Vec2(-CW, H))      
        pts.append(Vec2(-W, H))    
        pts.append(Vec2(-W, 0))        
        pts.append(Vec2(0, 0))        

        section = rotate(Vec3(1,0,0),pi/2)*Section(*pts)
        db_sec = Section(Vec2(0,0),Vec2(w,0),Vec2(w,l1),Vec2(0,l1),Vec2(0,0))
        db = Loft(db_sec,trans(0,0,High)*db_sec)
        db1 = trans(W,0,0)*db
        x1 = 3281.59

        mian1 = rotate(Vec3(0,0,1),-pi/10)*section
        mian2 = trans(0,-x1,0)*rotate(Vec3(0,0,1),pi/10)*section
        mian3 = trans(1807,-x1-2889,0)*rotate(Vec3(0,0,1),pi/10*2)*section
        mian4 = trans(4737,-x1-4346,0)*rotate(Vec3(0,0,1),pi/10*3)*section
        mian5 = trans(4737,-x1-4346,0)*rotate(Vec3(0,0,1),pi/10*4)*section

        kuai1 = Loft(mian1,section)
        kuai2 = Loft(section,mian2)
        kuai3 = Loft(mian2,mian3)
        kuai4 = Loft(mian3,mian4)
        kuai5 = Loft(mian4,mian5)
        kuai = Combine(kuai1,kuai2,kuai3,kuai4,kuai5)


        self['曲段下看台'] = Combine(kuai)

if __name__ == '__main__':
    FinalGeometry = 曲段下看台()
    FinalGeometry.replace()
    place(FinalGeometry)