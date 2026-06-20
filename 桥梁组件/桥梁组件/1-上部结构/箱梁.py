from pyp3d import *

class 箱梁(Component):
    def __init__(self):
        Component.__init__(self)
        self['底板宽度'] = Attr(80 , obvious = True)
        self['底板厚度'] = Attr(25 , obvious = True)

        self['顶板厚度'] = Attr(15 , obvious = True)

        self['腹板厚度'] = Attr(25 , obvious = True)
        self['箱梁高度'] = Attr(100, obvious = True)

        self['左翼缘长度'] = Attr(30 , obvious = True)
        self['右翼缘长度'] = Attr(30, obvious = True)

        self['箱梁长']  = Attr(3000  , obvious = True)
        self['箱梁']  = Attr(None,show=True)
        self.replace()
    @export
    def replace(self): 
        BD = self['底板宽度']
        Bhou = self['底板厚度']
        Thou = self['顶板厚度']
        Fhou = self['腹板厚度']
        H  = self['箱梁高度']
        W = self['左翼缘长度']
        WW = self['右翼缘长度']
        long = self['箱梁长']

        #镂空
        #腹板高
        fh = H - Thou
        #下导角
        a = 5
        ay = (fh-5)/30
        ax = 1
        fx = ((a**2)/((ay**2)+(ax**2))) ** 0.5
        fy = ay*(fx)
        x = (Bhou)/ay
        lkxx = BD/2-(Fhou-x)-5
        #上导角
        b = 15
        c = (((fh**2)+(((30/(fh-5))*fh)**2))**0.5)-5
        cx = ((c**2)/((ay**2)+(ax**2))) ** 0.5
        cy = ay*(cx)
        lksx =(b-fx)
        section = translation(0,0,0) * rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(lkxx,Bhou),Vec2(lkxx+ a +fx,Bhou+fy),Vec2(BD/2+(cx-Fhou),cy),Vec2((BD/2+(cx-Fhou))-lksx,fh),Vec2(-((BD/2+(cx-Fhou))-lksx),fh),Vec2(-(BD/2+(cx-Fhou)),cy),Vec2(-(lkxx+a+fx),Bhou+fy),Vec2(-lkxx,Bhou))
        #外截面
        ssection = translation(0,0,0) * rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(-BD/2,0),Vec2(-BD/2-30,H-Thou-5),Vec2(-BD/2-30-15,H-Thou),Vec2(-BD/2-30-W,H-Thou),Vec2(-BD/2-30-W,H),Vec2(BD/2+30+WW,H),Vec2(BD/2+30+WW,H-Thou),Vec2(BD/2+30+15,H-Thou),Vec2(BD/2+30,H-Thou-5),Vec2(BD/2,0))
        New = ssection - section
        
        line= Line(Vec3(0,0,0),Vec3(0,long,0))
        sweep = Sweep(New,line)

        #横隔板
        #中心点左右60,横隔板厚15,初始间距720
        hou = 15
        zy = 52.5
        j = 720
        start = zy
        end = long - zy - hou
        span = end - start
        #横隔板数量
        if 2640 <= long <= 3360:
            count = 5
        else:
            count = 5 + max(0, int((long - 3360) // j)+1)
        if count < 2:
            count = 2
        if count == 1:
            gap = 0
        else:
            gap = span / (count - 1)
        temp = Combine()
        if W == WW:
            hgb = trans(0,zy,0) * rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(-BD/2-10/ay,10),Vec2(-BD/2-30-W,10),Vec2(-BD/2-30-W,H-Thou),Vec2(-BD/2-30-15,H-Thou),Vec2(-BD/2-30,H-Thou-5))
            lines = Line(Vec3(0,zy,0),Vec3(0,zy+hou,0))
            hgbz = Sweep(hgb,lines)
            hgby = mirror(trans(0,zy,0) * rotz(0)) * hgbz
            hgbzy = Combine(hgbz,hgby)
            start = zy
            for i in range(count):
                x = start + i * gap
                temp = Combine(temp, trans(0, x - start, 0) * hgbzy)
        elif W > WW:
            hgb = rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(BD/2+10/ay,10),Vec2(BD/2+30+WW,10),Vec2(BD/2+30+WW,H-Thou),Vec2(BD/2+30+15,H-Thou),Vec2(BD/2+30,H-Thou-5))
            lines = Line(Vec3(0,zy,0),Vec3(0,zy+hou,0))
            hgby = trans(0,zy,0) * Sweep(hgb,lines)
            for i in range(count):
                x = start + i * gap
                temp = Combine(temp, trans(0, x - start, 0) * hgby)            
        else:
            hgb = rotate(Vec3(1,0,0),0.5*pi) * Section(Vec2(-BD/2-10/ay,10),Vec2(-BD/2-30-W,10),Vec2(-BD/2-30-W,H-Thou),Vec2(-BD/2-30-15,H-Thou),Vec2(-BD/2-30,H-Thou-5))
            lines = Line(Vec3(0,zy,0),Vec3(0,zy+hou,0))
            hgbz = trans(0,zy,0) * Sweep(hgb,lines)
            for i in range(count):
                x = start + i * gap
                temp = Combine(temp, trans(0, x - start, 0) * hgbz)           
        self['箱梁'] =Combine(sweep,temp)
        
if __name__ == "__main__":
    Final_Geometry = 箱梁()
    place(Final_Geometry)