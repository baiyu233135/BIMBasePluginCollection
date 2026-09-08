# 速构智维 —— BIMBase Python 插件集合

本项目是基于 **BIMBase Python SDK（pyp3d）1.6.x** 开发的土木工程数字化插件集合，围绕 **「速构智维」** 主插件，实现三大能力：

1. **CAD 画板 + AI 智能建模**：内嵌于 BIMBase 的 2D/3D 画板，支持自然语言（打字或语音）驱动参数化建模；
2. **桥梁病害识别**：无人机照片 → AI 圈出病害 → 投影到 BIM 三维构件 → 自动生成 Word 诊断报告；
3. **参数化组件库**：按真实工程图纸（PDF/DWG）参数化的桥梁构件组件。

> 用一句话说：让工程师「说句话就建模，拍张照就巡检」。

## 📁 项目结构

```
pythonplugin/
├── 速构智维/             # 主插件「速构智维」：CAD 画板 + AI 面板 + 自动配置环境（核心）
├── AI_Modeling/          # AI 智能建模引擎：本地中文解析 + DeepSeek 双路驱动（已并入 速构智维 AI 面板）
├── 桥梁病害识别/          # YOLOv8/OpenCV 病害检测 + Qwen-VL 诊断 + BIM 投影 + Word 报告
├── 组件测试/              # 参数化几何组件试验场（基础几何体 + 按图纸参数化的桥梁构件）
├── 组件成品/              # 成品组件（铁路封闭网×3版/被插板/凸插板/隧道，两点布置）
├── 体育馆组件库/           # 体育馆参数化组件库（19 个构件，4 面板分组）
├── 数据参考源/            # 原始资料：PDF/DWG 图纸、巡检报告（建模参数与病害数据集来源）
├── docs/                 # 项目级文档（含论文撰写指引）
├── archive/              # 临时调试脚本归档，不属于正式功能
├── 桥梁组件/              # ⚠️ 早期桥梁组件库，不在本项目范围内，仅供参考
├── AI建模/                # ⚠️ 早期 AI 建模（ChatGLM 网页版），不在本项目范围内，仅供参考
└── *.pyplugin            # BIMBase 插件清单文件（必须保留在根目录才能被加载）
```

## 🔌 插件清单

| 插件文件 | 名称 | 版本 | 入口目录 | 说明 |
|---|---|---|---|---|
| `速构智维.pyplugin` | 速构智维 | 1.2.0 | `速构智维/` | CAD 画板、自动配置环境、桥梁病害识别（转发） |
| `组件测试.pyplugin` | 组件测试 | 1.0.1 | `组件测试/` | 8 个参数化组件按钮 |
| `组件成品.pyplugin` | 组件成品 | 1.0.0 | `组件成品/` | 铁路封闭网×3版、被插板、凸插板、隧道 |
| `体育馆组件库.pyplugin` | 体育馆组件库 | 1.0.0 | `体育馆组件库/` | 19 个体育馆构件，4 面板分组 |
| `桥梁组件.pyplugin` | 桥梁组件库 | 1.0.6 | `桥梁组件/` | ⚠️ 范围外，仅供参考 |
| `AI建模.pyplugin` | AI建模（大语言模型） | 1.0.2 | `AI建模/` | ⚠️ 范围外，仅供参考 |

- `AI_Modeling/` 与 `桥梁病害识别/` **不单独注册 `.pyplugin`**：前者能力已并入 速构智维 画板右侧 AI 面板（也可 `python AI_Modeling/main.py` 独立运行）；后者由 速构智维 面板的「桥梁病害识别」按钮转发调用。
- 按钮 → 脚本的完整映射见 [docs/02_插件清单与入口.md](docs/02_插件清单与入口.md)。

## 🛠 核心技术

| 层次 | 技术 | 用在哪 |
|---|---|---|
| BIM 平台 | BIMBase V1.6.x + pyp3d SDK（Python 3.7 内嵌，NamedPipe 进程通信） | 全部模块 |
| 界面 | PyQt5（部分兼容 PyQt6）、QtMultimedia 录音 | 画板、AI 面板、病害对话框 |
| AI 大模型 | DeepSeek（流式对话/建模指令）、扣子 Coze、阿里云 Qwen-VL（图纸识别 + 病害诊断）、百度语音识别 | AI 建模、病害诊断 |
| 计算机视觉 | ultralytics YOLOv8n（病害检测）、OpenCV 多策略异常检测、EfficientNet-B0（构件分类，预留） | 病害识别 |
| 几何/图纸 | ezdxf（DXF 三视图生成）、PyMuPDF（PDF 导入/转图）、ODA File Converter（DWG↔DXF） | 画板、组件测试 |
| 报告/数据 | python-docx（Word 诊断报告）、JSON 配置与注册表持久化 | 病害识别、各模块 |

## 💡 创新点（项目亮点）

