# CADBoard - AI智能建模说明

## 功能概述

CADBoard 的 AI 智能建模功能将自然语言指令转换为参数化 BIM 构件。它有两种实现方式：

1. **调用 AI_Modeling**：通过 `ai_modeling_launcher.py` 启动独立的 AI 建模助手窗口。
2. **内嵌 AI 面板**：在 CAD画板内部集成 `utils/ai_panel.py`，实现轻量级 AI 助手。

## 入口

- 插件按钮：**AI智能建模** → `ai_modeling_launcher.py`

## 主要文件

| 文件 | 功能 |
|---|---|
| `ai_modeling_launcher.py` | 入口脚本，加载 `AI_Modeling/main.py` |
| `utils/ai_panel.py` | CAD画板内嵌 AI 面板，含本地解析和 DeepSeek 对话 |
| `utils/ai_executor.py` | AI 结构化指令执行引擎 |
| `utils/mcp_tools.py` | MCP 工具接口 |
| `ai_config.json` | DeepSeek/百度 API Key 配置 |

## 指令流程

```
用户输入自然语言
  ├── 本地解析（LocalCommandParser）
  │     ├── 成功 → 直接调用 ai_executor 执行
  │     └── 失败 → 调用 DeepSeek API
  │             └── 返回 JSON 指令 → ai_executor 执行
  └── 执行结果反馈到 CAD画板或 BIMBase
```

## 本地解析支持

`utils/ai_panel.py` 中的 `LocalCommandParser` 支持以下类型指令：

- 创建基础几何体（圆柱、长方体、正方体、球体、圆锥）
- 修改属性（把/将/让……改成/变成/设为/改为 <数值>）
- 删除实体
- 简单阵列

## 调用 AI_Modeling

```python
import sys
sys.path.insert(0, '../AI_Modeling')
from main import run
run()
```

## 依赖

- `AI_Modeling/` 目录必须存在。
- DeepSeek API Key（如需云端 AI 对话）。
- PyQt5/PyQt6、pyp3d。

## 使用建议

- 简单指令优先走本地解析，响应更快。
- 复杂需求使用 DeepSeek 对话。
- 如果 AI 返回的代码无法执行，可切换到 `AI建模/` 手动复制运行。
