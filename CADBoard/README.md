# CADBoard —— 速构智维主插件

「速构智维」是本项目的主插件（`CADBoard.pyplugin`，v1.2.0，SDK 1.6.2），一个内嵌于 BIMBase 的 **PyQt 简化版 CAD 画板**，右侧集成 **AI 助手面板**，外加 **自动配置环境** 与 **桥隧病害识别（转发入口）** 两个面板按钮。

## 功能总览

| 面板按钮 | 入口 | 功能 |
|---|---|---|
| CAD画板 | `main.py` → `board.py` `CADBoardWindow` | 2D/3D 绘图编辑、DWG/DXF/PDF 导入导出、与 BIMBase 双向同步、三视图面编辑、AI 助手面板 |
| 自动配置环境 | `setup_env.py` → `utils/env_config.py` | 一键检测/配置 BIMBase、VSCode、Python、pyp3d、pip 依赖、ODA 转换器 |
| 桥梁病害识别 | `bridge_disease_launcher.py` | 仅转发：把 `../桥隧病害识别` 加入 sys.path 后调用该模块入口（功能已拆分，见 `桥隧病害识别/README.md`） |

## 关键技术栈

- **界面**：PyQt5 为主、PyQt6 回退（`board.py:27-61` 双导入）；语音用 PyQt5.QtMultimedia
- **BIM 内核**：pyp3d SDK（`Component/Attr/Section/Sweep/UnifiedFunction` 等），仅存在于 BIMBase 进程内（Python 3.7 内嵌）
- **外部 API**：DeepSeek（`deepseek-chat`，流式 SSE，urllib 直连）、扣子 Coze、阿里云 DashScope Qwen-VL（`qwen-vl-max`，图纸识别）、百度语音识别
- **Python 包**：ezdxf、PyMuPDF、python-docx（`utils/env_config.py:27-33` REQUIRED_PACKAGES）
- **外部工具**：ODA File Converter（DWG↔DXF 互转，`env_config.py` 自动下载静默安装）
- **配置持久化**：`ai_config.json`（DeepSeek/Coze/百度 Key）、`drawing_ai_config.json`（DashScope Key）、`sync_config.json`、`component_registry.json`（element_id→参数注册表，逐条容错加载）

## 核心机制（技术说明）

### 1. pyp3d 进程通信修复（PID 写回）

pyp3d 通过 `sys.argv[1]` 找到目标 BIMBase 进程；画板窗口抢到前台后回退查找会连错进程，报 `'NoneType' object has no attribute 'send'`。

> 通俗说：画板一弹出来，BIMBase 就「找不到回家的路」了。

方案：启动时用 `ctypes` Toolhelp32 快照枚举 BIMBase.exe 的 PID 写回 argv（`utils/bimbase_pid.py:57-75`）；`_ensure_pyp3d_port` 每次通信前用一次轻量 `get_version` 调用探活，失败就清掉 `_Core` 单例重建管道（`bimbase_sync.py:129-157`）。

### 2. AI 指令三级路由

AI 面板的每条输入按优先级路由（`utils/ai_panel.py:1363-1581`）：

```
用户输入
  → ① 画板 2D 本地解析器 LocalCommandParser（"画一个半径50的圆"）
  → ② 3D 建模解析器（桥接 AI_Modeling 的 command_parser.py）
       命中 → ai_modeling_launcher 在隐藏窗口上下文中执行 pyp3d 放置
  → ③ DeepSeek/Coze 大模型，返回 JSON，用户确认后由 ai_executor 批量执行
```

> 通俗说：能在本地「听懂」的绝不花钱上云；本地听不懂的，再问大模型。`_prefer_modeling` 负责防止 3D 指令（如"生成一个圆柱"）被 2D 解析器误吞成"画圆"。

本地解析器支持：汉字数字（"五百"→500）、单位换算（cm/m→mm）、三种坐标写法 `(a,b,c)` / `a,b,c` / `a.b.c`。"AI优先"开关适合语音输入场景（识别结果不规范时直接交给大模型）。

### 3. AI_Modeling 代理执行与模块隔离

pyp3d 放置必须在窗口事件循环的交互回调链中执行，且 CADBoard 与 AI_Modeling 曾有同名 `bimbase_sync.py` 导致组件类解析错乱、BIMBase 崩溃。方案（`ai_modeling_launcher.py:109-209`）：

- 新建临时 `AIModelingWindow`，移到屏幕外 `(-32000,-32000)` 隐藏，借它的事件循环执行放置；
- 执行前快照 `sys.path` 和 `sys.modules['bimbase_sync'/'component_registry']`，finally 中恢复，做到「借地方办事，不弄脏环境」；
- 成功判定用放置前后实体计数对比，计数 API 不可用时按无异常判成功。

