# -*- coding: utf-8 -*-
"""
为桥隧病害照片生成 YOLO 格式的伪边界框标签。

策略：
1. 读取 labels.csv 中的图片级病害标签。
2. 用 cv_anomaly_detector 检测每张照片中的异常区域，得到候选边界框。
3. 把图片级病害类别赋给该图片的所有候选框，生成 YOLO 格式标签。
4. 按病害类别分层采样，组成训练/验证子集。
5. 输出 YOLO 数据集目录和 data.yaml。

用途：
- 在没有人工标注的情况下，快速获得可训练的目标检测数据。
- 适用于试点训练，验证流程和模型效果。

运行：
    python generate_yolo_pseudo_labels.py --max-per-class 100
"""

import os
import sys
import csv
import shutil
import random
import argparse
from pathlib import Path
from collections import defaultdict

# 添加桥隧病害识别根目录到路径
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from cv_anomaly_detector import detect_anomalies_cv


# YOLO 病害类别顺序（与 disease_detector.DISEASE_CLASSES 前 6 类一致）
DISEASE_CLASSES = ["裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀"]
CLASS_TO_ID = {name: i for i, name in enumerate(DISEASE_CLASSES)}


def parse_args():
    parser = argparse.ArgumentParser(description="生成 YOLO 伪边界框标签")
    parser.add_argument("--max-per-class", type=int, default=100,
                        help="每类病害最多采样的图片数 (默认: 100)")
    parser.add_argument("--dataset-dir", default=str(_project_root / "datasets" / "bridge_disease"),
                        help="桥隧病害数据集根目录")
    parser.add_argument("--output-dir", default=str(_project_root / "datasets" / "bridge_disease_yolo"),
                        help="YOLO 格式输出目录")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")
    return parser.parse_args()


def load_labels(csv_path: Path) -> list:
    """加载 labels.csv"""
    records = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def sample_by_disease(records: list, max_per_class: int, seed: int) -> dict:
    """按病害类别分层采样。"""
    random.seed(seed)
    by_disease = defaultdict(list)
    for r in records:
        disease = r.get("disease", "").strip()
        if disease in CLASS_TO_ID:
            by_disease[disease].append(r)

    sampled = {}
    for disease, items in by_disease.items():
        random.shuffle(items)
        sampled[disease] = items[:max_per_class]
    return sampled


def generate_labels_for_image(record: dict, src_image_path: Path) -> list:
    """
    对单张图片生成 YOLO 伪标签。

    Returns:
        [(class_id, x_center_norm, y_center_norm, w_norm, h_norm), ...]
    """
    disease = record.get("disease", "").strip()
    if disease not in CLASS_TO_ID:
        return []
    class_id = CLASS_TO_ID[disease]

    if not src_image_path.exists():
        print(f"  [跳过] 图片不存在: {src_image_path}")
        return []

    try:
        results = detect_anomalies_cv(str(src_image_path))
    except Exception as e:
        print(f"  [错误] 异常检测失败: {src_image_path}, {e}")
        return []

    if not results:
        return []

    # 读取图片尺寸
    import cv2
    import numpy as np
    data = np.fromfile(str(src_image_path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return []

    h, w = img.shape[:2]
    labels = []
    for res in results:
        x1, y1, x2, y2 = res.bbox
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)
        bw = x2 - x1
        bh = y2 - y1
        if bw <= 0 or bh <= 0:
            continue
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        labels.append((class_id, cx / w, cy / h, bw / w, bh / h))

    return labels


def build_yolo_dataset(records: list, split: str, output_dir: Path, max_per_class: int, seed: int):
    """构建 YOLO 格式训练集或验证集。"""
    images_dir = output_dir / "images" / split
    labels_dir = output_dir / "labels" / split
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    sampled = sample_by_disease(records, max_per_class, seed)

    total_images = 0
    total_boxes = 0

    for disease, items in sampled.items():
        print(f"[{split}] {disease}: {len(items)} 张")
        for r in items:
            img_path = Path(r["image_path"])
            if not img_path.is_absolute():
                img_path = _project_root.parent / img_path

            stem = f"{disease}_{img_path.stem}"
            ext = img_path.suffix
            dst_img = images_dir / f"{stem}{ext}"
            dst_label = labels_dir / f"{stem}.txt"

            if img_path.exists():
                shutil.copy2(str(img_path), str(dst_img))
            else:
                print(f"  [跳过] 图片不存在: {img_path}")
                continue

            labels = generate_labels_for_image(r, img_path)
            if labels:
                with open(dst_label, "w", encoding="utf-8") as f:
                    for cls_id, cx, cy, bw, bh in labels:
                        f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                total_boxes += len(labels)
            else:
                # 没有检测到异常，写空标签文件
                open(dst_label, "w", encoding="utf-8").close()

            total_images += 1

    return total_images, total_boxes


def write_data_yaml(output_dir: Path):
    """生成 YOLO 数据集配置文件 data.yaml。"""
    yaml_path = output_dir / "data.yaml"
    content = f"""path: {output_dir.resolve().as_posix()}
train: images/train
val: images/val
nc: {len(DISEASE_CLASSES)}
names:
{chr(10).join(f'  - {name}' for name in DISEASE_CLASSES)}
"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[生成] {yaml_path}")


def main():
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir)

    csv_path = dataset_dir / "labels.csv"
    if not csv_path.exists():
        print(f"[错误] 未找到 {csv_path}，请先运行 extract_dataset.py")
        sys.exit(1)

    print("=" * 60)
    print("生成 YOLO 伪边界框标签")
    print("=" * 60)
    print(f"输入: {dataset_dir}")
    print(f"输出: {output_dir}")
    print(f"每类采样数: {args.max_per_class}")
    print("=" * 60)

    all_records = load_labels(csv_path)

    # 按 8:2 从 labels.csv 中划分训练/验证
    # 优先使用 split 字段；如果没有，则按来源文档随机划分
    random.seed(args.seed)
    shuffled = all_records.copy()
    random.shuffle(shuffled)

    train_records = [r for r in shuffled if r.get("image_path", "").startswith("桥隧病害识别/datasets/bridge_disease/raw/all/")]
    # 用全部训练记录作为训练，采样在 build_yolo_dataset 中进行

    n_train = int(len(train_records) * 0.8)
    train_split = train_records[:n_train]
    val_split = train_records[n_train:]

    print(f"\n训练记录: {len(train_split)}, 验证记录: {len(val_split)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    train_imgs, train_boxes = build_yolo_dataset(
        train_split, "train", output_dir, args.max_per_class, args.seed
    )
    val_imgs, val_boxes = build_yolo_dataset(
        val_split, "val", output_dir, args.max_per_class // 2, args.seed + 1
    )

    write_data_yaml(output_dir)

    print("\n" + "=" * 60)
    print("伪标签生成完成")
    print("=" * 60)
    print(f"训练集: {train_imgs} 张, {train_boxes} 个边界框")
    print(f"验证集: {val_imgs} 张, {val_boxes} 个边界框")
    print(f"\n接下来可运行:")
    print(f"  python train_disease_yolo.py --data {output_dir / 'data.yaml'} --epochs 50 --batch 4")


if __name__ == "__main__":
    main()
