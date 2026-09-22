# 桥梁病害识别

导入无人机巡检照片，用 **OpenCV 多策略融合 / YOLOv8** 圈出桥隧表面病害，经 **阿里云 Qwen-VL** 大模型逐框诊断后，将病害按等比映射**投影到 BIMBase 真实构件表面**（半透明彩色点云），最后一键生成 **Word 诊断报告**。

> 用一句话说：拍张照片，AI 告诉你梁上哪里有裂缝、有多严重，在 BIM 模型上标出来，还帮你把巡检报告写好。

本模块**不单独注册 `.pyplugin`**，由 速构智维 面板按钮转发调用：

```
BIMBase 面板「速构智维」→「桥梁病害识别」
  → 速构智维/bridge_disease_launcher.py（仅转发，sys.path 加入本目录）
  → 桥梁病害识别/bridge_disease_launcher.py::run_disease_recognition()
  → disease_dialog.py::DiseaseDialog（模态对话框）
```

## 关键技术栈

- **UI**：PyQt5（Qt platform plugin 路径多路探测，兼容 BIMBase 自带 QTBoot）
- **病害检测**：ultralytics YOLOv8n（CPU 推理，`models/disease_yolov8n.pt` 专用权重——**v2 训练成果已接入**，7 类含「已修复」+ `yolov8n.pt` 通用兜底）+ OpenCV 多策略异常检测（免模型，当前对话框默认路径）
- **AI 诊断**：阿里云 DashScope Qwen-VL（`qwen-vl-max`，OpenAI 兼容端点，原图+带框图双图输入，严格 JSON 输出）
- **BIM 集成**：pyp3d（Component/Attr/Cube/Combine/create_material/UnifiedFunction），`bimbase_sync.py` 由 速构智维 提供、动态路径导入
- **报告**：python-docx（Word 诊断报告）
- **训练侧**：torch/torchvision（EfficientNet-B0 构件分类，预留）、OpenCV 伪标签生成、本地标注 GUI
- **数据集**：GYU-DET（11,123 张 6 类）、CODEBRIM（1,022 张 5 类）公开数据集 + 本地巡检报告提取 + 人工标注（合并集 7 类含「已修复」）

## 核心机制（技术说明）

### 1. 检测双模式与检测器路由

`disease_detector.py::DiseaseDetector` 按加载到的权重自动路由：

- **专用模型存在**（`disease_yolov8n.pt`，现为 v2 训练权重）→ YOLO 推理（conf≥0.25，CPU），输出 7 类病害（裂缝、剥落、露筋、蜂窝麻面、渗水、锈蚀、已修复）；
- **只有通用权重** → 不跑 YOLO（通用权重检不出病害），转 `cv_crack_detector.py` 传统裂缝检测；
- **ultralytics 缺失** → 尝试 pip 自动安装 CPU 版 torch。

当前对话框实际使用的是**免模型的 CV 异常检测**（`cv_anomaly_detector.py`），它只做「圈出可疑区域」、不分类，分类交给 Qwen-VL——这样即使没有训练好的模型也能用。

### 2. 五路掩码融合的 CV 异常检测

`cv_anomaly_detector.py::detect_anomalies_cv` 把五种经典图像算法的结果融合，互相补盲：

| 路子 | 算法 | 擅长抓 |
|---|---|---|
| 黑帽变换 | 21×7 细长核 | 细长裂缝 |
| 多尺度自适应阈值 | 3 组 blockSize/C | 不同大小的暗区 |
| K-Means 颜色聚类 | k=3 取最暗+最亮类 | 颜色异常（渗水、锈迹） |
| 局部纹理标准差 | 高于 78 分位 | 剥落、露骨料 |
| Canny 边缘密度 | 高于 88 分位 | 有明确边界的病害 |

再用 **HSV 天空/背景掩码**（高亮低饱和+偏蓝）把天空区域整体剔除，最后长宽比>8 剔除误判、简化 NMS（IoU 0.25）去重、按面积取 top10。

> 通俗说：五个「老师傅」各看一遍照片，把各自觉得可疑的地方画出来，去掉天空背景，重叠太多的框只留一个——不靠任何训练模型，纯规则，所以永远不会「没模型可用」。

### 3. AI 智能诊断（Qwen-VL）

