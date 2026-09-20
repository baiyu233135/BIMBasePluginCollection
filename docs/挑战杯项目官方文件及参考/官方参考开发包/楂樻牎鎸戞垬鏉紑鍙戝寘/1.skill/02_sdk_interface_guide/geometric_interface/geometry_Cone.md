---
name: Cone
description: 创建圆锥、圆台或圆柱体（当两端半径相等时）
---

## 功能说明

创建圆锥/圆台几何体；当 `radiusA == radiusB` 时，生成圆柱体。圆锥台的轴线方向由 `centerA` 与 `centerB` 两点共同确定，可用于任意空间方向建模。

**函数：**

```python
Cone(centerA, centerB, radiusA, radiusB)
```

**参数说明：**

- `centerA`：底面 A 的圆心坐标（`Vec3`）
- `centerB`：底面 B 的圆心坐标（`Vec3`）
- `radiusA`：底面 A 的半径（`float`）
- `radiusB`：底面 B 的半径（`float`）

## 接口用例

**创建圆柱体（两端半径相同）：**

```python
Testcone = Cone(Vec3(10000,0,0), Vec3(10000,0,2000), 1000, 1000).color(1,0,0,0.3)
```

## 含义说明

以上示例创建了一个轴线平行 Z 轴的圆柱体：

- 变量名为 `Testcone`
- 底面 A 圆心为 `(10000, 0, 0)`
- 底面 B 圆心为 `(10000, 0, 2000)`
- `radiusA = 1000`、`radiusB = 1000`，因此几何体为圆柱
- 高度由两圆心在 Z 方向的差值确定，为 `2000mm`

## 注意事项

- **圆柱判定：** `radiusA` 与 `radiusB` 相等时为圆柱，不相等时为圆锥/圆台
- **轴线方向：** 圆锥台轴线不限制在 Z 轴方向，可由任意 `centerA -> centerB` 方向定义
- **单位一致：** 建议坐标与半径统一使用毫米（mm）
