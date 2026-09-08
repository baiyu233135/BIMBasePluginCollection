from pyp3d import * 

class 引桥桥墩(Component):

    def __init__(self):
        Component.__init__(self) 

        self['墩高'] = Attr(600, obvious=True)
        self['桩长'] = Attr(600, obvious=True)

        self['桥墩'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):

        DG = self['墩高']
        ZC = self['桩长']
        N = 64
        R = 125

        SLP = Section(Vec2(0,0),Vec2(1410,0),
                      Vec2(1680,120),Vec2(1680,300),
                      Vec2(1650,300),Vec2(1650,250),
                      Vec2(-240,250),Vec2(-240,300),
                      Vec2(-270,300),Vec2(-270,120))
        section = rotate(Vec3(1,0,0),0.5*pi) * SLP
        line = Line(Vec3(0,0,0),Vec3(0,300,0))
        SL1 = Sweep(section, line)
        SL = translate(-R*2,-R,ZC+DG) * SL1
# 1. 生成圆形截面（和你T梁的Section写法完全一致）
        circle_pts = [
            Vec2(R * cos(2 * pi * i / N), R * sin(2 * pi * i / N))
            for i in range(N)
        ]
        sec = Section(*circle_pts)
        YZ = translate(-R, 0, 0) * Loft(sec, translate(0, 0, ZC+DG) * sec)
        YZ2 = translate(1160,0,0)*YZ

        # ====================== 3. 横向系梁建模（修正位置，匹配桩基） ======================
        # 系梁竖向间距（两道系梁均分墩高）

        XL1 = translate(-100, -100, ZC-200) * scale(1140, 200, 200) * Cube()
        XL2 = translate(-100, -100, ZC+DG/2-100) * scale(1140, 200, 200) * Cube()

        # ====================== 4. 模型合并（修正拼接逻辑） ======================

        self['桥墩'] =XL1+XL2+YZ+YZ2+SL

if __name__ == "__main__":
    FinalGeometry = 引桥桥墩()
    place(FinalGeometry)