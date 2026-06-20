# 桥梁组件 - STL工具说明

## 功能概述

STL 工具用于在 BIMBase 与外部 3D 打印/渲染软件之间交换模型数据，支持 FBX 导出、STL 导入导出、FBX 转 STL 等功能。

## 入口

由 `桥梁组件.pyplugin` 注册：

- **导入Stl** → `桥梁组件/桥梁组件/Stl插件/导入Stl.py`
- **导出FBX** → `桥梁组件/桥梁组件/Stl插件/仅导出stl.py`
- **导出FBX并打开切片** → `桥梁组件/桥梁组件/Stl插件/导出stl.py`
- **FBX转STL工具** → `桥梁组件/桥梁组件/Stl插件/test_button.py`

## 主要文件

| 文件 | 功能 |
|---|---|
| `Stl插件/导入Stl.py` | 导入 STL 文件到 BIMBase |
| `Stl插件/仅导出stl.py` | 导出当前场景为 FBX |
| `Stl插件/导出stl.py` | 导出 FBX 并打开切片软件 |
| `Stl插件/FBX转STL工具.py` | 将 FBX 文件转换为 STL |
| `Stl插件/test_button.py` | FBX 转 STL 工具入口 |

## 使用流程

### 导出 FBX

1. 在 BIMBase 中准备好模型。
2. 点击“导出FBX”按钮。
3. 选择保存路径，生成 `.fbx` 文件。

### FBX 转 STL

1. 点击“FBX转STL工具”。
2. 选择要转换的 `.fbx` 文件。
3. 生成 `.stl` 文件。

### 导入 STL

1. 点击“导入Stl”。
2. 选择 `.stl` 文件。
3. 模型导入到 BIMBase 场景。

### 导出并切片

1. 点击“导出FBX并打开切片”。
2. 导出 FBX 后自动打开 OrcaSlicer。
3. 在 OrcaSlicer 中设置切片参数。

## 依赖

- pyp3d
- PyQt5/PyQt6
- OrcaSlicer（3D 打印切片，需单独安装）

## 注意事项

- FBX 转 STL 过程中可能丢失材质信息。
- 大型模型导出时可能需要较长时间。
- 确保 OrcaSlicer 路径配置正确。
