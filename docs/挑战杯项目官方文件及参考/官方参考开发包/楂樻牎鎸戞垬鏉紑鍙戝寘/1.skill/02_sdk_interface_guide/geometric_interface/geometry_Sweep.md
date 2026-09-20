---
name: Sweep
description: 创建扫掠几何体，通过截面沿轨迹路径扫掠形成实体
---
## 防退化警告（必读）

- 用Section进行Sweep时：必须使用空间变换函数（如 rotate、translate 等）旋转Section截面使其法线对齐轨迹方向，否则会退化为平面。


## 功能说明

Sweep 函数用于创建扫掠几何体，通过将一个截面沿轨迹路径扫掠形成完整的实体。需要装载截面和截面路径（扫掠轨迹）两个参数。

**接口形式：**

```python
Sweep(section, path)
```

**参数要求：**
- **截面：** 可装填点 (Vec3)、线 (Line) 和弧 (Arc)
- **轨迹路径：** 可装填线 (Line) 和弧 (Arc)

## 接口用例

**示例 1：基本扫掠**

```python
# 描述截面
testsection = Section(Vec3(100,-100,0), scale(100) * Arc(0.5*pi), Vec3(-100,100,0), Vec3(-100,-100,0))
# 描述轨迹
testline = Line(Vec3(0,0,0), Vec3(500,500,500))
# 扫掠
testsweep = Sweep(testsection, testline)
```

**示例 2：带孔洞截面的扫掠**

```python
r = 90
sectionOut = translation(200,0,0) * rotate(Vec3(1,0,0), 0.5*pi) * Section(Vec2(0,0), Vec2(100,0), Vec2(100,100), Vec2(0,100))
section_1 = translation(200,0,0) * rotate(Vec3(1,0,0), 0.5*pi) * Section(Vec2(80,80), Vec2(60,80), Vec2(60,60), Vec2(80,60))
section_2 = translation(200,0,0) * rotate(Vec3(1,0,0), 0.5*pi) * Section(Vec2(50,50), Vec2(20,50), Vec2(20,20), Vec2(50,20))
line = Line(Arc(r*pi/180))
sweep = Sweep(sectionOut - section_1 - section_2, line)
```

## 注意事项

- **轨迹限制：** Sweep 中装填的 Line 只能为一段圆弧和一个两点组成的直线段
- **禁止多段线：** 不能装填多段线，不能装填线、弧结合的 Line
- **Arc 的含义：** 装填 Arc 时，仅表示截面的旋转角度，不表示截面运动的弧线轨迹
- **位置处理：** 由于 Arc 仅表示旋转角度，请先将截面根据半径移动后，再进行 Sweep 操作
