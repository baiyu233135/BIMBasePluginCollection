---
name: Box
description: 创建任意朝向的四棱台（含长方体、棱柱等特例）
---

## 功能说明

创建由底面与顶面原点、局部坐标基矢、上下底尺寸共同定义的四棱台实体。  
当 `baseX == topX` 且 `baseY == topY` 时，可得到等截面的棱柱/长方体特例。

**函数：**

```python
Box(baseOrigin, topOrigin, vectorX, vectorY, baseX, baseY, topX, topY)
```

## 参数说明

- `baseOrigin`：底部原点（`Vec3`）
- `topOrigin`：顶部原点（`Vec3`）
- `vectorX`：局部坐标系 X 方向基矢（`Vec3`）
- `vectorY`：局部坐标系 Y 方向基矢（`Vec3`）
- `baseX`：局部坐标系下底部 X 方向长度（`float`）
- `baseY`：局部坐标系下底部 Y 方向长度（`float`）
- `topX`：局部坐标系下顶部 X 方向长度（`float`）
- `topY`：局部坐标系下顶部 Y 方向长度（`float`）
- `color`：颜色与透明度建议通过链式调用设置：`.color(r, g, b, a)`

## 接口用例

```python
Textbox = Box(
    Vec3(0,0,0),
    Vec3(0,0,3000),
    Vec3(1,0,0),
    Vec3(0,1,0),
    3000, 5000,
    3000, 5000
).color(1,1,0,0.5)
```

## 含义说明

以上示例创建了一个局部坐标系对齐全局 XY 平面的四棱台特例（等截面长方体）：

- 底面原点为 `(0, 0, 0)`，顶面原点为 `(0, 0, 3000)`
- 局部基准平面由 `vectorX=(1,0,0)` 与 `vectorY=(0,1,0)` 定义
- 底面尺寸为 `3000mm x 5000mm`，顶面尺寸为 `3000mm x 5000mm`
- 高度由 `topOrigin - baseOrigin` 的轴向差确定，本例为 `3000mm`

## 注意事项

- **基矢要求：** `vectorX` 与 `vectorY` 应保持线性无关，避免退化几何
- **尺寸约束：** `baseX/baseY/topX/topY` 建议为正值，零或负值可能导致异常
- **特例判定：** 顶底尺寸相同得到棱柱特例；顶底尺寸不同得到标准四棱台
- **单位一致：** 坐标与尺寸建议统一使用毫米（mm）
