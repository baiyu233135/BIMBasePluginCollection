from pyp3d import *

# 定义圆柱体组件
class 圆柱体(Component):
    def __init__(self):
        Component.__init__(self)
        self['圆柱体'] = Attr(None, show=True)
        self.replace()
    
    @export
    def replace(self):
        # 创建一个圆柱体，底面圆心在(0, 0, 0)，顶面圆心在(0, 0, 100)，底面和顶面半径均为50
        # 当两个半径相等时，Cone函数生成的是圆柱体
        self['圆柱体'] = Cone(Vec3(0, 0, 0), Vec3(0, 0, 100), 50, 50).color(1, 0, 0, 1)

if __name__ == "__main__":
    demo = 圆柱体()
    place(demo)
