# BIMBase Python 插件集合

本项目是基于 **BIMBase Python SDK** 开发的一系列插件，用于参数化建模、CAD 绘图、AI 智能建模、桥梁病害识别等工程场景。

## 📁 项目结构

```
pythonplugin/
├── AI_Modeling/          # 新版 AI 智能建模（DeepSeek + 本地解析 + 自动放置）
├── AI建模/               # 早期 AI 建模入口（ChatGLM 网页 + 剪贴板代码运行）
├── CADBoard/             # CAD 画板 / AI 智能建模 / 自动配置环境
│   └── bridge_disease_launcher.py  # 桥梁病害识别转发入口
├── 桥隧病害识别/         # 桥梁病害识别独立模块（由 CADBoard 按钮调用）
├── 建模/                 # 曲线建模 + 圆柱批量建模（读取 Excel 参数）
├── 桥梁组件/             # 桥梁参数化组件库 + 清单工具 + STL/Lumion/3D打印
├── 组件测试/             # 基础几何体测试组件
├── archive/              # 临时调试脚本归档
├── docs/                 # 项目级文档
└── *.pyplugin            # BIMBase 插件清单文件（保留在根目录）
```

## 🔌 插件清单

| 插件文件 | 名称 | 功能 | 入口目录 |
|---|---|---|---|
| `AI建模.pyplugin` | AI建模（大语言模型） | 登录大模型账号，对话生成建模代码 | `AI建模/` |
| （已并入 CADBoard） | AI_Modeling | 本地 AI 智能建模，能力已并入 CADBoard 画板 AI 面板 | `AI_Modeling/` |
| `CADBoard.pyplugin` | CADBoard | CAD 画板、AI 智能建模、桥梁病害识别、自动配置环境 | `CADBoard/` |
| `建模.pyplugin` | 建模插件库 | 曲线建模、圆柱批量建模 | `建模/` |
| `桥梁组件.pyplugin` | 桥梁组件库 | 桥梁参数化结构、清单工具、STL 工具 | `桥梁组件/` |
| `组件测试.pyplugin` | 组件测试 | 基础几何体与组合梁测试 | `组件测试/` |

> 注意：`.pyplugin` 文件必须保留在根目录，BIMBase 才能正确加载插件。

### 桥梁病害识别入口说明

桥梁病害识别功能已独立到 `桥隧病害识别/` 目录，不单独注册 `.pyplugin`：

```text
CADBoard 面板 → 桥梁病害识别 → CADBoard/bridge_disease_launcher.py（转发）
    → 桥隧病害识别/bridge_disease_launcher.py → disease_dialog.py
```

## 🚀 快速开始

1. 安装 BIMBase 软件，并确保版本为 **V1.6.x**。
2. 安装 VSCode，配置 Python 解释器指向 BIMBase 内置 Python（或系统 Python）。
3. 将本项目目录配置为 BIMBase 插件加载路径，或直接把 `.pyplugin` 文件放入 BIMBase 插件目录。
4. 启动 BIMBase，在插件面板中点击对应按钮即可使用。

详细环境配置请参考 [docs/03_环境搭建与安装.md](docs/03_环境搭建与安装.md)。

## 📚 文档索引

- [项目总览](docs/01_项目总览.md)
- [插件清单与入口](docs/02_插件清单与入口.md)
- [环境搭建与安装](docs/03_环境搭建与安装.md)
- [pyp3d 组件颜色与透明度](docs/04_pyp3d颜色与透明度.md)
- [pyp3d 交互放置工具与放置坐标回写](docs/05_pyp3d交互放置工具与坐标回写.md)
- [常见问题与调试](docs/99_常见问题与调试.md)

各模块详细文档请进入对应目录查看 `README.md` 和 `docs/`。

## ⚠️ 说明

- 根目录下的 `.pdf` 文件为外部学习资料与测试素材。
- `archive/` 目录存放开发过程中的临时调试脚本，不属于正式功能。
- 部分插件依赖外部 API（如 DeepSeek、百度语音、ChatGLM），使用前需配置 API Key。
