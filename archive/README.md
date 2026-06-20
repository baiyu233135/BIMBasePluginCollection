# 临时调试脚本归档

本目录用于存放项目开发过程中产生的临时调试脚本、输出文件和实验性代码。
这些文件不属于正式插件功能的一部分，保留以备后续查错或参考。

## 子目录说明

### `dll_inspect/`

用于分析 BIMBase 相关 DLL 的程序集信息、导出函数、公共类型等。

| 文件 | 说明 |
|---|---|
| `analyze_dlls.py` | 用 `pefile` 扫描 PLATFORM 和 BIMBase 目录下的 DLL，判断是否为 .NET assembly 并列出导出函数 |
| `analyze_pe.py` | 类似 `analyze_dlls.py`，列出前 10 个导出函数 |
| `check_exports.py` | 针对指定 DLL 检查导出表数量及 .NET COM descriptor |
| `deep_inspect.ps1` | 深度反射单个 DLL，列出公共类型、方法签名、构造函数 |
| `inspect.ps1` | 主反射脚本，读取 `dlls.txt` 并输出程序集信息到 `output.txt` |
| `inspect_dll.ps1` | 类似 `inspect.ps1`，硬编码 DLL 路径并带 AssemblyResolve 处理 |
| `inspect_dll_safe.ps1` | 使用 `ReflectionOnlyLoadFrom` 的安全/兼容版 |
| `run_inspect.py` | Python 编排脚本，生成 `dlls.txt` 并调用 PowerShell 执行 |
| `dlls.txt` | 待扫描的 DLL 路径列表 |
| `bimbase_types.txt` | `BIMBaseNet.dll` 反射结果（213 个公共类型） |
| `geometries_types.txt` | `BIMBaseNet.Geometries.dll` 反射结果 |
| `output.txt` | `inspect.ps1` 的运行输出 |

### `pdf_inspect/`

用于测试读取 PDF 矢量元素的脚本。

| 文件 | 说明 |
|---|---|
| `_inspect_pdf.py` | 用 PyMuPDF 读取 `测试1.0.pdf`，统计每页矢量元素 |
| `_inspect_pdf2.py` | 读取 PDF 第 1 页，将绘图元素坐标转换为毫米 |

### `misc/`

其他零散测试脚本。

| 文件 | 说明 |
|---|---|
| `_test_parser3.py` | 本地测试 `CADBoard/utils/ai_panel.py` 中的 `LocalCommandParser` |
| `test_regex.py` | 测试中文建模指令的正则表达式提取 |

## 注意事项

- 这些脚本大多依赖本地环境（如 `D:\BIMBASE` 路径、PowerShell、特定 DLL），在新环境中可能需要调整路径。
- 部分脚本输出的 `.txt` 文件体积较大，Git 提交时不会忽略，如需清理可手动删除。
