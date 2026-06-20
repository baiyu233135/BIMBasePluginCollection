# 通过 MCP 实现自动放置的可行性分析

## 什么是 MCP？

MCP（Model Context Protocol）是 Anthropic 推出的开放协议，用于标准化 AI 助手与外部工具/数据源的连接。它的核心思想是：

- **MCP Server**：一个独立进程，暴露一组工具（Tools）给 AI
- **MCP Client**：AI 客户端（如 Claude Desktop、Cursor、Kimi 等）
- **通信方式**：stdio（标准输入输出）或 SSE（HTTP）

当 LLM 判断需要调用工具时，Client 启动 Server 进程，发送 JSON-RPC 请求，等待响应。

---

## 核心问题：MCP 能绕过交互上下文限制吗？

### 直接回答：不能

pyp3d 的所有实体创建 API 最终都通过 **NamedPipe → BIMBASE.exe C++ 端**。C++ 端的 `BPParametricComponentManager` 检查的是**调用者是否处于合法的交互回调链中**。

这个检查是**与进程无关**的：
- 从 CADBoard 插件进程调用 → 检查失败（模态对话框阻塞了上下文）
- 从 MCP 独立进程调用 → 检查失败（不在 BIMBase 进程内）
- 从 Python 控制台调用 → 检查失败（没有交互工具上下文）

**MCP 改变的是"谁调用 API"，不是"API 自身的限制"。**

---

## MCP 真正能带来的价值：架构重构

虽然 MCP 不能绕过限制，但它可以改变整个系统的架构，间接解决问题：

### 当前架构的问题

```
用户点击按钮 → CADBoard 插件加载 AI_Modeling
                    ↓
              弹出模态 QDialog
                    ↓
              exec_() 阻塞事件循环
                    ↓
              用户输入指令
                    ↓
              代码调用 pyp3d API
                    ↓
              ModelId=-2（失败）
```

**核心矛盾**：模态对话框阻塞了 BIMBase 的事件循环，导致 pyp3d API 无法获得交互上下文。

### MCP 重构后的理想架构

```
┌─────────────────────────────────────────────────────────────┐
│                     AI 客户端（Claude/Cursor）                │
│                      不需要在 BIMBase 内运行                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP 协议（stdio / HTTP）
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              BIMBase MCP Server（Python 脚本）               │
│                                                               │
│  这是一个 BIMBase 插件脚本，在交互上下文中运行：               │
│  - 通过 launch_tool() 启动                                   │
│  - 在 interact() 回调中处理请求                              │
│  - 或利用 QTimer 在事件循环中轮询                            │
│                                                               │
│  关键优势：它在 BIMBase 的交互上下文中运行！                  │
│  → place_to() / create_geometry() 可以正常工作              │
└─────────────────────────────────────────────────────────────┘
```

**关键洞察**：如果 MCP Server 本身是在 BIMBase 的交互上下文中运行的，那么它在处理请求时就有合法的上下文！

---

## 具体实现方案

### 方案 A：interact() 内循环（最可靠）

```python
# ai_mcp_server.py
from pyp3d import interact, place_to, create_geometry

# MCP 通信队列（可以用文件、NamedPipe、或共享内存）
request_queue = []

def interact():
    """BIMBase 工具交互循环"""
    while True:
        # 1. 检查是否有来自 MCP Client 的请求
        request = check_request_from_mcp_client()
        if request:
            # 2. 在交互上下文中执行实体创建！
            if request['action'] == 'create_cylinder':
                comp = CylinderComponent(**request['params'])
                place_to(comp, translate(request['x'], request['y'], request['z']))
            
            # 3. 返回结果给 MCP Client
            send_response_to_mcp_client({'success': True})
        
        # 4. 让出控制权，等待下一次 interact 调用
        break
```

**问题**：`interact()` 每次只执行一次就 `break`，需要某种机制让它持续运行。

### 方案 B：QTimer 轮询（更灵活）

