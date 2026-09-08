# 本地病害照片标注工具

## 功能

- 浏览病害照片列表
- 用 CV 异常检测自动生成伪标签
- 人工增删改边界框，指定病害类别
- 保存 YOLO 格式标签
- 导出 YOLO 数据集（images/ + labels/ + data.yaml）

## 运行方式

### 1. GUI 模式（推荐）

```bash
cd 桥梁病害识别/training
python local_annotator.py
```

打开后操作：

1. 点击 **“打开图片目录”**，选择 `桥梁病害识别/datasets/bridge_disease/raw/all/` 或某个子目录。
2. 在左侧列表中点击一张图片。
3. 点击 **“生成伪标签”**，自动用 CV 圈出异常区域。
4. 在图片上用鼠标拖拽添加新框，或选中框后点 **“删除选中框”**。
5. 双击框列表中的条目可查看位置，框的颜色对应病害类别。
6. 点击 **“保存标签”**，生成 YOLO 格式 `.txt`。
7. 点击 **“导出数据集”**，复制 images/labels 并生成 `data.yaml`。

### 2. 命令行模式（批量伪标签）

```bash
python local_annotator.py --images <图片目录> --output <标签目录> [--export <导出目录>]
```

示例：

```bash
python local_annotator.py \
  --images ../datasets/bridge_disease/by_disease/剥落 \
  --output ../datasets/pseudo_labels \
  --export ../datasets/bridge_disease_manual
```

## 病害类别颜色

| 类别 | 颜色 | 编号 |
|---|---|---|
| 裂缝 | 红 | 0 |
| 剥落 | 橙 | 1 |
| 露筋 | 黄 | 2 |
| 蜂窝麻面 | 紫 | 3 |
| 渗水 | 蓝 | 4 |
| 锈蚀 | 灰 | 5 |
| 已修复 | 绿 | 6 |

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

## 如何打包成 exe

如果需要生成独立的 `.exe` 可执行文件，可以使用 PyInstaller：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed local_annotator.py
```

生成的 exe 在 `dist/` 目录下，双击即可运行。

> 注意：exe 仍需依赖 `opencv-python`、`PyQt5`、`numpy`。PyInstaller 会自动打包这些依赖，但体积会比较大。

## 注意事项

- 伪标签默认全部标为“裂缝”（编号 0），需要人工逐个改类。
- 建议先标注 100-300 张，训练后看效果再决定是否扩大。
- 保存标签后，下次打开同一张图片会自动加载已有标签。
