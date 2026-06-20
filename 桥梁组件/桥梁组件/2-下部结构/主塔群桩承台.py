from pyp3d import *
from math import atan

class 主塔群桩承台(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['构件类型'] = Attr('下部结构',obvious=True,readonly = True, group='构件分类')
        self['构件名称'] = Attr('主塔群桩承台',obvious=True,readonly = True,group='构件分类')

        self['承台长'] = Attr(3982.7, obvious=True)
        self['承台宽'] = Attr(2280, obvious=True)
        self['承台高'] = Attr(600, obvious=True)
        self['桩基长度'] = Attr(7600, obvious=True)
        self['桩基半径'] = Attr(140, obvious=True)

        self['主塔群桩承台'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        CTW = self['承台宽']
        CTL = self['承台长']
        CTH = self['承台高']

        DZH = self['桩基长度']
        R = self['桩基半径']

        R1=50

        test_section = translate((CTL-R1*2)/2,(CTW-R1*2)/2,0) *Section(Vec2(R1,-(CTW-R1*2)/2), scale(R1) * Arc(0.5*pi), Vec2(-(CTL-R1*2)/2,R1), Vec2(-(CTL-R1*2)/2,-(CTW-R1*2)/2))

        # 复制并旋转四个
        s0 = test_section
        s1 = mirror_axis(Vec3(0,1,0))*test_section
        s2 = mirror_axis(Vec3(1,0,0))*test_section
        s3 = mirror_axis(Vec3(0,0,1))*test_section
        zzzz = s0 + s1 + s2 + s3

        section3 = Loft(zzzz, translate(0, 0, CTH) * zzzz)


        # 桩基
        ZJ_array = []
        for i in range(3):      # 行
            for j in range(4):  # 列
                ZJ_array.append(
                    translate(i * (CTL/2-240-551.3)/2, j * (CTW-240-240)/3, 0) * rotate(Vec3(1, 0, 0), pi) * Cone(
                        Vec3(0, 0, 0),
                        Vec3(0, 0, DZH),
                        R,
                        R
                    )
                )
        ZJ = translate(551.3, -(CTW-240-240)/2, 10) *Combine(*ZJ_array)
        ZJ1 = mirror_yoz() * ZJ

        self['承台体积'] = Attr((((CTL - 2*R1) * (CTW - 2*R1) + pi * R1**2) * CTH)*(10**-6),obvious = False,readonly = True, group='全局参数')
        self['桩基体积'] = Attr((24 * pi * R**2 * DZH)*(10**-6),obvious = False,readonly = True, group='全局参数')
        self[f'总体积'] = Attr(self['承台体积']+self['桩基体积'],obvious = True,readonly = True, group='全局参数')

        self['主塔群桩承台'] =  section3 + ZJ + ZJ1
if __name__ == "__main__":    
    FinalGeometry = 主塔群桩承台()
    place(FinalGeometry)