`ai_diagnosis.py`：把**原图 + 带框标注图**两张图一起发给 Qwen-VL，prompt 中附带构件类型和各框像素坐标，要求严格输出 5 字段 JSON（病害类型/严重程度/尺寸/建议等）；解析三级容错（直接 JSON → markdown 代码块 → 大括号截取）；超时 120s。诊断结果逐框回填到病害记录表格，之后可用「清理AI判定非病害」剔除误报。

### 4. 2D 检测框 → 3D 构件面投影（本模块核心）

三步管线（`face_projection.py` + `disease_dialog.py::_on_disease_project`）：

**① 面几何注册与解析计算**。`FACE_REGISTRY` 登记每种构件可投影的面名；`FaceProjectionEngine` 按命名约定反射调用 `_get_{构件}_{面名}_face` 方法，返回 `FaceInfo`（面中心世界坐标、外法向、宽高、U/V 轴单位向量）。每种构件的面几何是**手写解析公式**，从 BIMBase 参数字典计算，且与组件源码的原点约定严格对齐（如柱式桥墩"原点：盖梁前左下角"）。支持**条件面**（墩柱高≤1500 无系梁则返回 None）与**圆柱面展开矩形近似**。

**② 照片 bbox → 面局部坐标（等比铺满）**。假设照片取景范围≈目标面，做归一化线性映射：`u = (cx/photo_w - 0.5) × 面宽`，`v = (0.5 - cy/photo_h) × 面高`（照片 Y 向下取反），颜色查 `DISEASE_COLOR_MAP`。

**③ 局部 → 世界坐标 + 点云放置**。`薄片中心 = 面中心 + u·U轴 + v·V轴 + 法向×2mm`（2mm 偏移避免 z-fighting 闪面）。实际投影用**点云方案**：`PointCloudGenerator` 在病害区域按密度网格生成彩色小点，`_DiseasePointCloudMarker` 把点列表序列化成 `'u,v,z,r,g,b;...'` 字符串存进单个 Attr，`replace()` 时用 `pyp3d.Combine` 合成一个几何体。

> 通俗说：把照片当成「贴」在构件面上的一张纸——框在照片的什么位置，就按比例换算到构件面的什么位置，再沿面的朝向往外挪 2 毫米，撒一把彩色小点标出来。

⚠️ **关键不变式**：点云几何以面中心世界坐标为基准烘焙，放置时必须零变换 `translate(0,0,0)`，否则平移被应用两次。

**基准位置获取多策略回退**：手动输入框 → 参数里的 x/y/z → transformation/Placement 属性（`_extract_xyz_robust` 递归解析多种矩阵形态）→ 原点兜底。

**构件类型识别**（`bimbase_query.py`）：19+ 种构件的参数键名签名打分（required×10 + optional×1），取最高分；选中构件获取走 entityId→datakey 优先，代理实体失败则全场景扫描并让用户从候选中选择。

### 5. 病害框交互控件与报告

- `image_box_widget.py::ImageBoxLabel`：照片上等比缩放显示，框以矢量叠加（不烘焙进图），可点选/拖拽补框/Delete 删框，与记录表格联动；
- **框选颜色与投影颜色一致**（2026-09）：照片上的框、烘焙标注图、报告单框图统一走 `face_projection.DISEASE_COLOR_MAP`（裂缝红/剥落橙/露筋黄/蜂窝麻面紫/渗水蓝/锈蚀灰，未诊断的"异常区域"绿色兜底），不再全红；选中高亮仍为黄色；
- **构件类型按识别时缓存**（2026-09）：记录在创建时缓存当时的构件类型下拉框值，记录表新增「构件类型」列直接可见；「获取当前选中组件」自动切换类型时会弹提示（后续记录归新类型，已有记录不变）；多构件记录可叠加到同一份报告导出；
- `report_generator.py`：python-docx 生成 Word 报告——封面 → 项目概况（病害分布统计）→ 统计表（构件×病害）→ 病害详图（每条记录 + 单框标注图）→ 处理建议汇总（按病害类型×严重程度的内置建议字典，置信度 0.7/0.5 分档）。

### 6. 尺寸量化标定与数字孪生网页导出

