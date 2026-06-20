# BIMBase Python SDK 技术支持提问文档

> **提问人**：BIMBase 插件开发者  
> **软件版本**：BIMBase 建模软件 2025  
> **Python 版本**：3.7.9（嵌入式）  
> **pyp3d SDK 版本**：v18446497937724801024  
> **插件路径**：`C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\AI_Modeling`

---

## 背景说明

我们正在基于 BIMBase Python SDK（pyp3d）开发一个 AI 智能建模插件。核心需求是：

> **用户在插件弹出的模态对话框中输入参数后，程序能全自动在指定世界坐标创建几何体（圆柱、长方体、球体等），不需要用户再到 3D 视图中手动点击确认位置。**

为此，我们已经进行了大量技术调研和尝试，但所有"纯 API"路径都无法在非交互环境下创建有效实体。以下是详细的问题。

---

## 问题 1：官方推荐方案是什么？

### 场景描述

我们的插件架构如下：
1. 用户在 BIMBase 中点击插件按钮
2. 弹出 PyQt 模态对话框（`QDialog.exec_()`）
3. 用户在对话框中输入自然语言指令（如"在 (1000,2000,500) 生成半径 300 高 800 的圆柱"）
4. 程序解析参数后，需要**自动**在指定坐标创建可见实体

### 已尝试的方案及结果

| 方案 | 调用方式 | 结果 |
|------|---------|------|
| `place_to()` | `place_to(noumenon, translate(x,y,z))` | `ModelId=-2, ElementId=0`（无效实体） |
| `create_geometry()` | `create_geometry(noumenon)` | `ModelId=-2, ElementId=0`（无效实体） |
| `UnifiedFunction` 底层调用 | `UnifiedFunction('BPParametricComponent', 'BPParametricComponentManager::create')(noumenon)` | `ModelId=-2, ElementId=0`（无效实体） |
| `place()` 后调用 `create_geometry()` | 先 `place(comp)` 启动交互工具，在工具运行期间调用 `create_geometry()` | 仍然是 `ModelId=-2, ElementId=0` |
| `python_transformation_operation()` | 先通过其他方式创建实体，再移动 | 非交互环境下同样无效 |

**结论**：以上所有 Python SDK 中的实体创建 API，在模态对话框环境中均返回无效实体。

### 核心问题

对于这种"从模态对话框中自动创建实体"的需求，**官方推荐的实现方式是什么**？是否有我们遗漏的 API、设计模式或架构思路？

---

## 问题 2：`create_geometry()` 到底需要什么具体的"交互上下文"？

### 现象

`create_geometry()` 的文档说明是：
> "基于当前交互句柄，在全局坐标系的原点创建一个几何体"

但我们发现，"有交互句柄"和"能创建实体"之间还有一层我们未能满足的条件。

### 已验证的细节

1. **单纯的 `create_component()` 预处理 + `create_geometry()`** → 无效
   - `create_component()` 设置了 `PARACMTP_PLACE_CUSTOM_TOOL=True` 等标志
   - 随后调用 `create_geometry()` 仍然返回 `ModelId=-2`

2. **`place()` 启动活跃工具上下文后调用 `create_geometry()`** → 无效
   - 调用 `place(comp)` 启动手动放置工具
   - 工具处于运行状态（等待用户点击）
   - 在此期间调用 `create_geometry(comp)`
   - 结果仍然是 `ModelId=-2, ElementId=0`

3. **从 `UnifiedFunction` 底层直接调用** → 无效
   - 绕过 `interface/__init__.py` 中对 `place_to` 的覆盖
   - 直接调用 `UnifiedFunction(PARACMPT_PARAMETRIC_COMPONENT, "BPParametricComponentManager::create")`
   - 结果仍然是 `ModelId=-2, ElementId=0`

### 核心问题

`BPParametricComponentManager` 在 C++ 端检查的具体条件到底是什么？

- 是**调用线程**必须在 GUI 主线程？
- 是**调用栈**必须处于 `interact()` 回调函数中？
- 是某种我们无法在 Python 端设置的**内部会话状态/标志位**？
- 还是 `place()` 启动的"放置工具上下文"和 `create_geometry()` 需要的"创建上下文"是**两种不同的内部状态**？