```python
# 在 BIMBase 插件中注册一个定时器
from pyp3d import *
from PyQt5.QtCore import QTimer

def on_plugin_load():
    timer = QTimer()
    timer.timeout.connect(process_mcp_requests)
    timer.start(100)  # 每 100ms 检查一次

def process_mcp_requests():
    request = read_request_from_pipe_or_file()
    if request:
        # 此时我们在 BIMBase 的主线程中！
        # 如果有活跃的工具上下文，API 可以工作
        pass
```

**问题**：定时器回调是否有交互上下文？取决于 BIMBase 的当前状态。如果用户没有激活任何工具，可能没有上下文。

### 方案 C：自定义工具常驻（最佳）

创建一个自定义 BIMBase 工具，让它长期运行：

```python
# ai_tool.py
from pyp3d import *

class AIPlacementTool:
    def interact(self):
        # 工具处于活跃状态，交互上下文存在
        # 在这里检查 MCP 请求并执行放置
        pass

# 注册工具
launch_tool('ai_tool.py')
```

**问题**：如何保持工具长期运行而不阻塞 UI？BIMBase 的工具系统可能需要用户交互才能保持活跃。

---

## MCP vs 当前 SendInput 方案的对比

| 维度 | MCP 架构 | 当前 SendInput 方案 |
|------|---------|-------------------|
| 是否需要模态对话框 | ❌ 不需要 | ✅ 需要（但可以优化） |
| 是否阻塞 BIMBase | ❌ 不阻塞 | ⚠️ 模态时阻塞 |
| 是否能绕过交互限制 | ❌ 不能 | ❌ 不能 |
| 是否需要交互上下文 | ✅ 需要（通过架构设计获得） | ✅ 通过 SendInput 获得 |
| 实现复杂度 | 🔴 高 | 🟢 低 |
| 稳定性 | 🟡 待验证 | 🟢 已验证（日志 valid=True） |
| 用户体验 | ⭐⭐⭐⭐⭐（自然对话） | ⭐⭐⭐⭐（对话框输入） |

---

## 现实结论

### MCP 不能解决根本问题

pyp3d 的交互上下文限制是 **BIMBase C++ 端的架构设计**，不是通信协议能绕过的。

### MCP 的价值在于"解耦"

如果你希望：
- 在 **Claude Desktop / Cursor / VS Code** 中直接和 BIMBase 对话
- 让 AI 自动理解 BIMBase 的当前状态（选中什么、模型里有什么）
- 把 AI 建模能力开放给其他 AI 客户端

那么 MCP 是有价值的。但它的实现前提是：**BIMBase 端有一个能在交互上下文中运行的常驻服务**。

### 当前最现实的路径

**方案 1（推荐）：继续优化 SendInput 方案**
- 它已经验证成功（`valid=True`）
- 去掉 IFC 导入等失败尝试，减少延迟
- 添加多轮对话、批量编辑等实用功能
- 用户体验接近完美（输入指令 → 几何体出现）

**方案 2（长期）：开发 BIMBase MCP Server**
- 研究如何让 Python 脚本在 BIMBase 中常驻运行
- 探索 `interact()` 或 `QTimer` 机制
- 如果能在交互上下文中稳定运行，再用 MCP 协议包装

---

## 如果你仍然想做 MCP

我可以帮你实现一个 **MCP Server 原型**：

1. 写一个 `bimbase_mcp_server.py`，暴露以下工具：
   - `create_cylinder(x, y, z, radius, height)`
   - `create_box(x, y, z, length, width, height)`
   - `get_model_info()` — 返回当前模型的实体列表
   - `set_view(x, y, z)` — 设置视图方向

2. 通信方式选择：
   - **stdio**：最简单，适合本地测试
   - **HTTP localhost**：更灵活，支持远程连接
   - **NamedPipe**：Windows 本地进程间通信

3. 但关键瓶颈仍然是：Server 中的 pyp3d API 调用需要交互上下文。

**你愿意投入时间研究"如何在 BIMBase 中维持一个常驻的交互上下文"吗？** 如果这个问题能解决，MCP 就是水到渠成的事。
