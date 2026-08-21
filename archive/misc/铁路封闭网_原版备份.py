from pyp3d import *
import math

class 铁路封闭网(Component):
    def __init__(self):
        Component.__init__(self)
        self['长杆半径'] = Attr(40,obvious = True)
        self['长杆高'] = Attr(3000,obvious = True)
        self['侧长'] = Attr(500,obvious = True)

        self['线半径'] = Attr(10,obvious = True)

        self['单块网长度'] = Attr(9000,obvious = True)
        self['单块网高度'] = Attr(2800,obvious = True)
        self['网长'] = Attr(100,obvious = True)
        
        self['铁路封闭网'] = Attr(None,show = True)

        self.replace()

    @export
    def replace(self):
        N = 32
        R1 = self['长杆半径']
        circle_pts_down = [
            Vec2(R1 * cos(2 * pi * c / N), R1 * sin(2 * pi * c / N))
            for c in range(N)
        ]
        sec_long = Section(*circle_pts_down)
        R2 = self['线半径']
        circle_pts_down = [
            Vec2(R2 * cos(2 * pi * c / N), R2 * sin(2 * pi * c / N))
            for c in range(N)
        ]
        sec_short = Section(*circle_pts_down)
        long = self['长杆高']
        up = self['侧长']
        wind = self['单块网高度']
        x = self['单块网长度']
        y = self['网长']
        k = 100
        frame_long = y-2*R1-2*k
        z = int(frame_long//x)
        
        pillar_unit = Loft(sec_long,trans(0,0,long)*sec_long)
        box = trans(0,-R1,0)*scale(k+R1,k,k)*Cube()
        pillar_first_down = pillar_unit + trans(0,0,long-300)*box + trans(0,0,long-300-long/5)*box + trans(0,0,long-300-long/5*2)*box + trans(0,0,long-300-long/5*3)*box
        pillar_last_down = trans(y,0,0)*rotate(Vec3(0,0,1),pi)*pillar_first_down
        pillar_up_unit = Loft(sec_long,trans(0,0,up)*sec_long)
        pillar_up = trans(0,R1/2,long-R1)*rotate(Vec3(1,0,0),pi/4)*pillar_up_unit
        pillar_first = pillar_first_down + pillar_up
        pillar_last = pillar_last_down + trans(y,0,0)*pillar_up
        pillar_line_wide_unit = Loft(sec_short, trans(0,0,up)*sec_short)
        pillar_line_long_unit = rotate(Vec3(0,1,0), pi/2) * Loft(sec_short, trans(0,0,y)*sec_short)
        pl_el = int(y - 2*k)
        pl_ew = int(up - 2*k)
        pl_ell = int(pl_el // k)
        pl_eww = int(pl_ew // k)
        pillar_line_wide_list = []
        for i in range(pl_ell):
            pillar_line_wide_list.append(trans(pl_el % k + i*k + k, k/2, 0) * pillar_line_wide_unit)
        pillar_line_wide = Combine(*pillar_line_wide_list)
        pillar_line_long_list = []
        for i in range(pl_eww):
            pillar_line_long_list.append(trans(0, k/2, pl_ew % k + i*k + k) * pillar_line_long_unit)
        pillar_line_long = Combine(*pillar_line_long_list)
        pillar_line = trans(0, R1/2, long-R1) * rotate(Vec3(1,0,0), pi/4) * (pillar_line_long + pillar_line_wide)
        pillar = Combine(pillar_first,pillar_last,pillar_line)

        line_unit_wide = Loft(sec_short,trans(0,0,wind)*sec_short)
        line_unit_long = rotate(Vec3(0,1,0),pi/2)*Loft(sec_short,trans(0,0,x)*sec_short)
        line_end_long = rotate(Vec3(0,1,0),pi/2)*Loft(sec_short,trans(0,0,frame_long-x*z)*sec_short)
        line_end_long2 = rotate(Vec3(0,1,0),pi/2)*Loft(sec_short,trans(0,0,frame_long-x*z+x)*sec_short)
        
        el = int(x-2*k)
        ew = int(wind-2*k)
        ell = int(el//k)
        eww = int(ew//k)
        end_l = int((frame_long-z*x)-2*k)
        end_ll = int(end_l//k)
        end_lll = int(((frame_long-z*x+x)-2*k)//k)
        frame_list = []
        line_end_long_list = []
        line_end_wide_list = []
        line_long_list = []
        line_wide_list = []
        if z > 0:
            if int(frame_long%x) <= 200:
                frame_unit = scale(x,k,wind)*Cube()-trans(k,0,k)*scale(x-k*2,k,wind-k*2)*Cube()
                for i in range(eww):
                    line_long_list.append(trans(0,k/2,ew%k+i*k+k)*line_unit_long)
                line_long = Combine(*line_long_list)
                for i in range(ell):
                    line_wide_list.append(trans(el%k+i*k+k,k/2,0)*line_unit_wide)
                line_wide = Combine(*line_wide_list)
                frame = Combine(line_long,line_wide,frame_unit)
                for i in range(z-1):
                    frame_list.append(trans(i*x,0,0)*frame)
                frame_unit_all = Combine(*frame_list)
                frame_unit_end = scale(frame_long-x*z+x,k,wind)*Cube()-trans(k,0,k)*scale(frame_long-x*z-k*2+x,k,wind-k*2)*Cube()
                for i in range(eww):
                    line_end_long_list.append(trans(0,k/2,ew%k+i*k+k)*line_end_long2)
                line_end_long = Combine(*line_end_long_list)
                for i in range(end_lll):
                    line_end_wide_list.append(trans(el%k+i*k+k,k/2,0)*line_unit_wide)
                line_end_wide = Combine(*line_end_wide_list)
                frame_unit_end = Combine(line_end_long,line_end_wide,frame_unit_end)
                frame_all = Combine(trans(k+R1,-R1,long-wind)*frame_unit_all,trans(k+R1+x*z-x,-R1,long-wind)*frame_unit_end)
            else:
                frame_unit = scale(x,k,wind)*Cube()-trans(k,0,k)*scale(x-k*2,k,wind-k*2)*Cube()
                for i in range(eww):
                    line_long_list.append(trans(0,k/2,ew%k+i*k+k)*line_unit_long)
                line_long = Combine(*line_long_list)
                for i in range(ell):
                    line_wide_list.append(trans(el%k+i*k+k,k/2,0)*line_unit_wide)
                line_wide = Combine(*line_wide_list)
                frame = Combine(line_long,line_wide,frame_unit)
                for i in range(z):
                    frame_list.append(trans(i*x,0,0)*frame)
                frame_unit_all = Combine(*frame_list)
                frame_unit_end = scale(frame_long-x*z,k,wind)*Cube()-trans(k,0,k)*scale(frame_long-x*z-k*2,k,wind-k*2)*Cube()
                for i in range(eww):
                    line_end_long_list.append(trans(0,k/2,ew%k+i*k+k)*line_end_long)
                line_end_long = Combine(*line_end_long_list)
                for i in range(end_ll):
                    line_end_wide_list.append(trans(el%k+i*k+k,k/2,0)*line_unit_wide)
                line_end_wide = Combine(*line_end_wide_list)
                frame_unit_end = Combine(line_end_long,line_end_wide,frame_unit_end)
                frame_all = Combine(trans(k+R1,-R1,long-wind)*frame_unit_all,trans(k+R1+x*z,-R1,long-wind)*frame_unit_end)
        else:
            frame_unit_end = scale(frame_long-x*z,k,wind)*Cube()-trans(k,0,k)*scale(frame_long-x*z-k*2,k,wind-k*2)*Cube()
            for i in range(eww):
                line_end_long_list.append(trans(0,k/2,ew%k+i*k+k)*line_end_long)
            line_end_long = Combine(*line_end_long_list)
            for i in range(end_ll):
                line_end_wide_list.append(trans(el%k+i*k+k,k/2,0)*line_unit_wide)
            line_end_wide = Combine(*line_end_wide_list)
            frame_unit_end = Combine(line_end_long,line_end_wide,frame_unit_end)
            frame_all = trans(k+R1,-R1,long-wind)*frame_unit_end
        all = Combine(frame_all,pillar)

        self['铁路封闭网'] = all

if __name__ == "__main__":
    FinalGeometry = 铁路封闭网()
    TwoPointPlace.linearize(FinalGeometry,'网长')
    place(FinalGeometry)
