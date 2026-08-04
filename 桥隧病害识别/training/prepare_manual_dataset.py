# -*- coding: utf-8 -*-
"""
将人工标注的 T 梁病害数据集整理为标准 YOLO 训练格式。

功能：
1. 从 人工标注训练集（T梁）/ 读取 images/ 和 labels/。
2. 按 8:2 随机划分为 train / val。
3. 复制到 bridge_disease_manual_yolo/ 标准结构。
4. 生成正确的 data.yaml。

运行：
    python prepare_manual_dataset.py
"""

import os
import shutil
import random
from pathlib import Path

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent  # 桥隧病害识别/
SRC_DIR = BASE_DIR / "datasets" / "bridge_disease" / "by_component" / "人工标注训练集（T梁）"
DST_DIR = BASE_DIR / "datasets" / "bridge_disease_manual_yolo"

TRAIN_RATIO = 0.8
RANDOM_SEED = 42

DISEASE_CLASSES = ["裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀", "已修复"]


def main():
    if not SRC_DIR.exists():
        print(f"[错误] 源目录不存在: {SRC_DIR}")
        return

    src_images = SRC_DIR / "images"
    src_labels = SRC_DIR / "labels"
    if not src_images.exists() or not src_labels.exists():
        print(f"[错误] 源目录缺少 images/ 或 labels/: {SRC_DIR}")
        return

    # 收集有效图片（有对应标签的）
    image_files = []
    for f in sorted(src_images.glob("*.*")):
        if f.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp"]:
            continue
        label_file = src_labels / f"{f.stem}.txt"
        if label_file.exists():
            image_files.append(f)

    print(f"有效图片数: {len(image_files)}")

    # 划分
    random.seed(RANDOM_SEED)
    random.shuffle(image_files)
    n_train = int(len(image_files) * TRAIN_RATIO)
    train_files = image_files[:n_train]
    val_files = image_files[n_train:]

    print(f"训练集: {len(train_files)} 张")
    print(f"验证集: {len(val_files)} 张")

    # 创建目标目录
    for split, files in [("train", train_files), ("val", val_files)]:
        img_dir = DST_DIR / "images" / split
        lbl_dir = DST_DIR / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            shutil.copy2(str(f), str(img_dir / f.name))
            label_src = src_labels / f"{f.stem}.txt"
            shutil.copy2(str(label_src), str(lbl_dir / f"{f.stem}.txt"))

    # 生成 data.yaml
    yaml_path = DST_DIR / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {DST_DIR.resolve().as_posix()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"nc: {len(DISEASE_CLASSES)}\n")
        f.write("names:\n")
        for name in DISEASE_CLASSES:
            f.write(f"  - {name}\n")

    print(f"[完成] 数据集已整理到: {DST_DIR}")
    print(f"[完成] data.yaml 已生成: {yaml_path}")


if __name__ == "__main__":
    main()
