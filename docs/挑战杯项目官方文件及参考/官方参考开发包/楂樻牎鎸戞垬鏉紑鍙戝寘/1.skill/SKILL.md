---
name: BIMBaseModel
description: BIMBase Python 建模知识库 — 编码规范、SDK接口、专业模式、自定义组件
---
# BIMBase 建模知识库

**任务边界**: pyp3d API 参考文档。每个文档描述一个或一组 SDK 函数的签名、参数、约束和使用示例。使用任何 SDK 前必须加载对应文档。

#### 几何体接口（geometric_interface/）

| SDK      | 路径                                                                | 功能                |
| -------- | ------------------------------------------------------------------- | ------------------- |
| Arc      | `02_sdk_interface_guide/geometric_interface/geometry_Arc.md`      | 单位圆弧 / 三点圆弧 |
| Bool     | `02_sdk_interface_guide/geometric_interface/geometry_Bool.md`     | 布尔减、交运算      |
| Box      | `02_sdk_interface_guide/geometric_interface/geometry_Box.md`      | 任意朝向四棱台      |
| Color    | `02_sdk_interface_guide/geometric_interface/geometry_Color.md`    | RGBA 颜色和透明度   |
| Combine  | `02_sdk_interface_guide/geometric_interface/geometry_Combine.md`  | 多几何体组合        |
| Cone     | `02_sdk_interface_guide/geometric_interface/geometry_Cone.md`     | 圆锥/圆台/圆柱      |
| Cube     | `02_sdk_interface_guide/geometric_interface/geometry_Cube.md`     | 单位立方体          |
| Line     | `02_sdk_interface_guide/geometric_interface/geometry_Line.md`     | 二维/三维线段       |
| Linspace | `02_sdk_interface_guide/geometric_interface/geometry_Linspace.md` | 等分点序列          |
| Loft     | `02_sdk_interface_guide/geometric_interface/geometry_Loft.md`     | 放样几何体          |
| Section  | `02_sdk_interface_guide/geometric_interface/geometry_Section.md`  | 放样截面装填        |
| Sphere   | `02_sdk_interface_guide/geometric_interface/geometry_Sphere.md`   | 单位球体            |
| Sweep    | `02_sdk_interface_guide/geometric_interface/geometry_Sweep.md`    | 扫掠几何体          |
|          |                                                                     |                     |

#### 变换与布置（顶层）

| SDK    | 路径                                           | 功能                 |
| ------ | ---------------------------------------------- | -------------------- |
| Matrix | `02_sdk_interface_guide/matrix_interface.md` | 平移、旋转、缩放变换 |
| Place  | `02_sdk_interface_guide/place_interface.md`  | 旋转/两点线性布置    |
