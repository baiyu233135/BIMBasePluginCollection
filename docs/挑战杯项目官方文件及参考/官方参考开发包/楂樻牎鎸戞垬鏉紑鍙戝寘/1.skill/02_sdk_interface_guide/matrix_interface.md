---
name: TransformFunctions
description: 几何体变换函数（平移、旋转、缩放）
---


## 功能说明

提供三种基本变换函数：平移 (translate)、旋转 (rotate) 和缩放 (scale)，所有变换必须作用于几何体上，使用乘号 (*) 连接。

### 5.1 平移 (translate)

**接口形式：**

```python
# 形式 1：空间矢量 Vec3
testcube = translate(Vec3(100, 100, 100)) * Cube()

# 形式 2：三维空间数值
testcube = translate(100, 100, 100) * Cube()

# 形式 3：二维空间数值（仅在 XY 平面平移）
testcube = translate(100, 100) * Cube()
```

**简易写法：**

```python
testcube = trans(100, 100, 100) * Cube()
```

### 5.2 旋转 (rotate)

**接口形式：**

```python
# 形式 1：空间矢量 + 角度（弧度制）
rotatecube = rotate(Vec3(0, 0, 1), pi/2) * Cube()

# 形式 2：仅角度（默认绕 Z 轴正方向旋转）
rotatecube = rotate(pi/2) * Cube()
```

**绕轴旋转函数：**

```python
# 绕 X 轴旋转
rotatecube = rotx(pi/2) * Cube()

# 绕 Y 轴旋转
rotatecube = roty(pi/2) * Cube()

# 绕 Z 轴旋转
rotatecube = rotz(pi/2) * Cube()
```

**右手定则：**
- 右手四指握拳，大拇指伸出（"点赞"姿势）
- 大拇指指向为旋转轴指向
- 四指握拳方向为旋转正方向
- 例如：旋转轴为 (0,0,1) 时，正方向为逆时针

### 5.3 缩放 (scale)

**接口形式：**

```python
# 形式 1：整体缩放（一个参数）
testArc = scale(100) * Arc(pi*1.5).color(1, 0, 0, 1)

# 形式 2：平面缩放（两个参数，适用于二维几何体）
testArc = scale(100, 50) * Arc(pi*1.5).color(1, 0, 0, 1)

# 形式 3：三轴缩放（三个参数）
testcube = scale(500, 200, 400) * Cube()
```

**使用规则：**
- `scale` 和被作用的几何体用乘号 (*) 相连
- 乘号表示"作用于"

## 接口用例

**组合变换：**

```python
# 平移 + 缩放 + 旋转
testcube = translate(100, 100, 100) * scale(500, 200, 400) * Cube()
rotatecube = rotate(Vec3(0, 0, 1), pi/2) * scale(500, 200, 400) * Cube()
```

## 注意事项

- **作用顺序：** 变换按从右到左的顺序执行，`translate * scale * Cube()` 先缩放再平移
- **必须作用于几何体：** 所有变换函数必须通过乘号连接到具体的几何体上
- **弧度制：** 旋转角度使用弧度制，非角度制
- **右手坐标系：** 遵循右手定则确定旋转正方向
