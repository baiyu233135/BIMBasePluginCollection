---
name: Sphere
description: 创建单位球体或指定半径的球体
---


## 功能说明

创建单位球体，支持等比例缩放。由于球体只能三轴同时放大，因此不支持三轴不等长放大（椭球）。

**接口形式：**

```python
Sphere()
scale(radius) * Sphere()
scale(x, x, x) * Sphere()  # x = y = z
```

## 接口用例

**创建单位球体：**

```python
sphere = Sphere()
```

**等比例缩放：**

```python
# 方式一：单参数缩放
testsphere = scale(200) * Sphere()

# 方式二：三轴同时放大（必须相等）
testsphere = scale(200, 200, 200) * Sphere()
```

## 注意事项

- **等比例限制：** 球只能三轴同时放大，不支持三轴不等长放大
- **缩放一致性：** 使用 `scale(x, y, z)` 时，x、y、z 必须相等
- **两种形式：** 可以使用单参数 `scale(r)` 或三参数 `scale(x,x,x)` 两种形式
- **非椭球：** 此实现不支持创建椭球体
