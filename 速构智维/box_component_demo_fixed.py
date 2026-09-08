# -*- coding: utf-8 -*-
"""
BIMBase参数化立方体Component - 修正版
基于官方文档正确API用法：
- place(noumenon) 只接收一个Component参数
- 使用 translate * scale * Cube 创建立方体
- 使用 @export 装饰器导出replace方法
- 使用 Sweep(section, path) 创建拉伸体

官方文档确认的标准写法：
    self['几何'] = translate(x,y,z) * scale(L,W,H) * Cube()
    place(FinalGeometry)  # 只传一个参数

使用方法：
    1. VSCode中按F5运行（需配置Python Debugger连接到BIMBase）
    2. 或作为插件按钮触发执行
"""

from pyp3d import *
import math

# BIMBase不同版本中export装饰器可能不存在
try:
    from pyp3d import export
except ImportError:
    def export(func):
        return func


class BoxComponent(Component):
    """
    参数化立方体 - 官方标准框架
    在BIMBase属性面板中可修改长宽高和位置参数
    """

    def __init__(self, x=0, y=0, z=0, length=500, width=300, height=200):
        super().__init__()
        self['x'] = Attr(float(x), show=True)
        self['y'] = Attr(float(y), show=True)
        self['z'] = Attr(float(z), show=True)
        self['length'] = Attr(float(length), show=True)
        self['width'] = Attr(float(width), show=True)
        self['height'] = Attr(float(height), show=True)
        self['立方体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        """BIMBase自动调用：属性面板修改参数后触发重建"""
        x, y, z = self['x'], self['y'], self['z']
        L, W, H = self['length'], self['width'], self['height']
        if L <= 0: L = 100
        if W <= 0: W = 100
        if H <= 0: H = 100
        # 官方标准写法
        self['立方体'] = translate(x, y, z) * scale(L, W, H) * Cube()


class SweepBoxComponent(Component):
    """使用Sweep扫掠方式创建拉伸体"""

    def __init__(self, x=0, y=0, z=0, length=500, width=300, height=200):
        super().__init__()
        self['x'] = Attr(float(x), show=True)
        self['y'] = Attr(float(y), show=True)
        self['z'] = Attr(float(z), show=True)
        self['length'] = Attr(float(length), show=True)
        self['width'] = Attr(float(width), show=True)
        self['height'] = Attr(float(height), show=True)
        self['拉伸体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        x, y, z = self['x'], self['y'], self['z']
        L, W, H = self['length'], self['width'], self['height']
        if L <= 0: L = 100
        if W <= 0: W = 100
        if H <= 0: H = 100

        # 底面矩形截面（使用Vec2二维点，按官方文档）
        section = Section(
            Vec2(x, y),
            Vec2(x + L, y),
            Vec2(x + L, y + W),
            Vec2(x, y + W)
        )
        # 沿Z轴拉伸的轨迹线
        path = Line(Vec3(x, y, z), Vec3(x, y, z + H))
        self['拉伸体'] = Sweep(section, path)


# ============ 主入口 ============
if __name__ == "__main__":
    FinalGeometry = BoxComponent(0, 0, 0, 500, 300, 200)
    # place只接收一个Component参数，启动手动布置工具
    place(FinalGeometry)
