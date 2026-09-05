# AI_Modeling —— AI 智能建模引擎

基于 BIMBase pyp3d SDK 的 AI 智能建模助手：**本地中文指令解析（优先）+ DeepSeek 大模型对话（兜底）** 双路驱动，把自然语言变成 BIMBase 场景里的参数化构件——创建、复制、修改、删除、移动、阵列、沿路线布置，还能语音输入。

> 用一句话说：对它说"在(1000,2000,500)生成一个半径300高800的圆柱"，构件就出现在模型里。

自 CADBoard 1.2.0 起，本模块的能力已**并入 CADBoard 画板右侧 AI 面板**（日常使用走画板），本目录保留独立运行入口与全部引擎代码。

## 两条使用入口

**① CADBoard 集成入口（推荐，日常用法）**

```
CADBoard 画板 → 工具栏「AI助手」→ utils/ai_panel.py
  → 2D 解析失败 → utils/ai_modeling_bridge.py（动态加载本目录 command_parser.py）
  → 命中 → CADBoard/ai_modeling_launcher.py::execute_modeling_action()
  → 在屏幕外隐藏的临时 AIModelingWindow 事件循环中执行 pyp3d 放置
```

**② 独立运行入口**

```bash
python AI_Modeling/main.py    # 弹出独立对话窗口（模态 exec_()，pyp3d 放置需要事件循环）
```

## 关键技术栈

- **BIM 内核**：pyp3d SDK（Component/Attr/Section/Sweep/Cube/Sphere/Cone/Loft/translate/place_to/UnifiedFunction 等），BIMBase 内嵌 Python 3.7.9
- **界面**：PyQt5 优先、PyQt6 回退（全部文件双导入）；PyQt5.QtMultimedia 录音（16kHz/16bit/单声道，RMS 音量检测）
- **大模型**：DeepSeek API（`deepseek-chat`，temperature=0.3，强制 JSON 输出，SSE 流式，纯标准库 urllib 实现）
- **语音**：百度短语音识别（OAuth token + `vop.baidu.com/server_api`，普通话 dev_pid=1537）
- **其他**：ctypes + Win32 SendInput（模拟鼠标点击兜底放置）；手写 OBJ/IFC2X3 几何导出（文件导入兜底）
- **配置**：`ai_modeling_config.json`（api_key/api_base/model/coze_*/baidu_*），优先用环境变量 `AI_MODELING_PLUGIN_DIR` 定位（规避 BIMBase 编译缓存 BFATemp 导致 `__file__` 失真）

## 核心机制（技术说明）

### 1. 双路解析：本地优先、AI 兜底

每条指令先过本地解析器 `ModelingCommandParser`（`command_parser.py`，897 行）：

```
预处理（全角→半角、汉字数字转阿拉伯、"五百二百一百"坐标连读切 3 段）
  → 单位归一化（mm/cm/m/毫米/厘米/米 → 毫米，或"单位用米"整体声明）
  → ACTION_MAP / COMPONENT_MAP 命中动作与构件
  → 提取参数/位置/阵列/路线/移动/颜色
```

- 方向词映射：上+Z、下-Z、左-X、右+X、前+Y、后-Y；
- "位置不变/不要移动"由 `_detect_preserve_position` 识别，避免误判为移动指令。

本地解析失败才调 DeepSeek：固定 system prompt 约束输出 JSON schema（坐标系 X右/Y前/Z上、单位 mm、9 种组件参数表、route 四种模式），历史只带最近 10 条。

> 通俗说：常用句式本地「秒懂」，不花钱不联网；说得太随意本地听不懂了，才请大模型出山。面板上的 "⚡本地 / ☁AI" 指示告诉你当前走的是哪条路。

### 2. 七级兜底自动放置（核心中的核心）

pyp3d 的实体创建 API 经 NamedPipe 到 BIMBase C++ 端，`BPParametricComponentManager` 校验调用者必须在**合法交互回调链**中——模态对话框里直接调，全部返回 `ModelId=-2`。为此 `component_factory.py::place_component_at`（`:739-905`）实现了逐级回退的策略链：

