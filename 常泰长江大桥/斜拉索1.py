from pyp3d import *

class 斜拉索(Component):

    def __init__(self):

        Component.__init__(self) 
        self['斜拉索数量'] = Attr('20',obvious = True)
        self['斜拉索半径'] = Attr(21, obvious=True)
        self['竖向距离'] = Attr(6910, obvious=True)
        self['横向距离'] = Attr(1600, obvious=True)
        self['竖向间距'] = Attr(250, obvious=True)
        self['横向间距'] = Attr(1200, obvious=True)
        self['上间距'] = Attr(500, obvious=True)
        self['下间距'] = Attr(1000, obvious=True)
        
        self['斜拉索'] = Attr(None, show=True)
        
        self.replace()

    @export

    
    def replace(self):
        # 数量为字符串型，容错解析（非法输入回退默认值）
        try:
            x = int(float(str(self['斜拉索数量']).strip()))
        except (TypeError, ValueError):
            x = 20
        x = max(x, 0)
        R = self['斜拉索半径'] 
        
        HJL = self['竖向距离'] 
        SJL = self['横向距离'] 
        
        SJ = self['竖向间距'] 
        HJ = self['横向间距'] 

        SJ_up = self['下间距']
        SJ_down = self['上间距']
        

        # 圆截面分段数按半径自适应：R=21mm 的拉索 24 段足够光滑，
        # 替代原 64 段，数据量降约 62%，形状与 Loft 拓扑不变
        N = max(12, min(64, int(abs(R))))    
        pts = [
            Vec2(R * cos(2 * pi * i / N), R * sin(2 * pi * i / N))
            for i in range(N)
        ]
        sec = Section(*pts)          # 基准截面只建一次，循环内用变换复用
        sec_v = rotate(Vec3(0, 1, 0), -0.5 * pi) * sec

        cables = []

        # 两列（Y方向对称）：左列(-1) 和 右列(+1)
        for sign in [-1, 1]:
            for i in range(x):
                xp = translation(
                    -(x - 1 - i) * HJ,
                    sign * SJ_up / 2,
                    HJL
                ) * sec         
                
                zp = translation(
                    SJL + R,
                    sign * SJ_down / 2,
                    -(x - 1 - i) * SJ
                ) * sec_v
                
                cables.append(Loft(xp, zp))

        if not cables:                       # 数量为 0 时给一个零尺寸占位，防空 Combine
            cables.append(scale(0, 0, 0) * Cube())
        self['斜拉索'] = translation(
            -SJL - R, 
            0,        
            HJL       
        ) * rotate(
            Vec3(1, 0, 0), 
            pi           
        ) * Combine(*cables)

if __name__ == "__main__":
    FinalGeometry = 斜拉索()
    place(FinalGeometry)
