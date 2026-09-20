---
name: PlaceInterface
description: 布置接口（旋转、两点线性）使用指南
author: BIMBase SDK Team
version: "1.0"
doc_type: sdk_interface
---

## 功能说明

提供两种标准布置模式，用于将参数化组件快速定位到目标位置。

**适用场景：**<br>
- **旋转布置**：需要绕指定原点旋转放置（如沿路径转角、对齐局部坐标系）<br>- **两点布置**：需沿线性变量均匀排布（如管廊、护栏连续铺设）

## 核心约束

| 模式 | 关键限制 |
|------|----------|
| **旋转布置** | 1. `RotationFunction` 为内部函数，不可直接导入<br>2. 原点由鼠标交互选择，布局时自动捕捉 |
| **两点布置** | 1. 需指定"线性变量"（如长、高）<br>2. 变化轴必须对齐 X 轴；Y/Z轴排布需在 replace() 中预旋转 |

## 标准流程

### Step 1：在 replace() 中定义布置参数
```python
from pyp3d import *

class myPart(Component):
    def __init__(self):
        Component.__init__(self)
        self['长'] = Attr(500, obvious=True)      # 线性变量（两点布置时）
        self['宽'] = Attr(200, obvious=True)
        self['高'] = Attr(300, obvious=True)
        self['结果'] = Attr(None, show=True)
        self.replace()
    
    @export
    def replace(self):
        L, W, H = self['长'], self['宽'], self['高']
        # 生成几何并赋值
        body = scale(L,W,H) * Cube()
        self['结果'] = body
```

### Step 2：实例化并调用布置函数
```python
# 创建组件实例
g = myPart()

# --- 旋转布置（需交互选择原点）---
# RotationPlace.RotationFunction(g)
# place(g)  # 显示结果

# --- 两点布置（直接传入线性变量名）---
TwoPointPlace.linearize(g, '长')   # '长'是线性变化维度
place(g)
```

## 接口用例

### 用例 1：旋转布置示例
```python
from pyp3d import *

class Cylinder(Component):
    def __init__(self):
        Component.__init__(self)
        self['直径'] = Attr(200, obvious=True)
        self['高'] = Attr(500, obvious=True)
        self['布置体'] = Attr(None, show=True)
        self.replace()
    
    @export
    def replace(self):
        D, H = self['直径'], self['高']
        cylinder = Cylinder(D/2, H)  # pyp3d 圆柱体 API
        self['布置体'] = cylinder

# 使用：旋转布置，绕原点旋转放置
FinalGeometry = Cylinder()
RotationPlace.RotationFunction(FinalGeometry)
place(FinalGeometry)
```

### 用例 2：两点线性布置（管廊）
```python
from pyp3d import *

class Pipe(Component):
    def __init__(self):
        Component.__init__(self)
        self['长度'] = Attr(10, obvious=True)   # 线性变量
        self['高'] = Attr(2.5, obvious=True)
        self['管体'] = Attr(None, show=True)
        self.replace()
    
    @export
    def replace(self):
        L, H = self['长度'], self['高']
        pipe = scale(L, 10, H) * Box()      # 固定宽 10，沿长和高变化
        self['管体'] = pipe

# 使用：两点布置，沿"长度"维度均匀排布
PipeInstance = Pipe()
TwoPointPlace.linearize(PipeInstance, '长度')
place(PipeInstance)
```

## 注意事项

| 约束项 | 说明 |
|--------|------|
| **函数调用** | `RotationFunction`、`linearize` 均在模块顶层调用，无需导入额外对象 |
| **线性变量选择** | 两点布置时选"长"或"高"；若模型本身为"宽"线性变化，需交换尺寸定义使 X 轴对齐 |
| **Y/Z 轴排布** | 需在 replace() 中预旋转：`rotation(math.pi/2) * translate(0,y,0)` |

## 性能提示

- RotationPlace/TwoPointPlace 均为内部布置工具，不产生额外几何运算<br>- 两点布置的线性变量名称必须与 Attr 参数名完全一致（区分大小写）