1. 官方 `create_geometry(translate × comp)`（坐标先烘焙进组件「偏移X/Y/Z」参数，变换用恒等矩阵避免双重偏移）
2. `_PlaceToDirect`（绕过被覆盖的 place_to，直接写变换 + `BPParametricComponentManager::create`，实体计数校验）
3. 原生 `place_to`
4. 坐标烘焙后再 `place_to`
5. 生成临时 IFC/OBJ 文件导入（`geometry_exporter.py` 手写 IFC2X3/OBJ）
6. ctypes SendInput 模拟鼠标点击 BIMBase 视图（先标准化俯视图）
7. `place()` 手动放置

放置期间临时改 `sys.argv[0]` 指向 `aim_bimbase_sync.py`，让 BIMBase 按 DependentFile 找到组件类；成功后写注册表并自动缩放全图。

> 通俗说：正门走不通走侧门，侧门锁了翻窗户，窗户也封了就「遥控鼠标」替人点——总有一级能把构件放进去。

### 3. 同名模块冲突治理

CADBoard 与本模块曾各有 `bimbase_sync.py`，pyp3d 按模块名解析组件类会拿错类导致崩溃。治理：

- 本模块组件类文件改名 `aim_bimbase_sync.py`；
- 加载时若 `bimbase_sync` 未被占用则注册别名，兼容旧工程实体反序列化；
- CADBoard 侧 launcher 执行前快照 `sys.path`/`sys.modules`，finally 恢复。

### 4. 组件注册表（跨会话记忆）

`component_registry.py`：单例 + 延迟加载，key 统一为 `"ModelId=x;ElementId=y"` 字符串，持久化到 `component_registry.json`（placement/params/entity_id）。支撑「复制选中组件」（重启后按 entity_id 查回参数）；`validate_and_update` 启动时剔除已消失实体、用 bounds 刷新 placement。

### 5. 阵列与沿路线/路径布置

- `array_generator.py`：线性/矩形/极坐标阵列坐标生成；
- `route.py`：`Route`（直线/折线按目标弧长在分段上线性插值）与 `ArcRoute`（圆弧按角度等分），`sample_frames` 返回等距采样点 + 单位切线；
- `component_path.py`：把"顶面前边/中线"等描述映射到宿主局部盒的 12 条预定义棱边/中线，子组件按 `atan2(dy,dx)` 绕 Z 轴旋转对齐切向——沿曲线布置的构件会自动"拐弯"。

### 6. 颜色与移动

- 颜色存 `"r,g,b[,a]"` 字符串（pyp3d Attr 只能存标量/字符串，存元组报"该类型尚未注册序列化方法"），`replace()` 末尾统一 `_apply_color_attr` 保持上色；支持"半透明"（alpha 0.5）；
- 移动用 pyp3d `python_transformation_operation` 平移，成功后回写注册表 placement；"移动到(x,y,z)"是绝对坐标，不带"到"是相对位移。

## 使用说明

1. **配置**（首次）：编辑 `ai_modeling_config.json` 填 DeepSeek `api_key`（语音另需百度两个 Key），或在面板点 ⚙️ 配置填写。
2. **打开面板**：CADBoard 画板工具栏「AI助手」（推荐）；或 `python AI_Modeling/main.py` 独立窗口。
3. **输入指令**：打字 / 🎤 语音 / 复杂指令交给 AI 兜底（可勾"AI优先"）。
4. **指令示例**：
   - 创建：`放一个半径2高5的圆柱`、`在(1000,2000,500)生成半径300高800的圆柱`
   - 阵列/路线：`沿X轴每隔10放5个圆柱`、`沿选中的线布置灯柱`
   - 改删移：`把选中的圆柱半径改成400，位置不变`、`删除选中的组件`、`向左移动500`
5. **选中联动**：涉及"选中的"操作前先在 BIMBase 视图中选中实体；缺坐标时会弹输入框询问。
6. **维护**：🧹清理缓存 清空注册表与日志（不删场景几何体）；排查看 `ai_modeling_debug.log`。

