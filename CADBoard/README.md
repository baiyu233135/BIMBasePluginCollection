# CADBoard - CAD 画板与智能建模平台

本模块是功能最复杂的插件集合，集成 **CAD 画板、AI 智能建模、桥隧病害识别、自动配置环境** 四大方向。

## 四大功能方向

### 1. CAD 画板

2D/3D 绘图与编辑工具，类似简化版 CAD。

- 绘图：直线、圆、圆弧、矩形、多段线、多边形、椭圆、点、样条曲线
- 编辑：删除、打断、移动、旋转、缩放、镜像、阵列
- 3D 实体：拉伸、立方体、球体、圆锥、圆环、棱锥、三棱柱
- 导入导出：DWG、DXF、PDF

入口：`main.py` → `board.py` → `CADBoardWindow`

### 2. AI 智能建模

在 CAD 画板内嵌 AI 助手面板，或将自然语言指令转发到 `AI_Modeling` 执行。

入口：`ai_modeling_launcher.py`

### 3. 桥隧病害识别

基于 YOLOv8 检测无人机照片中的桥梁/隧道病害，生成 Word 诊断报告，并将病害投影到 BIMBase 模型。

入口：`bridge_disease_launcher.py` → `dialogs/disease_dialog.py`

### 4. 自动配置环境

一键检测并配置 VSCode、Python、pyp3d、依赖包、ODA 转换器。

入口：`setup_env.py` → `utils/env_config.py`

## 目录结构

```
CADBoard/
├── commands/             # 绘图与编辑命令
├── dialogs/              # 对话框
├── geometry/             # 2D/3D 几何元素
├── models/               # AI 模型权重
├── training/             # 模型训练脚本
├── utils/                # 工具模块
├── datasets/             # 数据集
├── Picture/              # 图标资源
├── main.py               # CAD画板入口
├── setup_env.py          # 自动配置环境入口
├── ai_modeling_launcher.py # AI智能建模入口
├── bridge_disease_launcher.py # 桥隧病害识别入口
└── docs/                 # 模块文档
```

## 文档

- [CAD画板功能说明](docs/CAD画板功能说明.md)
- [AI智能建模说明](docs/AI智能建模说明.md)
- [桥隧病害识别说明](docs/桥隧病害识别说明.md)
- [自动配置环境说明](docs/自动配置环境说明.md)
- [测试文档](docs/测试文档.md)
- [报错处理记录](docs/报错处理记录.md)
