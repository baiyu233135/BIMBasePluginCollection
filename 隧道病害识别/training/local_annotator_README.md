# 本地隧道病害照片标注工具

## 功能

- 浏览病害照片列表
- 用 CV 异常检测自动生成伪标签
- 人工增删改边界框，指定病害类别
- 保存 YOLO 格式标签
- 导出 YOLO 数据集（images/ + labels/ + data.yaml）

## 病害类别（4 类，顺序固定）

| 类别 | 颜色 | 编号 |
|---|---|---|
| 裂缝 | 红 | 0 |
| 渗水 | 蓝 | 1 |
| 剥落 | 橙 | 2 |
| 其他 | 绿 | 3 |

> 构件维度（衬砌、路面、洞门、检修道、排水）仅用于照片按目录分类/筛选，
> **不进入 YOLO 类别**。建议把照片按构件放在不同子目录中，逐目录打开标注。

> **与统一 7 类训练集的关系**：本标注器是 4 类体系（供隧道界面使用）。
> 若标注结果要并入统一病害模型（nc=7：裂缝/剥落/露筋/蜂窝麻面/渗水/锈蚀/已修复）
> 的训练集，合并时按隧道归并规则的逆映射处理：**其他→剥落**（裂缝/渗水/剥落一一
> 对应）。类别 id 的换算与数据集合并由训练管线脚本负责，标注工具本身保持 4 类不变。

## 运行方式

### 1. GUI 模式（推荐）

```bash
cd 隧道病害识别/training
python local_annotator.py
```

打开后操作：

1. 点击 **“打开图片目录”**，选择 `隧道病害识别/datasets/tunnel_disease/` 下的某个图片目录（如按构件分的 `衬砌/`、`路面/` 子目录）。
2. 在左侧列表中点击一张图片。
3. 点击 **“生成伪标签”**，自动用 CV 圈出异常区域。
4. 在图片上用鼠标拖拽添加新框，或选中框后点 **“删除选中框”**。
5. 双击框列表中的条目可查看位置，框的颜色对应病害类别。
6. 点击 **“保存标签”**，生成 YOLO 格式 `.txt`。
7. 点击 **“导出数据集”**，复制 images/labels 并生成 `data.yaml`。

> 注意：保存标签时，标签写在图片目录同级的 `labels/` 目录下
> （代码取 `图片目录.parent / "labels"`）。导出数据集时会自动带上。

### 2. 命令行模式（批量伪标签）

```bash
python local_annotator.py --images <图片目录> --output <标签目录> [--export <导出目录>]
```

示例：

```bash
python local_annotator.py \
  --images ../datasets/tunnel_disease/衬砌 \
  --output ../datasets/pseudo_labels \
  --export ../datasets/tunnel_disease_manual
```

## 快捷键 / 交互

- **鼠标左键拖拽**：在图片上画新框，松开后弹出类别选择对话框
- **“删除选中框”**：删除框列表中选中的框
- **“保存标签”**：把当前图片的所有框写入 YOLO `.txt`
- 保存过的标签在下次打开同一张图片时自动加载

## 导出格式

导出后目录结构：

```
输出目录/
├── images/
│   ├── xxx.jpg
│   └── ...
├── labels/
│   ├── xxx.txt
│   └── ...
└── data.yaml
```

每个 `.txt` 文件每行一个框：

```text
class_id x_center_norm y_center_norm width_norm height_norm
```

`data.yaml` 由导出功能自动生成，内容形如：

```yaml
path: <导出目录绝对路径>
train: images
val: images
nc: 4
names:
  - 裂缝
  - 渗水
  - 剥落
  - 其他
```

## 与 train_disease_yolo.py 的配合

1. 用本工具标注并 **“导出数据集”**，得到含 `data.yaml` 的目录
   （例如 `隧道病害识别/datasets/tunnel_disease_manual/`）。
2. 运行训练脚本：

```bash
cd 隧道病害识别/training
python train_disease_yolo.py --data ../datasets/tunnel_disease_manual/data.yaml --epochs 100
```

3. 训练输出的最佳模型在 `../models/disease_yolov8n/weights/best.pt`，
   类别顺序与 `DISEASE_CLASSES` 一致（0=裂缝, 1=渗水, 2=剥落, 3=其他）。

> 注意：插件自动识别优先加载的是**统一病害模型** `隧道病害识别/models/disease_yolov8n.pt`
> （桥隧合并训练，nc=7，由训练管线统一部署，见 `models/模型放置说明.txt`），
> 本地 4 类训练仅用于试验/过渡。

> 提示：标注工具导出的 `train`/`val` 都指向同一个 `images/` 目录。
   正式训练前建议自行划分训练/验证集（如按 8:2 分目录），
   并相应修改 `data.yaml` 中的 `train`/`val` 路径。

## 如何打包成 exe

如果需要生成独立的 `.exe` 可执行文件，可以使用 PyInstaller：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed local_annotator.py
```

生成的 exe 在 `dist/` 目录下，双击即可运行。

> 注意：exe 仍需依赖 `opencv-python`、`PyQt5`、`numpy`，以及同目录的
> `cv_anomaly_detector.py`（伪标签功能）。PyInstaller 会自动打包第三方依赖。

## 注意事项

- 伪标签默认全部标为“裂缝”（编号 0），需要人工逐个改类。
- 建议先标注 100-300 张，训练后看效果再决定是否扩大。
- 保存标签后，下次打开同一张图片会自动加载已有标签。
