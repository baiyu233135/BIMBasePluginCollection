# -*- coding: utf-8 -*-
"""
合并两个人工标注数据集并整理为标准 YOLO 训练格式。

合并规则：
1. 新数据集（人工标注数据集00）中的图片与旧数据集（人工标注训练集（T梁））
   重复时，使用新数据集的标签（视为修正版）。
2. 仅存在于旧数据集中的图片，保留旧标签。
3. 仅存在于新数据集中的图片，使用新标签。
4. 合并后按 8:2 划分 train/val，输出到 bridge_disease_merged_yolo/。

运行：
    python merge_manual_datasets.py
"""

import os
import shutil
import random
from pathlib import Path
from collections import Counter

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent  # 桥梁病害识别/
OLD_DIR = BASE_DIR / "datasets" / "bridge_disease" / "by_component" / "人工标注训练集（T梁）"
NEW_DIR = BASE_DIR / "datasets" / "bridge_disease" / "by_disease" / "人工标注数据集00"
DST_DIR = BASE_DIR / "datasets" / "bridge_disease_merged_yolo"

TRAIN_RATIO = 0.8
RANDOM_SEED = 42

DISEASE_CLASSES = ["裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀", "已修复"]
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def collect_pairs(root: Path):
    """收集 root/images 与 root/labels 下的有效 图片-标签 对。"""
    images_dir = root / "images"
    labels_dir = root / "labels"
    pairs = {}
    if not images_dir.exists() or not labels_dir.exists():
        return pairs
    for f in sorted(images_dir.glob("*.*")):
        if f.suffix.lower() not in IMG_EXTS:
            continue
        label = labels_dir / f"{f.stem}.txt"
        if label.exists():
            pairs[f.name] = (f, label)
    return pairs


def main():
    old_pairs = collect_pairs(OLD_DIR)
    new_pairs = collect_pairs(NEW_DIR)

    print(f"旧数据集: {len(old_pairs)} 对")
    print(f"新数据集: {len(new_pairs)} 对")

    # 合并：新数据集标签优先
    merged = dict(old_pairs)
    overlap = set(old_pairs) & set(new_pairs)
    for name in overlap:
        merged[name] = new_pairs[name]
    for name in set(new_pairs) - set(old_pairs):
        merged[name] = new_pairs[name]

    print(f"重复图片(用新标签): {len(overlap)}")
    print(f"合并后总数: {len(merged)}")

    # 划分 train/val
    names = sorted(merged.keys())
    random.seed(RANDOM_SEED)
    random.shuffle(names)
    n_train = int(len(names) * TRAIN_RATIO)
    train_names = names[:n_train]
    val_names = names[n_train:]

    print(f"训练集: {len(train_names)} 张")
    print(f"验证集: {len(val_names)} 张")

    # 清理并重建目标目录
    if DST_DIR.exists():
        shutil.rmtree(DST_DIR)

    class_counter = Counter()
    for split, split_names in [("train", train_names), ("val", val_names)]:
        img_dir = DST_DIR / "images" / split
        lbl_dir = DST_DIR / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for name in split_names:
            img_src, lbl_src = merged[name]
            shutil.copy2(str(img_src), str(img_dir / name))
            shutil.copy2(str(lbl_src), str(lbl_dir / f"{Path(name).stem}.txt"))

            # 统计类别
            with open(lbl_src, encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if parts:
                        class_counter[int(parts[0])] += 1

    # 写 data.yaml
    yaml_path = DST_DIR / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {DST_DIR.resolve().as_posix()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"nc: {len(DISEASE_CLASSES)}\n")
        f.write("names:\n")
        for name in DISEASE_CLASSES:
            f.write(f"  - {name}\n")

    print("\n合并后类别分布：")
    for i, name in enumerate(DISEASE_CLASSES):
        print(f"  {i} {name}: {class_counter.get(i, 0)} 个框")
    print(f"总框数: {sum(class_counter.values())}")

    print(f"\n[完成] 数据集已整理到: {DST_DIR}")
    print(f"[完成] data.yaml: {yaml_path}")


if __name__ == "__main__":
    main()
