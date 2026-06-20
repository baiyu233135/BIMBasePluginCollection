from pyp3d import *
from math import atan

class 波形护栏(Component):
    def __init__(self):
        Component.__init__(self)
        # 单位为cm
        self['长'] = Attr(800, obvious=True)
        self['半径'] = Attr(7, obvious=True)
        self['立柱高度'] = Attr(150, obvious=True)
        self['波形护栏'] = Attr(None, show=True)
        self['间距'] = Attr(400, obvious=True)
        self.replace()

    @export
    def replace(self):

        L=self['长']
        R=self['半径']
        zH=self['立柱高度']
        spacing = self['间距']

        ZJ_array = []
        count = max(1, int(L // spacing)) + 1
        for i in range(count):
            ZJ_array.append(
                translate(0, i*spacing, 0) * Cone(Vec3(0, 0, 0), Vec3(0, 0, zH), R, R)
            )
        ZJ_array.append(translate(0, L-3.6, 0) * Cone(Vec3(0, 0, 0), Vec3(0, 0, zH), R, R))
        ZJ_all = Combine(*ZJ_array)

        section =Section(Vec2(0,0),Vec2(-0.8, 0),
                                                Vec2(-7.4-0.8, 5),
                                                  Vec2(-7.4-0.8, 5+1.6), 
                                                  Vec2(-0.8, 5+1.6+5),
                                                    Vec2(-0.8, 5+1.6+5+1.6),
                                                      Vec2(-7.4-0.8, 5+1.6+5+1.6+5),
                                                      Vec2(-7.4-0.8, 5+1.6+5+1.6+5+1.6),
                                                      Vec2(-0.8,  5+1.6+5+1.6+5+1.6+5),
                                                      Vec2(-0.8, 5+1.6+5+1.6+5+1.6+5+1.6),
                                                      Vec2(-7.4-0.8,5+1.6+5+1.6+5+1.6+5+1.6+5),
                                                      Vec2(-7.4-0.8, 5+1.6+5+1.6+5+1.6+5+1.6+5+1.6),
                                                      Vec2(-0.8,  5+1.6+5+1.6+5+1.6+5+1.6+5+1.6+5),Vec2(0,5+1.6+5+1.6+5+1.6+5+1.6+5+1.6+5),

                                                      Vec2(0,5+1.6+5+1.6+5+1.6+5+1.6+5+1.6+5-0.2),
                                                      Vec2(-0.8,  5+1.6+5+1.6+5+1.6+5+1.6+5+1.6+5-0.2),
                                                      Vec2(-7.4-0.8+0.2, 5+1.6+5+1.6+5+1.6+5+1.6+5+1.6-0.1),
                                                      Vec2(-7.4-0.8+0.2,5+1.6+5+1.6+5+1.6+5+1.6+5+0.1),
                                                      Vec2(-0.8+0.2, 5+1.6+5+1.6+5+1.6+5+1.6+0.1),
                                                      Vec2(-0.8+0.2,  5+1.6+5+1.6+5+1.6+5-0.1),
                                                      Vec2(-7.4-0.8+0.2, 5+1.6+5+1.6+5+1.6-0.1),
                                                      Vec2(-7.4-0.8+0.2, 5+1.6+5+1.6+5+0.1),
                                                      Vec2(-0.8+0.2, 5+1.6+5+1.6+0.1),
                                                      Vec2(-0.8+0.2, 5+1.6+5-0.1),
                                                        Vec2(-7.4-0.8+0.2, 5+1.6-0.1), 
                                                        Vec2(-7.4-0.8+0.2, 5+0.1),
                                                        Vec2(-0.8+0.2, 0.2),
                                                        Vec2(0,0.2))
       
        section1 =  translate(-(R+1.6+7.4+0.8)+9.8,-R,zH) *rotate(Vec3(1,0,0),- 0.5*pi) *Loft(section, translate(0, 0,L+2*R) * section)


        self['波形护栏'] = rotate(Vec3(0,0,1),-0.5*pi) *(section1+ZJ_all)
if __name__ == "__main__":
    FinalGeometry = 波形护栏()
    TwoPointPlace.linearize(FinalGeometry, '长')
    place(FinalGeometry)