## 测试

全部为 unittest 风格独立脚本，4 个可离线跑：

| 文件 | 怎么跑 | 测什么 |
|---|---|---|
| `test_component_registry.py` | `python AI_Modeling/test_component_registry.py` | 注册表持久化 + 解析器回归 |
| `test_pier_parse.py` | 同上 | 引桥桥墩解析/参数过滤/类型推断 |
| `test_new_components_parse.py` | 同上 | 门式桥墩/承台桩基解析（含别名） |
| `test_delete_component.py` | 同上 | 删除链路（解析 + mock + 路由） |
| `test_place_to.py` | BIMBase 命令行 exec | place_to/replace_noumenon 底层接口 |

手动 UI 测试 13 组见 `docs/测试文档.md`。

## 报错与调试

- **日志**：`ai_modeling_debug.log`（主日志）、`ai_modeling_config_debug.log`（配置）、`ai_modeling.log`（入口生命周期）、`CADBoard/ai_modeling_launcher.log`（launcher 侧）。
- **报错记录**：`docs/报错处理记录.md` 5 条：
  1. 放置返回无效实体 → 七级兜底已覆盖；注意模态对话框阻塞问题
  2. DeepSeek 调用失败 → 查 api_key/api_base/model，看日志 HTTP 码
  3. 本地解析失败 → 用标准句式（"创建一个半径5高10的圆柱"），避免方言
  4. 语音识别失败 → 麦克风占用/百度 Key/环境嘈杂（代码对 err_no 6/3300/3301/3302 有针对性提示）
  5. 窗口重复创建 → 已有全局单例缓存机制

## 目录结构

```
AI_Modeling/
├── main.py                  # 独立运行入口（QApplication 管理、窗口单例）
├── aim_bimbase_sync.py      # pyp3d 参数化组件类定义（9 个组件类，由 bimbase_sync.py 改名）
├── component_registry.json  # 注册表数据文件
├── ai_modeling_config.json  # API 配置（⚠️ 含明文 Key，注意脱敏）
├── ai_modeling/             # 源码包
│   ├── ai_window.py         # 主对话框：气泡聊天 UI、本地动作执行、AI 调用与 JSON 执行
│   ├── command_parser.py    # 本地中文指令解析器（正则+映射表）
│   ├── component_factory.py # 组件创建 + 七级兜底放置（核心）
│   ├── bimbase_modifier.py  # 选中实体读取/参数修改/删除
│   ├── component_registry.py# 单例注册表（跨会话持久化）
│   ├── component_path.py    # 沿宿主组件棱边/中线布置
│   ├── array_generator.py   # 线性/矩形/极坐标阵列
│   ├── route.py             # 路线等距采样（直线/折线/圆弧）
│   ├── geometry_exporter.py # 手写 OBJ/IFC2X3 导出（文件导入兜底）
│   ├── chat_thread.py       # DeepSeek 流式 SSE 线程（纯 urllib）
│   ├── config.py            # 配置读写（环境变量定位）
│   └── voice_input.py       # 百度语音识别
├── test_*.py                # 单元测试（见上表）
├── docs/                    # 功能说明 / 测试文档 / 报错处理记录
├── AI自动化扩展路线图.md      # 后续扩展方向规划
├── MCP架构可行性分析.md       # 论证：MCP 无法绕过 pyp3d 交互上下文限制
└── BIMBase技术支持提问.md     # 向官方的提问记录（模态对话框创建实体困境）
```

## 与「AI建模/」的区别

- `AI建模/` 是早期版本（范围外）：打开 ChatGLM 网页，用户手动复制代码再运行；
- `AI_Modeling/` 是新版引擎：DeepSeek API 直连 + 本地解析，无需手动复制代码，能力已并入 CADBoard 画板 AI 面板。

## 文档

- [功能说明](docs/功能说明.md)（10 类指令详解，最全面的使用文档）
- [测试文档](docs/测试文档.md)
- [报错处理记录](docs/报错处理记录.md)
