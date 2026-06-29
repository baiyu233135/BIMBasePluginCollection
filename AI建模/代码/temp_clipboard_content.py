from pyp3d import *

class 定位立方体(Component):
    def __init__(self):
        Component.__init__(self)
        # 定义组件属性
        self['X坐标'] = Attr(100.0, obvious=True)
        self['Y坐标'] = Attr(100.0, obvious=True)
        self['Z坐标'] = Attr(100.0, obvious=True)
        self['立方体'] = Attr(None, show=True)
        self.replace()
    
    @export
    def replace(self):
        # 获取坐标参数
        x = self['X坐标']
        y = self['Y坐标']
        z = self['Z坐标']
        
        # 生成立方体模型
        # Cube()生成单位立方体，通过translate平移到指定坐标
        cube = translate(x, y, z) * Cube()
        self['立方体'] = cube

if __name__ == '__main__':
    # 创建组件实例
    final_geometry = 定位立方体()
    # 布置组件
    place(final_geometry)