了解这个能帮助我们判断：是否存在一种在 Python 端可以合法满足的条件，或者这确实是架构级别的硬性限制。

---

## 问题 3：Python SDK 之外是否有非交互式创建几何的途径？

如果 pyp3d 的所有实体创建 API 确实必须依赖交互上下文，我们想确认是否有其他技术路径可以绕过这个限制。

### 子问题 3.1：`execute_command` 是否支持带参数的命令调用？

我们在 `Support/ShortcutCommand/ShortcutCommand_BIMBASE.xml` 中找到了 `ImportIfcBimebase` 命令，尝试用以下方式程序化导入 IFC 文件：

```python
from pyp3d import execute_command
execute_command('ImportIfcBimebase "C:\\temp\\model.ifc"')
```

BIMBase 状态栏显示：**"执行命令失败!——ImportIfcBimebase"**

同时也尝试了不带引号路径和纯命令名格式，均无效。

**问题**：`execute_command` 的正确参数格式是什么？它是否支持传递文件路径？如果不支持，如何程序化触发 IFC/OBJ/其他格式的导入？

### 子问题 3.2：`BIMBase_command()` 支持的完整命令列表？

SDK 中定义了：
```python
def BIMBase_command(str:str):
    UnifiedFunction(PARACMPT_PARAMETRIC_COMPONENT, PARACMPT_BIMBASE_COMMAND)(str)
```

但 Python 端只发现了一处被注释掉的用法 `# BIMBase_command('pythoncallbackrelease')`。

**问题**：`BIMBase_command` 支持哪些命令字符串？是否有类似于 `CreateCylinder`、`CreateBox` 之类的原生命令可以直接创建几何？是否有完整的命令文档？

### 子问题 3.3：`.NET API (`BIMBaseNet.dll`) 是否有直接写入模型数据库的接口？

我们在安装目录的 `PLATFORM/` 下发现了：
- `BIMBaseNet.dll`
- `BIMBaseNet.BIMCore.dll`
- `BIMBaseNet.Geometries.dll`
- `BIMBaseNet.UI.dll`

尝试用 PowerShell 加载 `BIMBaseNet.dll` 时，报告依赖缺失（未能加载文件或程序集）。

**问题**：`.NET API` 是否暴露了可以绕过 Python SDK 交互限制的几何创建接口？比如 `Model.CreateEntity`、`Document.AddGeometry` 或类似方法？正确的加载方式和入口点是什么？

### 子问题 3.4：P3D 文件格式是否支持程序化追加几何数据？

如果所有 API 路径都不可行，我们想了解是否可以直接操作 `.p3d` 模型文件本身。

**问题**：P3D 文件格式是开放的还是部分开放的？是否支持向已有模型文件追加几何数据？是否有相关的格式文档或示例？

---

## 附录：当前唯一成功的方案（供参考）

作为背景信息，目前我们唯一能让实体成功创建的方案是：

1. 将目标世界坐标**烘焙**到组件的几何定义中（通过 `偏移X/Y/Z` 参数）
2. 调用 `place(comp)` 启动交互放置工具
3. 用 `SendInput` 模拟鼠标点击视图中心（自动点击，用户无感知）
4. 调用 `exit_tool()` 退出工具
5. 几何体因坐标已烘焙，直接出生在正确位置

**效果**：用户输入指令 → 几何体自动出现在正确位置。用户全程不需要手动点击。  
**代价**：技术上属于"模拟鼠标点击"，不够优雅，且依赖 Win32 API。

我们希望找到一个**纯 API 调用**的替代方案，消除对 `SendInput` 的依赖。

---

## 联系方式

> 请技术支持团队回复以上问题，任何方向的指引都会非常有帮助。  
> 如有需要，我们可以提供更详细的日志、测试代码或进行远程调试。

---

*文档生成时间：2026-05-27*  
*基于 BIMBase 建模软件 2025 + pyp3d v18446497937724801024 测试*
