---
name: BooleanOperations
description: 执行几何体的布尔减、交运算
---


## 功能说明

执行几何体的布尔运算，包括：

- **布尔减 (Subtract)**：从一个几何体中切除与另一个几何体重叠的部分
- **布尔交 (Intersect)**：提取两个几何体相交的公共部分

**接口形式：**

```python
# 布尔减：从 testa 中减去 testb
testFusion = testa - testb

# 布尔交：提取 testa 和 testb 的交集
testFusion = Intersect(testa, testb)
```

## 接口用例

**布尔减运算：**

```python
# 从 geometryA 中切除 geometryB
result = geometryA - geometryB
```

**布尔交运算：**

```python
# 获取两个几何体的交集部分
result = Intersect(geometryA, geometryB)
```

## 注意事项

- **操作符重载：** 支持使用减号 (-) 直接进行差集运算，语法简洁
- **颜色重置：** 布尔运算执行后，原有几何体的颜色信息会被抹除，运算结果需要重新设置颜色
