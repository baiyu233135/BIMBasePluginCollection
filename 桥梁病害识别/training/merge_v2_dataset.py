# -*- coding: utf-8 -*-
"""
合并 v2 统一训练集：v1 桥隧合并集 + GYU-DET 抽样集 → bridge_tunnel_gyu_v2/

用法：
    python merge_v2_dataset.py

输出：桥梁病害识别/datasets/bridge_tunnel_gyu_v2/
  images/train  images/val  labels/train  labels/val  data.yaml
类别顺序与 v1 一致（7 类：裂缝/剥落/露筋/蜂窝麻面/渗水/锈蚀/已修复）。
GYU 抽样集按 85/15 随机划分（固定种子，可复现）；v1 沿用其已有 train/val 划分。
"""
import os
import random
import shutil
from pathlib import Path
from collections import Counter

TRAINING_DIR = Path(__file__).resolve().parent
BASE_DIR = TRAINING_DIR.parent
V1_DIR = BASE_DIR / "datasets" / "bridge_tunnel_unified_yolo"
GYU_DIR = BASE_DIR / "datasets" / "gyu_det" / "sampled"
OUT_DIR = BASE_DIR / "datasets" / "bridge_tunnel_gyu_v2"

SEED = 42
VAL_RATIO = 0.15
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def collect_labels_count(label_path):
    """统计标签文件里各类实例数（空/缺失文件返回空 Counter）。"""
    cnt = Counter()
    try:
        with open(label_path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if parts:
                    cnt[int(float(parts[0]))] += 1
    except OSError:
        pass
    return cnt


def copy_pair(img, labels_dir, out_split, counters):
    """复制图片及其同名标签到输出目录的指定 split，并统计各类数量。"""
    name = img.name
    stem = img.stem
    dst_img = OUT_DIR / "images" / out_split / name
    shutil.copy2(img, dst_img)
    label = labels_dir / (stem + ".txt")
    if label.is_file():
        shutil.copy2(label, OUT_DIR / "labels" / out_split / (stem + ".txt"))
        counters.update(collect_labels_count(label))


def main():
    random.seed(SEED)
    for split in ("train", "val"):
        (OUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    classes = ["裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀", "已修复"]
    cnt_train, cnt_val = Counter(), Counter()

    # ---- 1. v1 桥隧合并集：沿用已有 train/val 划分 ----
    n_v1 = 0
    for split, counter in (("train", cnt_train), ("val", cnt_val)):
        img_dir = V1_DIR / "images" / split
        if not img_dir.is_dir():
            continue
        labels_dir = V1_DIR / "labels" / split
        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in IMG_EXTS:
                continue
            copy_pair(img, labels_dir, split, counter)
            n_v1 += 1
    print(f"[v1 桥隧合并集] 复制 {n_v1} 张（沿用原 train/val 划分）")

    # ---- 2. GYU 抽样集：85/15 随机划分 ----
    gyu_imgs_dir = GYU_DIR / "images"
    gyu_labels_dir = GYU_DIR / "labels"
    imgs = sorted(p for p in gyu_imgs_dir.iterdir()
                  if p.suffix.lower() in IMG_EXTS) if gyu_imgs_dir.is_dir() else []
    random.shuffle(imgs)
    n_val = max(1, int(len(imgs) * VAL_RATIO))
    n_gyu = 0
    for i, img in enumerate(imgs):
        if i < n_val:
            copy_pair(img, gyu_labels_dir, "val", cnt_val)
        else:
            copy_pair(img, gyu_labels_dir, "train", cnt_train)
        n_gyu += 1
    print(f"[GYU 抽样集] 复制 {n_gyu} 张（val {n_val} / train {n_gyu - n_val}）")

    # ---- 3. data.yaml ----
    yaml_path = OUT_DIR / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {OUT_DIR.as_posix()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("nc: 7\n")
        f.write("names:\n")
        for c in classes:
            f.write(f"  - {c}\n")

    def fmt(cnt):
        return {classes[i]: n for i, n in sorted(cnt.items()) if i < len(classes)}
    print(f"\n输出目录: {OUT_DIR}")
    print(f"train 实例统计: {fmt(cnt_train)}")
    print(f"val   实例统计: {fmt(cnt_val)}")
    total = sum(cnt_train.values()) + sum(cnt_val.values())
    print(f"总实例数: {total}")


if __name__ == "__main__":
    main()