### 4. 画板 ↔ BIMBase 双向同步

- 正向：画板元素 → 19 个 pyp3d `Component` 子类（`bimbase_sync.py:788-1662`）→ 放置策略链（优先级：官方 `create_geometry + translate` → `_PlaceToDirect` 底层写变换 → `place_to` → 坐标烘焙 → 手动 `place()`），放置后双路校验实体有效性；
- 反向：「从BIMBase更新」读回参数改写画板图元，用框选获取 entityId 避免全场景扫描（1900+ 实例会分钟级卡死）。

### 5. 面编辑双向同步（三视图改参数）

`geometry/faces.py` 定义每种组件的面模板（面属性 ↔ 组件参数的映射 `param_map`）；`utils/face_mapper.py` 的 `FaceEditSession` 记录编辑前状态，提交时 diff 反推参数 → 批量重生成面 → 同步更新 BIMBase 实体（不重新放置）。

> 通俗说：在图纸的三视图上直接拉尺寸，背后的 3D 模型参数自动跟着改——把「改模型」变成「改图纸」。

复杂构件（门式桥墩/引桥桥墩/索缆锚锭/承台桩基）走 Qwen-VL 图纸识别 → `component_matcher` 模板匹配 → `generated_component_cache` 生成独立 .py 到 `cad组件缓存/` 执行。

### 6. 坐标系统与画布

虚拟 A3 画布 420×297mm，世界坐标原点左下、Y 向上；屏幕坐标 Y 翻转（`utils/coord.py`）；`zoom_at` 以鼠标位置为不动点缩放。吸附系统支持端点/交点/中心/垂足/网格（`utils/snap.py`）。撤销/重做 50 步历史栈。

### 7. DWG/PDF 链路

- 导入 DWG → ODA 转 DXF → ezdxf 解析；导出先写 DXF 再 ODA 转 DWG，ODA 缺失时回退 DXF（`utils/dwg_handler.py`）；
- 矢量 PDF 导入经 PyMuPDF（pt→mm，Y 翻转，`utils/pdf_handler.py`）；
- 「识别三视图」：简单构件走本地线条聚类规则（`utils/pdf_view_recognizer.py`，第一角投影），复杂构件走 Qwen-VL 多模态识别（`utils/drawing_recognizer.py`）。

## 使用说明

1. **首次使用**：面板点「自动配置环境」→ 弹窗显示各项检测结果 → 失败项按 `CADBoard_env_setup.log` 排查。
2. **画图**：点「CAD画板」→ 工具栏或快捷键绘图（L 直线、C 圆、REC 矩形、PL 多段线…）；底部命令行支持坐标 `(100,200)`、相对 `@50,30`、极坐标 `@100<45`；滚轮缩放、中键平移、ESC 回选择模式；支持图层、吸附、撤销/重做、3D 预览。
3. **AI 助手**：工具栏「AI助手」→ 右侧「配置」填 DeepSeek/Coze/百度 Key → 输入自然语言（2D："画一个半径50的圆"；3D："在(1000,2000,500)生成半径300高800的圆柱"、"沿X轴每隔10放5个圆柱"、"把选中的圆柱半径改成400"）；云端命令需确认后执行；🎤 按钮语音输入。
4. **同步 BIMBase**：「同步到BIMBase」输入放置基准坐标 → 画板元素变成参数化组件；在 BIMBase 改参后「从BIMBase更新」回写画板。
5. **图纸识别建模**：导入 PDF 三视图 →「识别三视图」（复杂构件需先配 DashScope Key）→ 面编辑模式改尺寸反推参数 → 同步到 BIMBase。

完整操作手册见 `操作步骤文档.txt`（v1.3）。

## 测试

| 文件 | 怎么跑 | 测什么 |
|---|---|---|
| `test_ai_modeling_bridge.py` | `python CADBoard/test_ai_modeling_bridge.py` | AI 路由单元测试（纯标准库，无需 BIMBase/Qt） |
| `test_cached_component_ops.py` | `python CADBoard/test_cached_component_ops.py` | 缓存组件 AI 操作回归（无需 BIMBase） |
| `test_audio.py` | `python CADBoard/test_audio.py` | 音频设备诊断（需 PyQt5） |
| `test_noumenon_replace.py` / `测试.py` | BIMBase 命令行 exec（文件头有完整命令） | pyp3d 改参 API 行为 |
| 手动测试 | 见 `docs/测试文档.md` | 绘图/编辑/DWG/PDF/AI 面板 7 条回归指令 |

## 报错与调试

