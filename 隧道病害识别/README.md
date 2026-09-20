# 隧道病害识别

导入隧道巡检照片，用 **OpenCV 多策略融合 CV 检测**圈出衬砌/路面/洞门/检修道/排水表面病害，经 **阿里云 Qwen-VL** 大模型逐框诊断后，将病害按等比映射**投影到 BIMBase 隧道构件表面**（彩色点云），最后一键生成 **Word 诊断报告**。

> 用一句话说：拍张隧道巡检照片，AI 告诉你衬砌哪里有裂缝、有多严重，在 BIM 模型上标出来，还帮你把巡检报告写好。

本模块是**独立注册的 `.pyplugin` 插件**（与桥梁版依附于速构智维不同），入口链路：

```
BIMBase 面板「隧道病害识别」→「隧道病害识别」按钮
  → 隧道病害识别.pyplugin（command: tunnel_disease_launcher.py）
  → tunnel_disease_launcher.py::run_disease_recognition()
  → disease_dialog.py::DiseaseDialog（模态对话框）
```

## 关键技术栈

- **UI**：PyQt5 纯代码模态对话框（左侧 4 个 QGroupBox + 右侧照片预览/记录表格）
- **病害检测**：统一病害模型 `models/disease_yolov8n.pt`（YOLOv8n，桥隧合并训练，nc=7，推理结果归并为隧道 4 类）+ OpenCV 多策略异常检测兜底（`cv_anomaly_detector.py::detect_anomalies_cv`，免模型，只圈出可疑区域、不分类，分类交给 Qwen-VL）
- **AI 诊断**：阿里云 DashScope Qwen-VL（`qwen-vl-max`，OpenAI 兼容端点，原图+带框图双图输入，严格 JSON 输出）
- **BIM 集成**：pyp3d；`bimbase_sync.py` 随本插件自带（从速构智维复制），不再动态依赖速构智维目录
- **报告**：python-docx（Word 诊断报告）

## 核心机制（技术说明）

### 1. CV 异常检测（无模型时的兜底路径）

`cv_anomaly_detector.py::detect_anomalies_cv(image_path)` 融合多种经典图像算法互相补盲（黑帽变换抓细长裂缝、多尺度自适应阈值抓暗区、K-Means 聚类抓颜色异常、局部纹理差异抓剥落、边缘密度抓有明确边界的病害、天空/背景掩码剔除误检），NMS 去重后按面积取 top N。返回 `disease_detector.DiseaseResult` 列表（`.bbox` / `.confidence` / `.class_name`，class_name 均为占位标签 `"异常区域"`）。

自动识别按钮统一经 `disease_detector.DiseaseDetector().detect()` 调度：存在 `models/disease_yolov8n.pt` 时走 YOLO 推理（7 类归并为 4 类，见「统一病害模型」一节），模型缺失时自动回退到本 CV 路径。

对话框 `_on_detect_anomalies` 通过 `_normalize_detect_result` 归一化结果（兼容对象与字典两种形态），置信度经 `_confidence_to_severity` 映射为严重程度（≥0.75 严重 / ≥0.5 中等 / 否则轻微）。

### 统一病害模型（YOLO 自动分类，可选）

病害自动识别优先使用**统一病害模型** `隧道病害识别/models/disease_yolov8n.pt`：

- **模型来源**：桥梁 + 隧道病害数据合并训练的 YOLOv8n，nc=7，类别顺序为
  桥梁版顺序：裂缝 / 剥落 / 露筋 / 蜂窝麻面 / 渗水 / 锈蚀 / 已修复。
  训练管线完成后会自动放入 `models/` 目录（见 `models/模型放置说明.txt`）。
- **归并规则**：模型 7 类输出在隧道插件显示层统一归并为 4 类
  （`disease_detector.py::UNIFIED_TO_TUNNEL`，`merge_to_tunnel_class`）：

  | 统一模型类别（7 类） | 隧道显示层（4 类） |
  |---|---|
  | 裂缝 | 裂缝 |
  | 渗水 | 渗水 |
  | 剥落 | 剥落 |
  | 露筋 / 蜂窝麻面 / 锈蚀 / 已修复 | 其他 |

- **加载顺序**（`disease_detector.py`）：优先 `models/disease_yolov8n.pt`（7 类推理，
  返回前按上表归并）；文件不存在时回退通用预训练权重 `models/yolov8n.pt`
  并走 CV 兜底检测（只圈「异常区域」、不分类）；两者都缺失时自动识别不可用，
  仍可手动框选。归并后界面/投影/报告始终只出现 4 类，颜色与
  `face_projection.DISEASE_COLOR_MAP` 一致。

### 2. AI 智能诊断（Qwen-VL）