1. **「本地解析优先、大模型兜底」的混合式自然语言建模架构**
   中文建模指令先由本地正则解析器毫秒级响应（无网络、零成本、可离线），解析失败才调用 DeepSeek；指令三级路由（2D 画板 / 3D 建模 / 云端对话）自动分发，配合汉字数字转换、单位归一化（cm/m→mm）、三种坐标写法兼容。详见 `AI_Modeling/README.md`。
2. **绕过 SDK 限制的「七级兜底自动放置」策略链**
   pyp3d 的实体创建 API 要求调用方处于合法交互回调链中（模态对话框内全部返回失败）。项目通过「屏幕外隐藏窗口借事件循环 + 七级放置策略回退（官方 create_geometry → 底层 UnifiedFunction → 坐标烘焙 → IFC/OBJ 文件导入 → Win32 模拟点击）」实现了对话框场景下的全自动建模。
3. **病害「检测—诊断—定位—报告」全链路闭环**
   无人机照片经 OpenCV 五路掩码融合（黑帽/自适应阈值/K-Means/纹理/边缘密度）免模型圈出异常区域，Qwen-VL 大模型逐框诊断病害类型与严重程度，再按「照片 bbox → 构件面局部坐标 → 世界坐标」等比映射，以半透明彩色点云投影到 BIM 真实构件表面，最后一键生成 Word 诊断报告。详见 `桥梁病害识别/README.md`。
4. **2D 检测结果向 3D 参数化构件的解析式面投影引擎**
   为每种桥梁构件手写解析面公式（与组件源码原点约定严格对齐），支持条件面（如墩高不足无系梁）、圆柱面展开近似，点云几何烘焙 + 零变换放置避免双重偏移。
5. **CAD 画板 ↔ BIMBase 双向同步与「面编辑反推参数」**
   画板图元与 BIMBase 参数化组件可双向同步；在三视图「面编辑」模式下直接拖动尺寸，系统自动反推组件参数并批量重生成——把「改模型」变成「改图纸」。
6. **放置坐标自动回写**
   攻克 pyp3d replace 在内核 service 进程执行、取点 API 恒返回 (0,0,0) 的限制，从变换矩阵 `_mat` 提取放置平移写入组件参数，实现成品组件「放在哪，参数就显示哪」（`docs/05_pyp3d交互放置工具与坐标回写.md`）。

## 🚀 快速开始

1. 安装 **BIMBase V1.6.x**（本机位于 D 盘），将本目录配置为插件加载路径（`.pyplugin` 必须保留在根目录）。
2. 启动 BIMBase →「速构智维」面板 →「自动配置环境」，一键检测/配置 VSCode、Python、pyp3d、pip 依赖、ODA 转换器。详见 [docs/03_环境搭建与安装.md](docs/03_环境搭建与安装.md)。
3. 按需配置 API Key（均存于对应 JSON 配置文件，面板内也有配置界面）：
   - DeepSeek / Coze / 百度语音 → `速构智维/ai_config.json`、`AI_Modeling/ai_modeling_config.json`
   - 阿里云 Qwen-VL（病害诊断）→ `桥梁病害识别/disease_config.json`
   - 阿里云 DashScope（图纸识别）→ `速构智维/drawing_ai_config.json`
4. 各功能使用说明见对应模块 README（链接在文末「文档索引」）。

> ⚠️ **安全提示**：上述 `*.json` 配置文件中可能存有明文 API Key，且部分已被 git 跟踪。对外分享或公开发布仓库前，请务必脱敏或改用环境变量。

## 🧪 测试指引

本项目无 pytest/CI，测试分三类：**离线单元测试**（普通 Python 直接跑）、**BIMBase 内测试**（需在 BIMBase 进程内执行）、**手动回归**。

### 离线单元测试（无需 BIMBase）

| 文件 | 测什么 |
|---|---|
| `速构智维/test_ai_modeling_bridge.py` | AI 指令路由：3D 指令识别、2D/闲聊不误判 |
| `速构智维/test_cached_component_ops.py` | 缓存组件的 AI 操作链路 |
| `AI_Modeling/test_component_registry.py` | 组件注册表持久化 |
| `AI_Modeling/test_pier_parse.py` / `test_new_components_parse.py` | 引桥桥墩/门式桥墩/承台桩基指令解析 |
| `AI_Modeling/test_delete_component.py` | 删除指令链路 |
| `桥梁病害识别/test_pier_projection_mapping.py` | 投影映射纯数学验证（8 组断言） |
| `桥梁病害识别/test_t_beam_workflow.py` | T 梁检测→投影→报告全流程（需 cv2、python-docx） |
| `test_parse_cn.py`（根目录） | 画板中文指令解析器原型 |

运行方式：`python <文件路径>`。

### BIMBase 内测试（需 BIMBase 运行环境）

