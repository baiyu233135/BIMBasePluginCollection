from pyp3d import *

class 桩基承台(Component):
    # 定义各个参数及其默认值
    def __init__(self):
        Component.__init__(self)
        self['构件类型'] = Attr('下部结构',obvious=True,readonly = True, group='构件分类')
        self['构件名称'] = Attr('桩基承台',obvious=True,readonly = True,group='构件分类')
        

        self['承台宽'] = Attr(750, obvious = True)
        self['承台长'] = Attr(985, obvious = True)
        self['承台高'] = Attr(200, obvious = True)
        self['桩半径'] = Attr(80, obvious = True)
        self['桩高'] = Attr(2200, obvious = True)
        self['单边桩基数量'] = Attr(2, obvious = True)
        self['桩基承台']=Attr(None, show = True)
        self.replace()
    @export
    def replace(self): 
        CD = self['承台宽']
        CL = self['承台长']
        ZD = self['桩半径']
        CT = self['承台高']
        ZT = self['桩高']
        y  = self['单边桩基数量']
        #单桩
        YW = max(150,ZD)
        zhuang = Cone(Vec3(150,150,0),Vec3(150,150,-ZT),ZD,ZD)
        #桩
        k = []
        if y > 1:
            JJ = (CD - 300) / (y - 1)  # 柱Y间距
            y_points = linspace(Vec3(0, 0, 0), Vec3(0, (y - 1) * JJ, 0), y)
            for y_point in y_points:
                k.append(translation(y_point) * zhuang)
        else:
            k.append(translation(0, CD/2 - 150, 0) * zhuang)

        k2 = translation(Vec3(CL - 300, 0, 0)) * k

        #承台
        chengtai = translation(Vec3(0,0,0))*Section(Vec2(0,0),Vec2(300,0),Vec2(300,CD/2-150),Vec2(CL-300,CD/2-150),Vec2(CL-300,0),Vec2(CL,0),Vec2(CL,CD),Vec2(CL-300,CD),Vec2(CL-300,CD/2+150),Vec2(300,CD/2+150),Vec2(300,CD),Vec2(0,CD))
        tline    = Line(Vec3(0,0,0),Vec3(0,0,CT))
        sweep    = Sweep(chengtai,tline)
        self['承台体积'] = Attr((300*CD*CT*2+300*(CL-300*2)*CT)*(10**-6),obvious = False,readonly = True, group='全局参数')
        self['桩基体积'] = Attr((ZD*ZD*pi*ZT*y*2)*(10**-6),obvious = False,readonly = True, group='全局参数')
        self[f'总体积'] = Attr(self['承台体积']+self['桩基体积'],obvious = True,readonly = True, group='全局参数')
        #组合
        TOTAL  = Combine(k,sweep,k2)
 
        self['桩基承台'] = TOTAL

if __name__ == "__main__":
    Final_Geometry = 桩基承台()
    place(Final_Geometry)