`ai_diagnosis.py::diagnose_image_safe`：把**原图 + 带框标注图**两张图一起发给 Qwen-VL，prompt 中附带构件类型和各框像素坐标，要求严格输出 JSON（病害类型/严重程度/尺寸/建议等）；解析多级容错。诊断结果逐框回填到病害记录表格，之后可用「清理AI判定非病害」剔除误报。

### 3. 2D 检测框 → 3D 构件面投影

管线在 `face_projection.py` + `disease_dialog.py::_on_disease_project`：

- **面几何注册**：`FACE_REGISTRY` 登记每种隧道构件可投影的面（衬砌→拱圈内壁/仰拱内壁，路面→顶面，洞门→正面，检修道→左右检修道顶面/内侧面，排水→沟底面）；`FaceProjectionEngine` 按命名约定反射调用面几何方法，返回 `FaceInfo`（面中心世界坐标、外法向、宽高、U/V 轴单位向量）。隧道组件坐标系：轴线沿 **Y**（0→隧道长度，洞口朝 ±Y），横断面在 **XZ** 面（X 横向、Z 竖向；起拱线 z=0、拱顶 z=拱仰厚度、仰拱底 z=-底部高度），与 `组件成品/隧道.py` 一致。
- **照片 bbox → 面局部坐标（等比铺满）**：假设照片取景范围≈目标面，做归一化线性映射（照片 Y 向下取反），颜色查 `DISEASE_COLOR_MAP`。
- **局部 → 世界坐标 + 点云放置**：`PointCloudGenerator` 在病害区域按密度网格生成彩色小点，`create_point_cloud_marker` 把点列表序列化进单个 Attr，`place_to` 时用**零变换**放置（点云几何以面中心世界坐标为基准已烘焙，非零变换会导致平移应用两次）。
- **弧面贴面（拱圈/仰拱内壁）**：这两个面的 `FaceInfo.surface_fn` 携带弧面映射——u 为距拱顶的弧长（左负右正）、v 沿隧道纵向 Y，逐点精确落在三点圆弧（32 段离散的二次贝塞尔近似）上，并沿该点内法线偏移 2mm 防 z-fighting；点云以真 3D 局部坐标下发（`face_plane='xyz'`），不再用拱顶切平面近似。

**基准位置获取多策略回退**：手动输入框 → 参数里的 x/y/z → transformation/Placement 属性（`_extract_xyz_robust` 递归解析多种矩阵形态）→ 原点兜底。

**构件类型识别**（`bimbase_query.py::infer_bridge_component_type`）：按参数键名签名打分（required×10 + optional×1）取最高分；选中构件获取走 entityId→datakey 优先，代理实体失败则全场景扫描并让用户从候选中选择。

### 4. 病害框交互控件与报告

- `image_box_widget.py::ImageBoxLabel`：照片等比缩放显示，框以矢量叠加（不烘焙进图），可点选/拖拽补框/Delete 删框，与记录表格双向联动；
- **框颜色与投影颜色一致**：照片框、烘焙标注图、报告单框图统一走 `face_projection.DISEASE_COLOR_MAP`（裂缝红/渗水蓝/剥落橙/其他灰），未诊断的 `"异常区域"` 占位标签走绿色兜底 `_FALLBACK_COLOR`；选中高亮为黄色；
- **构件类型按录入时缓存**：记录在创建时缓存当时的构件类型下拉框值，「获取当前选中组件」自动切换类型时弹提示（后续记录归新类型，已有记录不变）；
- `report_generator.py`：python-docx 生成 Word 报告——封面 → 项目概况（病害分布统计）→ 统计表（构件×病害）→ 病害详图（每条记录 + 单框标注图）→ 处理建议汇总。

## 常量表位置

| 常量 | 位置 | 取值 |
|---|---|---|
| `COMPONENT_CLASSES`（构件 5 类） | `disease_dialog.py` | 衬砌、路面、洞门、检修道、排水 |
| `DISEASE_CLASSES`（病害 4 类） | `disease_dialog.py`、`disease_detector.py` | 裂缝、渗水、剥落、其他（显示层）；统一模型 7 类经 `UNIFIED_TO_TUNNEL` 归并到这 4 类 |
| `SEVERITY_LEVELS`（严重程度） | `disease_dialog.py` | 轻微、中等、严重、极严重 |
| `DISEASE_COLOR_MAP` / `_FALLBACK_COLOR`（病害颜色） | `face_projection.py` | 裂缝红/渗水蓝/剥落橙/其他灰，未知绿兜底 |
| `FACE_REGISTRY`（构件→投影面） | `face_projection.py` | 见上文第 3 节 |
| `COMPONENT_SIGNATURES`（构件参数签名表） | `bimbase_query.py` | 参数键名 → 构件类型 |
| CV 占位标签 | `disease_dialog.py` 业务流程 | `"异常区域"`（AI 诊断前，绿色兜底） |

## 日志与配置

