# 临时调试脚本归档

本目录用于存放项目开发过程中产生的临时调试脚本、输出文件和实验性代码。
这些文件不属于正式插件功能的一部分，保留以备后续查错或参考。

## 根目录测试脚本

| 文件 | 说明 |
|---|---|
| `test_modify_commands.py` | 速构智维 8 个修改命令（延伸/拉伸/偏移/倒角等）离线桩件回归，12/12 通过 |
| `test_cmd_name_activation.py` | 命令行回车按命令名/快捷键激活命令的回归测试 |

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

其他零散测试脚本与赛事材料生成脚本。

**PPT 生成（python-pptx）**

| 文件 | 说明 |
|---|---|
| `generate_ppt_challenge_cup.py` | 挑战杯参赛 PPT 生成 |
| `generate_ppt_guochuang.py` / `generate_ppt_guochuang_v2.py` | 国创赛 PPT 生成（v2 为迭代版） |
| `generate_tiaozhanbei_ppt_v2.py` | 挑战杯产业赛道 PPT v2 |

**Word 生成（python-docx，产物在 `docs/国创赛ppt/`）**

| 文件 | 说明 |
|---|---|
| `generate_word_duibiao_v1.py` ~ `generate_word_duibiao_v5.py` | 「智检桥安-命题解决方案（对标版）」v1~v5 迭代生成 |
| `generate_word_guochuang.py` / `generate_word_guochuang_v2.py` | 国创赛 Word 材料生成 |
| `generate_word_company_templates.py` | 企业证明文书模板生成 |

**配图绘制（matplotlib/PIL，产物为 `docs/国创赛ppt/*.png`）**

| 文件 | 产出图 |
|---|---|
| `draw_arch.py` | 架构图_系统总体架构 |
| `draw_before_after.py` | 对比图_检测流程前后对比 |
| `draw_collab.py` | 示意图_产教协同 |
| `draw_dual_form.py` | 示意图_双形态交付 |
| `draw_milestone.py` | 示意图_里程碑 |
| `draw_component_table.py` | 构件清单表 |
| `draw_mindmap_workflow.py` / `draw_mindmap_painpoints.py` / `draw_mindmap_dimension.py` / `draw_mindmap_dimension_v2.py` | 思维导图系列（业务流程/痛点/尺寸计算流程，v2 为迭代版） |
| `draw_model_performance.py` / `draw_model_performance_v2.py` | 模型性能基线与提升（v2 为迭代版） |
| `draw_page_background.py` / `draw_page_background_cover.py` | 页面背景_A4 / 页面背景_封面 |
| `draw_pest.py` | 分析图_PEST |

**测试与备份**

| 文件 | 说明 |
|---|---|
| `_test_parser3.py` | 本地测试 `CADBoard/utils/ai_panel.py` 中的 `LocalCommandParser` |
| `test_regex.py` | 测试中文建模指令的正则表达式提取 |
| `铁路封闭网_原版备份.py` | 铁路封闭网组件原版备份 |

`_ref_media/` 为生成脚本引用的素材；`_ppt_tmp/` 为 PPT 生成临时产物（已在 .gitignore 忽略）。

## 注意事项

- 这些脚本大多依赖本地环境（如 `D:\BIMBASE` 路径、PowerShell、特定 DLL），在新环境中可能需要调整路径。
- 部分脚本输出的 `.txt` 文件体积较大，Git 提交时不会忽略，如需清理可手动删除。
