# CADBoard - CAD画板功能说明

## 功能概述

CAD画板是 CADBoard 模块的核心功能之一，提供类似简化版 CAD 的 2D/3D 绘图与编辑能力，并支持与 BIMBase 的双向同步。

## 入口

- 插件按钮：**CAD画板** → `main.py` → `board.py` 的 `CADBoardWindow`
- 插件配置：`CADBoard.pyplugin`

## 支持的绘图命令

### 基本图形

| 命令 | 文件 | 说明 |
|---|---|---|
| 直线 | `commands/line_command.py` | 两点绘制直线 |
| 圆 | `commands/circle_command.py` | 圆心半径或两点画圆 |
| 圆弧 | `commands/arc_command.py` | 三点或圆心角画弧 |
| 矩形 | `commands/rectangle_command.py` | 两点绘制矩形 |
| 多段线 | `commands/polyline_command.py` | 连续线段组成的折线 |
| 多边形 | `commands/polygon_command.py` | 正多边形 |
| 椭圆 | `commands/ellipse_command.py` | 中心、长轴、短轴 |
| 点 | `commands/point_command.py` | 单点绘制 |
| 样条曲线 | `commands/spline_command.py` | B 样条曲线 |

### 编辑命令

| 命令 | 文件 | 说明 |
|---|---|---|
| 删除 | `commands/delete_command.py` | 删除选中图元 |
| 打断 | `commands/divide_command.py` | 在某点打断图元 |
| 修改编辑 | `commands/modify_edit.py` | 拉伸、修剪、延伸 |
| 修改变换 | `commands/modify_transform.py` | 移动、旋转、缩放、镜像 |
| 修改高级 | `commands/modify_advanced.py` | 阵列、偏移、倒角 |

### 3D 实体

| 命令 | 文件 | 说明 |
|---|---|---|
| 拉伸 | `commands/solid_commands.py` | 2D 面拉伸成实体 |
| 立方体 | `commands/solid_commands.py` | 参数化立方体 |
| 球体 | `commands/solid_commands.py` | 参数化球体 |
| 圆锥 | `commands/solid_commands.py` | 参数化圆锥 |
| 圆环 | `commands/solid_commands.py` | 参数化圆环 |
| 棱锥 | `commands/solid_commands.py` | 参数化棱锥 |
| 三棱柱 | `commands/solid_commands.py` | 参数化三棱柱 |

## 导入导出

- **DWG/DXF 导入导出**：`utils/dwg_handler.py`
- **PDF 矢量导入**：`utils/pdf_handler.py`
- **PDF 视图自动关联**：`utils/pdf_view_recognizer.py`

## 辅助功能

- **对象捕捉**：`utils/snap.py`
- **坐标系转换**：`utils/coord.py`
- **图层管理**：`utils/layer_manager.py`
- **组件注册表**：`utils/component_registry.py`
- **BIMBase 同步**：`bimbase_sync.py`、`utils/bimbase_sync.py`

## 使用流程

1. 启动 CAD画板。
2. 在画布中选择绘图命令。
3. 通过鼠标或坐标输入绘制图元。
4. 使用编辑命令修改图元。
5. 可将绘制结果同步到 BIMBase 场景。

## 依赖

- PyQt5/PyQt6
- pyp3d
- ezdxf（DWG/DXF 处理）
- PyMuPDF（PDF 处理）
