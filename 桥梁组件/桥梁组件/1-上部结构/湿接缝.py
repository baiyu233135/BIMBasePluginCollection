from pyp3d import *
class 湿接缝(Component):
    def __init__(self):
        Component.__init__(self)

        self['湿接缝数量'] = Attr(4, obvious=True)
        self['湿接缝间距'] = Attr(200, obvious=True)
        self['湿接缝长'] = Attr(3000, obvious=True)
        self['湿接缝上端宽'] = Attr(50, obvious=True)
        self['湿接缝上端高度'] = Attr(15, obvious=True)
        self['湿接缝下端高度'] = Attr(75, obvious=True)
        self['湿接缝'] = Attr(None, show=True)

        self.replace()
    @export
    def replace(self):
        n = self['湿接缝数量']
        k = self['湿接缝间距']
        c = self['湿接缝长'] 
        d = self['湿接缝上端宽'] 
        h = self['湿接缝上端高度']
        #长条
        box = Box(Vec3(0,0,0),Vec3(0,0,h),Vec3(1,0,0),Vec3(0,1,0),d,c,d,c)

        h2 = self['湿接缝下端高度']
        hou = 15
        zy = 52.5
        j = 720
        start = zy
        end = c - zy - hou
        span = end - start
        box2 = Box(Vec3(0,0,0),Vec3(0,0,-h2),Vec3(1,0,0),Vec3(0,1,0),d,hou,d,hou)
        sjfhgb = trans(0,zy,0) * box2
        if 2640 <= c <= 3360:
            count = 5
        else:
            count = 5 + max(0, int((c - 3360) // j)+1)
        if count < 2:
            count = 2
        if count == 1:
            gap = 0
        else:
            gap = span / (count - 1)
        temp = Combine()
        for i in range(count):
            x = start + i * gap
            temp = Combine(temp, trans(0, x - start, 0) * sjfhgb)
        all = Combine(temp , box)

        o = int((d * n + k * n)/(k+d))
        p = (d * n + k * n)/o
        temp2 = Combine()
        for i in range(o):
            temp2 = Combine(temp2,trans(i * p,0,0) * all)

        self['湿接缝'] = temp2
        
if __name__ == "__main__":    
    FinalGeometry = 湿接缝()
    place(FinalGeometry)