| 文件 | 测什么 |
|---|---|
| `组件测试/_test_components.py` | 基础 API + 全部组件实例化/放置冒烟 |
| `桥梁病害识别/test_projection.py` / `test_t_beam_projection.py` | 标记组件放置 / T 梁点云投影端到端 |
| `AI_Modeling/test_place_to.py` | place_to/replace_noumenon 底层接口 |
| `速构智维/test_noumenon_replace.py` / `测试.py` | pyp3d 改参 API 行为验证 |
| `速构智维/test_audio.py` | 麦克风/QAudioInput 诊断 |

运行方式：BIMBase 底部 Python 命令行 `exec(open(r'<绝对路径>', encoding='utf-8').read())`，或在 BIMBase Python 控制台运行。

### 手动回归

- `docs/手动测试清单.md` —— 51 项七轮手动回归清单（AI 布置、双向同步、改删、旧实体兼容等）。
- 各模块 `docs/测试文档.md` —— 本模块的手动测试步骤与预期结果。

## 🐞 报错与调试指引

**第一步看日志**（排查问题的最快路径）：

| 日志文件 | 记录内容 |
|---|---|
| `速构智维/CADBoard_error.log` | 画板启动与命令异常 |
| `速构智维/bimbase_sync_debug.log` | 同步 + AI 面板路由（`[AI_PANEL]`/`[AI_BRIDGE]`） |
| `速构智维/ai_modeling_launcher.log` | AI 建模指令代理执行 |
| `速构智维/face_debug.log` | 面生成/面编辑 |
| `速构智维/CADBoard_env_setup.log` | 自动配置环境过程 |
| `AI_Modeling/ai_modeling_debug.log` | AI 建模主日志（registry/factory/parser 共用） |
| `桥梁病害识别/bridge_disease_debug.log` | 病害模块统一日志（`[AI_DIAG]`/`[MARKER]`/`[REPORT]` 等前缀） |
| `速构智维/CADBoard_CRASH.txt`（崩溃时生成） | 画板崩溃堆栈 |

**第二步查报错记录文档**（已知问题与解决办法）：

- `速构智维/docs/报错处理记录.md` —— 15 条（启动闪退、同步失败、模块污染、颜色序列化等）
- `AI_Modeling/docs/报错处理记录.md` —— 5 条（放置失败、DeepSeek 调用、语音识别等）
- `桥梁病害识别/docs/报错处理记录.md` —— 7 条（启动、检测框异常、投影失败、import 错误等）
- `docs/99_常见问题与调试.md` —— 跨模块 FAQ 汇总
- `速构智维/组件调试指南.md` —— pyp3d 只能在 BIMBase 进程内调试的三种方案

**高频坑速查**（详细出处见各报错记录文档）：

- 改代码后必须**完全重启 BIMBase**（embed 环境缓存模块）；
- pyp3d 圆柱是 `Cone(p1,p2,r,r)`，多几何体并用 `Combine()` 不是 `+`；
- pyp3d `Attr` 只能存标量/字符串，颜色必须写 `"r,g,b,a"` 字符串；
- `P3DInstanceKey` 禁止 `str()`/`repr()`（会崩溃并拖垮后续调用）；
- 模态对话框内所有实体创建 API 返回 `ModelId=-2` → 用隐藏窗口借事件循环；
- 几何按世界坐标烘焙后必须**零变换放置**，否则平移应用两次。

## 📚 文档索引

**项目级（docs/）**

- [01 项目总览](docs/01_项目总览.md) / [02 插件清单与入口](docs/02_插件清单与入口.md) / [03 环境搭建与安装](docs/03_环境搭建与安装.md)
- [04 pyp3d 颜色与透明度](docs/04_pyp3d颜色与透明度.md) / [05 pyp3d 交互放置工具与坐标回写](docs/05_pyp3d交互放置工具与坐标回写.md)
- [99 常见问题与调试](docs/99_常见问题与调试.md) / [手动测试清单](docs/手动测试清单.md) / [画板图纸识别技术方案](docs/画板图纸识别技术方案.md)
- [论文撰写指引](docs/论文撰写指引.md) —— 面向 EI 会议/核心期刊投稿的创新点分析与写作路线

**模块级（各目录 README + docs/）**

- [速构智维/README.md](速构智维/README.md) —— 速构智维主插件
- [AI_Modeling/README.md](AI_Modeling/README.md) —— AI 智能建模引擎
- [桥梁病害识别/README.md](桥梁病害识别/README.md) —— 病害识别模块（另见 `桥梁病害识别_使用说明.md`）
- [组件测试/README.md](组件测试/README.md) —— 参数化组件试验场
- [组件成品/README.md](组件成品/README.md) —— 铁路封闭网成品组件

## ⚠️ 说明

- `桥梁组件/`、`AI建模/` 为早期成果，**不在本项目范围内**，仅作参考，相关文档不保证时效。
- `archive/` 存放开发期临时调试脚本；`数据参考源/` 为原始图纸与巡检资料。
- 各模块目录约定：`docs/功能说明.md`（功能与入口）、`docs/测试文档.md`（测试方法）、`docs/报错处理记录.md`（问题与处理）。
