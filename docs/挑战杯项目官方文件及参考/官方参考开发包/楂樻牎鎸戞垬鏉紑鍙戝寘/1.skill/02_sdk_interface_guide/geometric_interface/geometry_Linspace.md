---
name: Linspace
description: 生成等分点序列
---


## 功能说明

生成从起点到终点的等分点序列，支持空间矢量形式和数值形式两种用法。

**接口形式：**

```python
linspace(a, b, n)
```

**参数说明：**
- `a`, `b`: 起点和终点（可以是空间矢量或数值）
- `n`: 分成 n-1 份，生成 n 个点（含起点和终点）

## 接口用例

**空间矢量形式：**

```python
# 生成 10 个等分点
for i in linspace(Vec3(0,0,0), Vec3(1000,0,0), 10):
    Test_Array.append(translate(i))
```

**数值形式（圆弧角度）：**

```python
R = 100
# 生成 12 个等分角度值
for i in linspace(0, pi*2*11/12, 12):
    Test_Array.append(translate(Vec3(R*cos(i), R*sin(i), 0)))
```

## 注意事项

- **点数计算：** 分成 n-1 份，实际生成 n 个点（包含起点和终点）
- **类型兼容：** a 和 b 可以是空间矢量 (Vec2/Vec3) 或数值类型
- **矢量形式：** 适用于空间路径的点采样
- **数值形式：** 常用于圆弧角度的等分生成