- **日志**：`CADBoard_error.log`（画板）、`bimbase_sync_debug.log`（同步+AI 路由）、`ai_modeling_launcher.log`（3D 代理执行）、`face_debug.log`（面编辑）、`CADBoard_env_setup.log`（环境配置）；崩溃生成 `CADBoard_CRASH.txt`。
- **报错记录**：`docs/报错处理记录.md` 15 条，涵盖启动闪退、同步失败、模块污染（`'module' object is not callable'`）、颜色必须写 `"r,g,b,a"` 字符串、同名 bimbase_sync 冲突等。
- **调试方法**：`组件调试指南.md` —— pyp3d 只能在 BIMBase 进程内调试的三种方案（独立脚本/命令行 exec/debugpy 附加进程）。

## 目录结构

```
CADBoard/
├── main.py                  # CAD画板入口（PID 修复、窗口单例、崩溃捕获）
├── board.py                 # 主窗口 CADBoardWindow + CanvasWidget（约 4200 行）
├── bimbase_sync.py          # 同步引擎：19 个组件类 + BIMBaseSync + 放置策略链
├── ai_modeling_launcher.py  # AI_Modeling 代理执行器（隐藏窗口 + 环境快照恢复）
├── setup_env.py             # 「自动配置环境」按钮入口
├── bridge_disease_launcher.py # 「桥梁病害识别」转发入口
├── preview_3d.py            # 3D 预览窗口
├── face_overview_dialog.py  # 面参数总览/批量改参对话框
├── drawing_ai_config_dialog.py # 图纸识别 API 配置对话框
├── get-pip.py               # 官方 pip 引导（供 BIMBase 内嵌 Python 装 pip）
├── commands/                # 16 个绘图/编辑命令（继承 base_command.BaseCommand）
│   ├── base_command.py      # 命令基类 + 点选/框选
│   ├── line/circle/arc/rectangle/polyline/polygon/ellipse/point/spline_command.py
│   ├── delete_command.py / divide_command.py
│   ├── modify_transform.py  # 复制/移动/旋转/缩放
│   ├── modify_advanced.py   # 镜像/偏移/阵列/拉伸
│   ├── modify_edit.py       # 修剪/延伸/打断/合并/倒角/圆角/分解
│   └── solid_commands.py    # 7 种 3D 实体命令
├── geometry/
│   ├── elements.py          # 全部 2D 元素类（世界坐标 mm、序列化、图层）
│   └── faces.py             # 面模板 + FaceManager（参数↔面双向映射）
├── utils/
│   ├── ai_panel.py          # AI 面板：三级路由 + DeepSeek/Coze 流式 + 语音
│   ├── ai_executor.py       # AI 返回 JSON 的解析与批量执行
│   ├── ai_modeling_bridge.py # AI_Modeling 解析桥接
│   ├── bimbase_agent.py     # 轻量工具注册表 Agent（12 个工具）
│   ├── bimbase_pid.py       # BIMBase.exe PID 枚举写回
│   ├── component_registry.py # element_id→参数 单例注册表
│   ├── component_matcher.py / generated_component_cache.py # 图纸识别→组件模板/缓存执行
│   ├── drawing_recognizer.py / pdf_view_recognizer.py # Qwen-VL / 本地规则三视图识别
│   ├── dwg_handler.py / pdf_handler.py # DWG/DXF/PDF 导入导出
│   ├── env_config.py        # 环境配置核心
│   ├── coord.py / snap.py / layer_manager.py # 坐标/吸附/图层
│   ├── face_mapper.py       # 面编辑会话
│   ├── voice_input.py       # 百度语音识别
│   └── mcp_tools.py         # MCP 工具注册表（预留，未启用）
├── training/                # EfficientNet-B0 构件分类训练脚本（datasets/ 目前为空）
├── docs/                    # 模块文档（功能说明/测试/报错记录）
├── 操作步骤文档.txt          # 画板完整操作手册（v1.3）
├── 组件调试指南.md           # pyp3d 调试三种方案
├── 面编辑功能开发总结与技术文档.txt # 面编辑架构与已知问题
└── Picture/                 # 图标
```

> 注意：根目录下的 `dwg_handler.py`、`modify_edit.py`、`modify_advanced.py`、`snap.py` 是旧版遗留副本，实际生效的是 `utils/`、`commands/` 下的新版；`board_patch.py` 等 patch 脚本为开发期一次性工具；`BIMPyPlugin.xml` 是旧清单副本，以根目录 `CADBoard.pyplugin` 为准。

## 文档

- [CAD画板功能说明](docs/CAD画板功能说明.md)
- [AI智能建模说明](docs/AI智能建模说明.md)
- [桥隧病害识别说明](docs/桥隧病害识别说明.md)
- [自动配置环境说明](docs/自动配置环境说明.md)
- [测试文档](docs/测试文档.md)
- [报错处理记录](docs/报错处理记录.md)
