# AI_Modeling - 新版 AI 智能建模助手

本目录为新版 AI 智能建模插件，采用**本地中文命令解析 + DeepSeek 大模型对话**的双路策略，实现自然语言驱动参数化建模。

## 功能特点

- **本地解析**：将常见中文指令（如“创建一个半径 5 高 10 的圆柱”）直接解析为结构化命令并执行。
- **AI 对话**：本地无法解析时，调用 DeepSeek API 返回 JSON 操作指令。
- **自动放置**：使用多级兜底策略将几何体自动放置到 BIMBase 场景中。
- **阵列与路线**：支持线性阵列、矩形阵列、沿路线布置。
- **语音输入**：集成百度语音识别，支持语音输入指令。

## 目录结构

```
AI_Modeling/
├── ai_modeling/          # 源码包
│   ├── ai_window.py      # 主对话框
│   ├── command_parser.py # 本地命令解析器
│   ├── component_factory.py # 组件工厂与放置策略
│   ├── bimbase_modifier.py  # 实体修改
│   ├── chat_thread.py    # DeepSeek 网络对话线程
│   ├── config.py         # 配置读写
│   ├── array_generator.py # 阵列坐标生成
│   ├── route.py          # 路线等距采样
│   ├── geometry_exporter.py # 几何导出（OBJ/IFC）
│   └── voice_input.py    # 语音输入
├── main.py               # 独立运行入口
├── aim_bimbase_sync.py       # BIMBase 参数化组件定义
├── test_place_to.py      # place_to 测试脚本
├── ai_modeling_config.json # API Key 配置
└── docs/                 # 模块文档
```

## 入口

独立运行：

```bash
python AI_Modeling/main.py
```

在 CADBoard 中调用：

```python
from ai_modeling_launcher import run_ai_modeling
run_ai_modeling()
```

## 配置

编辑 `ai_modeling_config.json`：

```json
{
  "api_key": "sk-...",
  "api_base": "https://api.deepseek.com/chat/completions",
  "model": "deepseek-chat",
  "temperature": 0.3,
  "max_tokens": 2000,
  "baidu_api_key": "...",
  "baidu_secret_key": "..."
}
```

## 文档

- [功能说明](docs/功能说明.md)
- [测试文档](docs/测试文档.md)
- [报错处理记录](docs/报错处理记录.md)

## 与 AI建模 的区别

- `AI建模/` 是早期版本，依赖 ChatGLM 网页和剪贴板代码运行。
- `AI_Modeling/` 是新版独立实现，集成 DeepSeek 和本地解析，无需手动复制代码。