- **尺寸标定（参照物框选）**：`dimension_utils.py::calc_scale/box_dimensions`——在照片上框选一个已知实际长度的参照物，换算像素→毫米比例后，该照片所有病害框自动回填 `length_mm/width_mm/area_mm2`（记录表「尺寸(mm)」列），诊断与报告均可携带实测尺寸；
- **🌐 导出网页数据按钮**：把当前病害记录组装为「常泰长江大桥数字孪生.html」可直接导入的 JSON（桩号解析与 `数字孪生/template.html` 的 `parseStakeM` 保持一致，含实测毫米尺寸文字）；
- **数字孪生/**：`template.html` + 本地 three.js（`lib/three.min.js`+`OrbitControls.js`），`build.py` 打包成单文件 `常泰长江大桥数字孪生.html`（离线可用，双击打开），导入上面导出的 JSON 即在 3D 桥模上按桩号定位展示病害；`_export_verify/` 存验证截图与示例导出数据；
- **export_web_data.py**：独立 CLI（纯标准库），把桥梁/隧道病害记录整理成数字孪生网站数据包，默认输出到根目录 `网站数据/`（JSON + 人类可读 summary）。

## 使用说明

1. BIMBase 面板「速构智维」→「桥梁病害识别」，弹出主对话框。
2. **📷 导入无人机照片**（jpg/png/bmp/tiff）。
3. **🔍 自动识别异常区域**：CV 算法圈出红框并逐条加入记录列表；可在照片上点选/拖拽补框/Delete 删框。
4. **🔑 配置 AI Key**（首次）：粘贴 DashScope Key，写入 `disease_config.json`。
5. **🧠 AI 智能诊断**：逐框回填病害类型/严重程度/建议；可随后「🧹 清理AI判定非病害」。
6. **🔍 获取当前选中组件**：先在 BIMBase 选中真实构件（引桥桥墩/柱式桥墩等），系统识别类型并填充「投影面」下拉框；基准坐标读不到时可手动填 `x,y,z`。
7. **🎯 病害投影**：选中记录等比映射到所选面，以彩色点云放入 BIMBase 场景。
8. **📄 生成诊断报告**：选择保存路径，输出 Word 报告。
9. **尺寸标定**（可选）：在照片上框选参照物并输入实际长度，全部病害框自动换算毫米尺寸。
10. **🌐 导出网页数据**：导出数字孪生用 JSON；双击打开 `数字孪生/常泰长江大桥数字孪生.html` 导入该文件即可 3D 可视化。

更详细的字段说明与注意事项见 `桥梁病害识别_使用说明.md`。

## 测试

| 文件 | 怎么跑 | 测什么 |
|---|---|---|
| `test_pier_projection_mapping.py` | `python 桥梁病害识别/test_pier_projection_mapping.py` | 投影映射纯数学验证（8 组断言，不依赖 pyp3d） |
| `test_t_beam_workflow.py` | `python 桥梁病害识别/test_t_beam_workflow.py` | T 梁全流程离线验证（需 cv2/python-docx） |
| `test_projection.py` | BIMBase 内运行 | pyp3d 标记组件放置冒烟 |
| `test_t_beam_projection.py` | BIMBase 命令行 exec | T 梁照片 → 点云投影端到端 |
| `scan_debug.py` | BIMBase 内运行 | 扫描打印所有实例 key/参数，排查构件识别 |
| `training/extract_dataset.py` | 普通 Python | 从 docx/docm 巡检报告提图分类 |

手动测试 10 项见 `docs/测试文档.md`。

## 报错与调试

- **统一日志**：`bridge_disease_debug.log`，各模块带前缀（`[AI_DIAG]`/`[MARKER]`/`[REPORTGEN]`/`[SEL]`/`[SCAN_DBG]`）；入口启动失败用 Windows MessageBoxW 弹窗兜底（pythonw 无控制台）。
- **报错记录**：`docs/报错处理记录.md` 7 类故障（启动、检测不到、框多/少、模型加载、报告失败、投影失败、import 错误）。
- **常见坑速查**：
  - pythonw.exe 下 stdout 为 None、中文乱码 → 入口已强制 UTF-8 代码页并包装 stdout；
  - `dialog.show()` 不阻塞导致闪退 → 必须 `exec_()` 模态；
  - 检测框太多/太少 → 调 `cv_anomaly_detector.py` 顶部 `DEFAULT_MIN_AREA`、黑帽核、阈值参数；
  - 组件类必须**模块级定义**，否则 BIMBase 无法序列化；
  - `P3DInstanceKey` 禁止 `str()`（会抛 `_data` 异常）；
  - 几何烘焙世界坐标后必须**零变换放置**。

## 目录结构

```
桥梁病害识别/
├── bridge_disease_launcher.py   # 模块入口（Qt 环境/编码修复 + 模态对话框）
├── disease_dialog.py            # 主对话框（全部 UI 与业务流程编排，约 2000 行）
├── disease_detector.py          # YOLOv8n 检测封装（懒加载、路由、CV fallback）
├── cv_anomaly_detector.py       # 五路掩码融合异常检测（默认路径，不分类）
├── cv_crack_detector.py         # OpenCV 裂缝检测（YOLO 不可用时的 fallback）
├── ai_diagnosis.py              # Qwen-VL 智能诊断
├── face_projection.py           # 面投影引擎（FaceProjectionEngine/ShadowRegion/PointCloudGenerator）
├── disease_marker.py            # 5 种 pyp3d 标记组件 + 记录持久化
├── bimbase_query.py             # BIMBase 实例扫描 + 参数签名构件类型推断
├── component_classifier.py      # EfficientNet-B0 构件分类（预留，权重未训练）
├── report_generator.py          # Word 报告生成
├── image_box_widget.py          # 照片病害框交互控件
├── dimension_utils.py           # 尺寸标定（参照物→毫米换算）
├── export_web_data.py           # 网站数据导出 CLI（输出 网站数据/）
├── disease_config.json          # AI 诊断配置（⚠️ 含 API Key，注意脱敏）
├── disease_records.json         # 病害标记历史记录
├── models/                      # disease_yolov8n.pt（正式权重=v2 成果，7 类）+ yolov8n.pt（通用兜底）+ v1/轮次备份 + disease_yolov8n_v2/（v2 训练产物：weights、曲线图、results.csv）
├── datasets/                    # 巡检提取集 / YOLO 6类集 / 人工标注集 / 合并集（nc=7）
├── training/                    # 训练流水线：提图/下载/伪标签/标注GUI/合并/训练/进度
│   ├── 人工标注指南.md           # CVAT/LabelImg 标注指南
│   └── local_annotator_README.md # 本地标注工具用法
├── runs/                        # YOLO 验证输出（PR 曲线、混淆矩阵）
├── 数字孪生/                     # template.html + three.js 本地库 + build.py 打包 + 常泰长江大桥数字孪生.html（单文件离线版）+ _export_verify/
├── 数字孪生.zip                  # 数字孪生平台打包分发版
├── 桥梁病害识别_使用说明.md      # 面向用户的详细使用说明
├── Picture/                     # 图标
└── docs/                        # 功能说明 / 测试文档 / 报错处理记录
```

## 现状说明（诚实记录）

- 当前 UI 检测入口只暴露 **CV 异常识别** 路径；YOLO 七分类能力在代码层保留（`disease_detector.py`），对话框暂无「开始检测」按钮。**v2 训练权重已部署为正式模型**（`models/disease_yolov8n.pt` 即 v2 best 权重，7 类含「已修复」；v1 备份为 `models/disease_yolov8n_v1_backup.pt`），经 `DiseaseDetector` 调用即生效。
- `component_classifier.py`（EfficientNet-B0 19 类）实现完整，但权重未训练、界面未接入，属预留能力。
- `_on_face_project` / `_on_texture_project` / `_on_pointcloud_project` 三个测试方法未连接按钮，为隐藏调试入口。
- 最近一轮训练（v2）：合并集（nc=7 含「已修复」）、141 epochs、CPU，mAP50 约 0.33（`models/disease_yolov8n_v2/results.csv`），模型精度仍有较大提升空间——这也是后续工作方向。
- 原「投影测试××」4 个简化组件已从 `组件测试/` 删除，投影测试请改用真实构件。

## 文档

- [功能说明](docs/功能说明.md)
- [测试文档](docs/测试文档.md)
- [报错处理记录](docs/报错处理记录.md)
- [使用说明](桥梁病害识别_使用说明.md)

## 与 速构智维 的关系

- 本模块从 速构智维 拆分出来独立管理；`速构智维/bridge_disease_launcher.py` 保留为转发入口，面板按钮路径不变。
- `bimbase_sync.py`（pyp3d 组件类与放置策略）仍由 速构智维 提供，本模块通过动态路径导入复用。
