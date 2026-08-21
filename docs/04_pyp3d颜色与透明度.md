# 04 - pyp3d 组件颜色与透明度

> 适用环境：BIMBase 2025，Plugin SDK 1.6.2，pyp3d v18446497937724801024（2024.10 Release）
> 源码依据：`pyp3d/v18446497937724801024/pyp3d_component.py`（`Primitives.color`、`Combine.color`、`Symbology`）

## 一、基本用法

每个几何图元（`Cube` / `Cone` / `Loft` / `Sweep` / `Combine` 等 `Primitives` 子类）都有 `.color()` 方法，**返回自身，可链式调用**：

```python
self['正方体'] = scale(a, a, a) * Cube().color(0, 0.6, 0)   # 绿色
```

### 颜色值是 0~1 浮点数（不是 0~255）

| 想要的颜色 | 写法 |
|---|---|
| 红 | `.color(1, 0, 0)` |
| 绿 | `.color(0, 1, 0)` |
| 蓝 | `.color(0, 0, 1)` |
| 灰 | `.color(0.5, 0.5, 0.5)` |
| 任意 RGB | 0~255 除以 255 换算，如 RGB(30,144,255) → `.color(0.12, 0.56, 1)` |

### 支持的调用形式（源码 `Primitives.color`）

```python
.color()                    # 无参 → 默认灰色
.color(0.5, 0.5, 0.5)       # RGB 三个数
.color(r, g, b, a)          # RGBA 四个数（a = 透明度）
.color((r, g, b))           # 三元组
.color((r, g, b, a))        # 四元组
.color((r, g, b), a)        # 元组 + 透明度
```

### 快捷颜色方法

```python
.colorRed(A=1)   .colorGreen(A=1)  .colorBlue(A=1)   .colorYellow(A=1)
.colorMagenta(A=1) .colorCyan(A=1) .colorPurple(A=1) .colorOrange(A=1)
.colorBlack(A=1) .colorWhite(A=1)  .colorGray(A=1)
.colorRand(A=1, isOutput=True)     # 随机颜色，isOutput=True 时打印当前 RGB（调试好用）
```

`A` 就是透明度，省略默认 1（不透明）。

## 二、透明度

第 4 个参数（alpha）即透明度，0~1：

```python
.color(1, 0, 0, 1)     # 不透明
.color(1, 0, 0, 0.5)   # 半透明
.color(1, 0, 0, 0.1)   # 几乎全透明
```

> ⚠️ alpha 通道在 SDK 数据结构（`P3DColorDef`）中确实存在并传给内核，但 BIMBase 视图对半透明体的渲染效果（排序、遮挡关系）建议在软件里先小范围验证再大面积使用。

## 三、部分上色（一个组件多种颜色）

**核心规则：先上色，后 Combine。Combine 会保留每个零件各自的颜色。**

```python
# 立柱深灰
pillar_colored = Combine(pillar_first, pillar_last, pillar_line).color(0.2, 0.2, 0.2)
# 网片绿色
frame_colored = frame_all.color(0, 0.6, 0)
# 合并后各保各的颜色
self['铁路封闭网'] = Combine(frame_colored, pillar_colored)
```

### ⚠️ 常见坑：对最终 Combine 再调 .color() 会覆盖所有零件颜色

`Combine.color()` 的实现（`pyp3d_component.py:1243`）是**递归遍历所有 parts 逐个改色**，所以：

```python
Combine(红零件, 绿零件).color(0, 0, 1)   # 结果全蓝！前面的分色被覆盖
```

如果需要"大部分一个色、个别零件另一个色"，可以分组合并，或先整体上色再对个别零件重新上色（后调用的生效，因为颜色存在零件自己的 Style 上）。

## 四、原理简述

- 每个 `Primitives` 持有一个 `Style`（默认是 `Symbology`），颜色存在 `Symbology.color`（`P3DColorDef(r, g, b, a)`）上
- `Symbology` 还控制线宽（`weight`）和线型（`style` 0~7：实线/点线/各类虚线/点画线），主要对线类图元有效
- 另有 `.material(name)` 设置材质名（`Material` 样式），供渲染/导出场景使用

## 五、速查示例

```python
# 红色不透明立方体
scale(100, 100, 100) * Cube().colorRed()

# 半透明蓝色圆柱（Cone 起点/终点/半径）
Cone(Vec3(0, 0, 0), Vec3(0, 0, 800), 100, 100).color(0, 0, 1, 0.5)

# 分色组合：底座灰、立柱绿
base = scale(500, 500, 100) * Cube().colorGray()
pole = Cone(Vec3(250, 250, 0), Vec3(250, 250, 800), 40, 40).colorGreen()
self['组件'] = Combine(base, pole)
```
