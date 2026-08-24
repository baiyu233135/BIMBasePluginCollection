# 桥梁病害识别

本模块用于识别桥梁、隧道结构表面的常见病害，并将病害信息生成 Word 诊断报告、投影到 BIMBase 模型中。

## 功能特点

- **病害检测**：基于 YOLOv8n 模型，支持 6 类病害（裂缝、剥落、露筋、蜂窝麻面、渗水、锈蚀）。
- **异常区域识别**：无需训练模型，使用 OpenCV 传统图像处理方法自动圈出 T 梁等混凝土构件表面的异常区域（裂缝、渗水、污渍等），不区分具体病害类型。
- **CV Fallback**：当 YOLO 模型不可用时，使用 OpenCV 传统图像处理方法检测裂缝。
- **构件分类**：基于 EfficientNet-B0 自动识别 19 种桥梁构件类型。
- **病害标记**：在 BIMBase 场景中生成红色标记组件，直观展示病害位置。
- **面投影**：将病害阴影/纹理/点云投影到构件表面。
- **报告生成**：自动生成 Word 格式诊断报告。

## 目录结构

```
桥隧病害识别/
├── bridge_disease_launcher.py   # 模块入口
├── disease_dialog.py            # 主对话框
├── disease_detector.py          # YOLOv8n 病害检测
├── disease_marker.py            # 病害标记组件
├── cv_crack_detector.py         # OpenCV 裂缝检测 fallback
├── cv_anomaly_detector.py       # OpenCV 异常区域检测（T梁等，不分类）
├── component_classifier.py      # 桥梁构件图像分类
├── face_projection.py           # 面投影引擎
├── report_generator.py          # Word 报告生成
├── bimbase_query.py             # BIMBase 构件查询
├── scan_debug.py                # 扫描调试
├── test_projection.py           # 投影测试
├── 桥隧病害识别_使用说明.md      # 原始使用说明
├── models/
│   └── yolov8n.pt               # 预训练权重
├── datasets/                    # 从巡检报告提取的病害照片数据集
│   └── bridge_disease/
│       ├── raw/all/             # 全部导出图片
│       ├── raw/disease_closeup/ # 病害特写照片
│       ├── raw/bridge_overview/ # 桥梁整体照片
│       ├── by_component/        # 按构件类型分类
│       ├── by_disease/          # 按病害类型分类
│       ├── split/train/         # 训练集
│       ├── split/test/          # 测试集
│       ├── labels.json          # 结构化标签
│       └── labels.csv           # CSV 格式标签
├── training/
│   ├── extract_dataset.py       # 从 Word 巡检报告提取图片并分类
│   ├── train_disease_yolo.py    # YOLO 训练脚本
│   └── download_datasets.py     # 数据集下载
├── Picture/
│   └── 桥隧识别.ico              # 图标
└── docs/                        # 技术文档
```

## 投影测试组件

用于验证病害投影效果的 4 个简化参数化组件位于 `组件测试/` 目录下，并注册在 `组件测试.pyplugin` 的“桥隧投影测试”面板：

- `投影测试T梁`
- `投影测试横隔板`
- `投影测试湿接缝`
- `投影测试墩柱`

`face_projection.py` 已同步增加对应的面信息，可在 BIMBase 中选中组件后点击“投影到BIMBase”验证效果。详见 `组件测试/docs/投影测试组件说明.md`。

## 入口

本模块**不单独注册 `.pyplugin`**，仍通过 CADBoard 面板按钮调用：

```text
CADBoard 面板 → 桥梁病害识别 → CADBoard/bridge_disease_launcher.py（转发）
    → 桥隧病害识别/bridge_disease_launcher.py → disease_dialog.py
```

## 依赖

- PyQt5
- pyp3d
- ultralytics（YOLOv8）
- opencv-python
- python-docx
- Pillow
- numpy

## 文档

- [功能说明](docs/功能说明.md)
- [测试文档](docs/测试文档.md)
- [报错处理记录](docs/报错处理记录.md)

## 与 CADBoard 的关系

- 本模块从 CADBoard 中拆分出来，代码独立管理。
- `CADBoard/bridge_disease_launcher.py` 保留为转发入口，确保原有面板按钮路径不变。
- `bimbase_sync.py` 仍由 CADBoard 提供，本模块通过动态路径导入。
