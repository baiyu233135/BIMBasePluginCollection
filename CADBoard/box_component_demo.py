# -*- coding: utf-8 -*-
"""
BIMBase参数化立方体Component - v2.0 确定可用版

使用方法（在BIMBase底部"在此输入命令"框中逐行输入）：

第1步 - 导入：
    exec(open(r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard\box_component_demo.py').read())

第2步 - 创建组件：
    box = BoxComponent()

第3步 - 查看结果（直接输入变量名回车）：
    box

然后就能在BIMBase三维视图中看到参数化立方体，
在左侧"属性"面板中可以修改长宽高参数。
"""

try:
    from pyp3d import Component, Attr, Section, Point, place
except ImportError:
    raise ImportError("必须在BIMBase环境中运行！")


class BoxComponent(Component):
    """
    参数化立方体 - 底面矩形，沿Z轴拉伸
    
    使用方法：
        box = BoxComponent(0, 0, 0, 500, 300, 200)
        box  # 显示在BIMBase三维视图中
    """

    def __init__(self, x=0, y=0, z=0, length=500, width=300, height=200):
        # 必须先调用Component基类初始化
        super(BoxComponent, self).__init__()

        # 保存参数到实例变量（_build和replace都从这里读取）
        self._x = float(x)
        self._y = float(y)
        self._z = float(z)
        self._length = float(length)
        self._width = float(width)
        self._height = float(height)

        # 注册BIMBase参数（show=True表示在属性面板中显示可编辑）
        # 参数修改后BIMBase会自动调用 replace() 方法
        self['x'] = Attr(self._x, show=True)
        self['y'] = Attr(self._y, show=True)
        self['z'] = Attr(self._z, show=True)
        self['length'] = Attr(self._length, show=True)
        self['width'] = Attr(self._width, show=True)
        self['height'] = Attr(self._height, show=True)

        # 立即构建3D几何
        self._build()

    def replace(self):
        """
        BIMBase自动调用：用户在属性面板修改参数后触发
        从Component中获取最新值，然后重新构建几何
        """
        # 安全获取最新值（兼容不同BIMBase版本）
        self._x = self._get_value('x')
        self._y = self._get_value('y')
        self._z = self._get_value('z')
        self._length = self._get_value('length')
        self._width = self._get_value('width')
        self._height = self._get_value('height')

        # 重新构建
        self._build()

    def _get_value(self, key):
        """安全从Component获取值"""
        try:
            val = self[key]
            # 如果是Attr对象，取.value
            if hasattr(val, 'value'):
                return float(val.value)
            # 如果已经是数值，直接返回
            return float(val)
        except Exception:
            # 获取失败时返回0
            return 0.0

    def _build(self):
        """构建立方体3D几何"""
        x, y, z = self._x, self._y, self._z
        L, W, H = self._length, self._width, self._height

        # 参数有效性检查
        if L <= 0:
            L = 100
        if W <= 0:
            W = 100
        if H <= 0:
            H = 100

        # 底面矩形截面（二维坐标列表）
        # 顺序：左下 -> 右下 -> 右上 -> 左上 -> 闭合
        section = Section([
            [x,     y    ],
            [x + L, y    ],
            [x + L, y + W],
            [x,     y + W],
            [x,     y    ],  # 闭合
        ])

        # 沿Z轴方向拉伸H距离，生成3D立方体
        # t: 起始位置（3D点）
        # n: 方向向量（Z轴方向）
        # angle: 拉伸距离（即高度）
        self['图形'] = place(
            section,
            t=Point(x, y, z),
            n=Point(0, 0, 1),
            angle=H
        )

    def __repr__(self):
        return f"BoxComponent({self._x},{self._y},{self._z} L={self._length} W={self._width} H={self._height})"


class ChamferBoxComponent(Component):
    """带倒角的参数化立方体"""

    def __init__(self, x=0, y=0, z=0, length=500, width=300, height=200, chamfer=20):
        super(ChamferBoxComponent, self).__init__()

        self._x = float(x)
        self._y = float(y)
        self._z = float(z)
        self._length = float(length)
        self._width = float(width)
        self._height = float(height)
        self._chamfer = float(chamfer)

        self['x'] = Attr(self._x, show=True)
        self['y'] = Attr(self._y, show=True)
        self['z'] = Attr(self._z, show=True)
        self['length'] = Attr(self._length, show=True)
        self['width'] = Attr(self._width, show=True)
        self['height'] = Attr(self._height, show=True)
        self['chamfer'] = Attr(self._chamfer, show=True)

        self._build()

    def replace(self):
        self._x = self._get_value('x')
        self._y = self._get_value('y')
        self._z = self._get_value('z')
        self._length = self._get_value('length')
        self._width = self._get_value('width')
        self._height = self._get_value('height')
        self._chamfer = self._get_value('chamfer')
        self._build()

    def _get_value(self, key):
        try:
            val = self[key]
            if hasattr(val, 'value'):
                return float(val.value)
            return float(val)
        except Exception:
            return 0.0

    def _build(self):
        x, y, z = self._x, self._y, self._z
        L, W, H = self._length, self._width, self._height
        C = self._chamfer

        if L <= 0:
            L = 100
        if W <= 0:
            W = 100
        if H <= 0:
            H = 100

        # 限制倒角不超过边长一半
        C = min(C, L / 2, W / 2)
        C = max(0, C)

        if C <= 0:
            # 无倒角，标准矩形
            points = [
                [x,     y    ],
                [x + L, y    ],
                [x + L, y + W],
                [x,     y + W],
                [x,     y    ],
            ]
        else:
            # 带倒角（8个点）
            points = [
                [x + C,     y        ],  # 下边起点
                [x + L - C, y        ],  # 下边终点
                [x + L,     y + C    ],  # 右边起点
                [x + L,     y + W - C],  # 右边终点
                [x + L - C, y + W    ],  # 上边终点
                [x + C,     y + W    ],  # 上边起点
                [x,         y + W - C],  # 左边终点
                [x,         y + C    ],  # 左边起点
                [x + C,     y        ],  # 闭合
            ]

        section = Section(points)
        self['图形'] = place(section, t=Point(x, y, z), n=Point(0, 0, 1), angle=H)

    def __repr__(self):
        return f"ChamferBoxComponent(L={self._length} W={self._width} H={self._height} C={self._chamfer})"