- **统一日志**：`隧道病害识别/tunnel_disease_debug.log`（插件目录内），对话框写入带 `[REPORT]` / `[SEL]` / `[MANUAL]`（人工标注对照）前缀的日志；各管线模块自带日志前缀。
- **AI 配置**：`隧道病害识别/tunnel_disease_config.json`：
  ```json
  {
    "dashscope_api_key": "",
    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "model": "qwen-vl-max",
    "temperature": 0.3,
    "max_tokens": 2000,
    "max_boxes": 10
  }
  ```
- **病害记录持久化**：`disease_marker.py::RECORDS_PATH`（本模块目录下 `disease_records.json`）。

## 使用说明

1. BIMBase 面板「隧道病害识别」→「隧道病害识别」，弹出主对话框。
2. **📷 导入隧道巡检照片**（jpg/png/bmp/tiff）。
3. **人工标注对照（可选）**：标注目录默认指向 `人工标好/`（YOLO 格式，目录存在即自动生效）；导入的照片若存在同名人工标注，会以白色虚线「人工标注·类名」框叠加显示，自动识别/手动画框后状态区实时显示 `人工标注 3 ｜ 识别一致 2 ✓ ｜ 漏检 1 ｜ 误检 0`（一致率 ≥80% 绿 / ≥50% 黄 / <50% 红），选中记录时附显该条「识别一致 / 误检」判定。
4. **🔍 自动识别异常区域**：优先由统一病害模型（YOLO，识别裂缝/渗水/剥落/其他 4 类）圈出可疑区域；模型缺失时自动回退 CV 算法兜底，并逐条加入记录列表；可在照片上点选/拖拽补框/Delete 删框。
5. **🔑 配置 AI Key**（首次）：粘贴 DashScope Key，写入 `tunnel_disease_config.json`。
6. **🧠 AI 智能诊断**：逐框回填病害类型/严重程度/建议；可随后「🧹 清理AI判定非病害」。
7. **🔍 获取当前选中组件**：先在 BIMBase 选中隧道构件，系统识别类型并填充「投影面」下拉框；基准坐标读不到时可手动填 `x,y,z`。
8. **🎯 病害投影**：选中记录等比映射到所选面，以彩色点云放入 BIMBase 场景。
9. **📄 生成诊断报告**：选择保存路径，输出 Word 报告。

更详细的字段说明与注意事项见 `隧道病害识别_使用说明.md`。

## 目录结构

```
隧道病害识别/
├── tunnel_disease_launcher.py   # 插件入口（Qt 环境/编码修复 + 模态对话框）
├── disease_dialog.py            # 主对话框（全部 UI 与业务流程编排，约 2000 行）
├── disease_detector.py          # DiseaseResult 数据结构 + 病害类型/构件病害映射常量
├── cv_anomaly_detector.py       # 多策略融合异常检测（默认路径，不分类）
├── ai_diagnosis.py              # Qwen-VL 智能诊断
├── face_projection.py           # 面投影引擎（FACE_REGISTRY/FaceProjectionEngine/PointCloudGenerator）
├── disease_marker.py            # pyp3d 标记组件 + 记录持久化
├── bimbase_query.py             # BIMBase 实例扫描 + 参数签名构件类型推断
├── bimbase_sync.py              # pyp3d 放置策略（从速构智维复制，本插件自带）
├── report_generator.py          # Word 报告生成
├── image_box_widget.py          # 照片病害框交互控件（含人工标注虚线叠加层）
├── manual_compare.py            # 人工标注↔自动识别对照逻辑（YOLO 解析/IoU 匹配/统计，纯逻辑无 Qt）
├── tunnel_disease_config.json   # AI 诊断配置（⚠️ 含 API Key，注意脱敏）
├── disease_records.json         # 病害标记历史记录
├── BIMPyPlugin.xml              # 插件注册文件（与根目录 隧道病害识别.pyplugin 同内容）
├── Picture/                     # 图标（隧道病害识别.ico）
├── models/                      # 统一病害模型放置处（disease_yolov8n.pt，见 模型放置说明.txt）
├── 隧道病害识别_使用说明.md      # 面向用户的详细使用说明
├── datasets/                    # 数据集
└── training/                    # 训练相关
```

## 与桥梁病害识别的差异

- **注册方式**：桥梁版依附速构智维面板转发；隧道版独立 `.pyplugin`，按钮、图标、入口均在插件自身。
- **构件体系**：桥梁 19+ 类构件 → 隧道 5 类（衬砌/路面/洞门/检修道/排水），投影面为隧道语义（拱圈内壁、仰拱内壁、沟底面等）。
- **病害体系**：桥梁 7 类（含异常区域兜底标签在表内）→ 隧道 4 类 + 表外占位标签 `"异常区域"`（绿色兜底）。
- **bimbase_sync**：桥梁版动态导入速构智维的副本；隧道版直接随插件自带，对话框内 argv0/路径引用均指向本目录。

## 文档

- [使用说明](隧道病害识别_使用说明.md)
