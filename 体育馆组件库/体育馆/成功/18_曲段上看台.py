from pyp3d import *

class 曲段上看台(Component):
    def __init__(self):
        Component.__init__(self)
        self['宽度'] = Attr(22900,obvious = True)
        self['高度'] = Attr(11112, obvious=True)
        self['挡板宽'] = Attr(50, obvious=True)
        self['挡板高'] = Attr(1000, obvious=True)

        self['曲段上看台'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        H = self['高度']
        W = self['宽度']
        CW = W/33200.04*18110
        High = self['挡板高']
        w = self['挡板宽']
        l1 = 3000
        n = 21
        pts = []
        pts.append(Vec2(0, 0))        
        pts.append(Vec2(W, 0))            
        for i in range(n):
            pts.append(Vec2(W - CW/20*i, H/21*(i+1)))   
            if i < n - 1:
                pts.append(Vec2(W - CW/20*(i+1), H/21*(i+1)))  
        pts.append(Vec2(W - CW, H))      
        pts.append(Vec2(0, H))    
        pts.append(Vec2(0, 0))        

        section = rotate(Vec3(1,0,0),pi/2)*Section(*pts)
        path = Line(Vec3(0,0,0), Vec3(0,l1,0))
        louti = Sweep(section, path)
        db_sec = Section(Vec2(0,0),Vec2(w,0),Vec2(w,l1),Vec2(0,l1),Vec2(0,0))
        db = Loft(db_sec,trans(0,0,High)*db_sec)
        db1 = trans(W,0,0)*db

        louti1 = trans(1140,-l1*2.53,0)*rotate(Vec3(0,0,1),pi/12)*section
        louti2 = trans(1140,l1*3.53,0)*rotate(Vec3(0,0,1),-pi/12)*section
        lout1 = Loft(louti1,section)
        lout2 = Loft(trans(0,l1,0)*section,louti2)
        unit_1 = Combine(lout1,lout2,louti) 
        unit_3 = trans(18250,l1*10.3,0)*rotate(Vec3(0,0,1),-pi/6*2)*Combine(unit_1,db1)

        unit_2 = trans(4450,l1*5.88,0)*rotate(Vec3(0,0,1),-pi/6)*unit_1

        self['曲段上看台'] = Combine(unit_1+db1,unit_2+db1,unit_3)

if __name__ == '__main__':
    FinalGeometry = 曲段上看台()
    FinalGeometry.replace()
    place(FinalGeometry)
