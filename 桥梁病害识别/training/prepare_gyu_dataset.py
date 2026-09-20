# -*- coding: utf-8 -*-
"""
GYU-DET 数据集处理管线（下载由用户用浏览器完成，本脚本负责校验、解压、抽样、统计）。

数据源：ScienceDB, DOI 10.57760/sciencedb.19893
  train.zip 29.7GB, MD5 a8aad1cc02e86c4857b8315ee9f1606e
  zip 内结构：images/ + labels/ + classes.txt（6 类，类别名以 classes.txt 为准）

目录约定（桥梁病害识别/datasets/gyu_det/，详见该目录 README.md）：
  raw/train.zip        用户下载的原文件
  extracted/train/     解压产物（只读）
  sampled/             分层抽样 + 缩放后的 YOLO 子集（images/ labels/ data.yaml）
  logs/                处理日志

子命令（幂等，可重跑）：
  verify                      校验 raw/train.zip 的 MD5 与大小
  extract                     流式解压到 extracted/train/（已存在则跳过）
  sample --per-class 450      分层抽样、缩放、重写标签 id，输出到 sampled/
  report                      打印 extracted 全量统计（空目录时友好提示）

类别映射（GYU 6 类 -> 项目统一 7 类）：
  cracks->裂缝  spalling->剥落  seepage->渗水
  honeycomb surface->蜂窝麻面  exposed rebar->露筋
  holes->剥落（默认，可用 --holes-map {剥落,其他,skip} 调整）
项目统一 7 类顺序固定：裂缝/剥落/露筋/蜂窝麻面/渗水/锈蚀/已修复
"""

import os
import sys
import json
import time
import random
import shutil
import hashlib
import argparse
import zipfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

from PIL import Image

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent          # 桥梁病害识别/
DEFAULT_DATASET_DIR = BASE_DIR / "datasets" / "gyu_det"

# 各子命令通过 resolve_dirs() 解析路径，支持 --dataset-dir 覆盖（测试/调试用）
DATASET_DIR = DEFAULT_DATASET_DIR
RAW_ZIP = DATASET_DIR / "raw" / "train.zip"
EXTRACTED_DIR = DATASET_DIR / "extracted" / "train"
SAMPLED_DIR = DATASET_DIR / "sampled"
LOG_DIR = DATASET_DIR / "logs"


def resolve_dirs(dataset_dir: Path = None) -> None:
    """根据 --dataset-dir 更新全局路径（默认使用 datasets/gyu_det）。"""
    global DATASET_DIR, RAW_ZIP, EXTRACTED_DIR, SAMPLED_DIR, LOG_DIR
    DATASET_DIR = Path(dataset_dir).resolve() if dataset_dir else DEFAULT_DATASET_DIR
    RAW_ZIP = DATASET_DIR / "raw" / "train.zip"
    EXTRACTED_DIR = DATASET_DIR / "extracted" / "train"
    SAMPLED_DIR = DATASET_DIR / "sampled"
    LOG_DIR = DATASET_DIR / "logs"

EXPECTED_MD5 = "a8aad1cc02e86c4857b8315ee9f1606e"
EXPECTED_SIZE_GB = 29.7
RANDOM_SEED = 42

# 项目统一 7 类（顺序固定，与 bridge_tunnel_unified_yolo/data.yaml 一致）
UNIFIED_CLASSES = ["裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀", "已修复"]

# GYU 类别名（小写） -> 项目统一类别；hole(s) 单独由 --holes-map 决定。
# 官方 classes.txt（MD5 f078630bf0d0614b07c9dc990da40801）实际类别名：
#   Crack / Breakage / Comb / Hole / Reinforcement / Seepage
# 同时保留早期资料中的别名（cracks/spalling/...）以防数据再打包时改名。
DEFAULT_CLASS_MAP = {
    "crack": "裂缝",
    "cracks": "裂缝",
    "breakage": "剥落",
    "spalling": "剥落",
    "seepage": "渗水",
    "comb": "蜂窝麻面",
    "honeycomb surface": "蜂窝麻面",
    "reinforcement": "露筋",
    "exposed rebar": "露筋",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MAX_EDGE = 1280
JPEG_QUALITY = 85

IMG_SUFFIXES = (".jpg", ".jpeg", ".png")


# ============================================================
# 工具函数
# ============================================================
def log_line(msg: str) -> None:
    """打印并追加到日志文件。"""
    print(msg)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "prepare_gyu_dataset.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")


def md5_of_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """流式计算大文件 MD5。"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_gyu_classes(extracted_dir: Path) -> list:
    """读取 extracted/train/classes.txt，返回 GYU 类别名列表（顺序 = class id）。

    不做大小写/空白假设之外的猜测；文件缺失时抛 FileNotFoundError。
    """
    classes_path = extracted_dir / "classes.txt"
    if not classes_path.exists():
        raise FileNotFoundError(f"未找到 {classes_path}（请先运行 extract）")
    with open(classes_path, "r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    if not names:
        raise ValueError(f"{classes_path} 内容为空")
    return names


def build_id_map(gyu_classes: list, holes_map: str) -> dict:
    """构建 GYU class_id -> 统一类别索引 的映射。

    holes_map: 剥落 | 其他 | skip
    无法映射（未知类别且非 holes）时打印警告并 skip。
    """
    id_map = {}
    for gid, name in enumerate(gyu_classes):
        key = " ".join(name.lower().split())
        if key in ("hole", "holes"):
            if holes_map == "skip":
                continue
            unified = holes_map
        elif key in DEFAULT_CLASS_MAP:
            unified = DEFAULT_CLASS_MAP[key]
        else:
            log_line(f"[警告] GYU 未知类别 '{name}' (id={gid})，将跳过该类别标注")
            continue
        id_map[gid] = UNIFIED_CLASSES.index(unified)
    return id_map


def list_label_files(labels_dir: Path) -> list:
    if not labels_dir.is_dir():
        return []
    return sorted(p for p in labels_dir.iterdir() if p.suffix == ".txt")


def parse_label_file(path: Path) -> list:
    """解析 YOLO txt，返回 [(class_id, [x, y, w, h]), ...]，跳过坏行。"""
    boxes = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                log_line(f"[警告] {path.name} 第{ln}行字段不足，已跳过: {line!r}")
                continue
            try:
                cid = int(parts[0])
                coords = [float(v) for v in parts[1:5]]
            except ValueError:
                log_line(f"[警告] {path.name} 第{ln}行无法解析，已跳过: {line!r}")
                continue
            boxes.append((cid, coords))
    return boxes


def find_image_for_label(label_path: Path, images_dir: Path):
    """按同名不同后缀在 images/ 中找对应图片，返回 Path 或 None。"""
    for ext in IMG_SUFFIXES:
        cand = images_dir / (label_path.stem + ext)
        if cand.exists():
            return cand
    return None


def resize_max_edge(img: Image.Image, max_edge: int = MAX_EDGE) -> Image.Image:
    """等比缩放到最长边 max_edge；已经不超大的原样返回。"""
    w, h = img.size
    if max(w, h) <= max_edge:
        return img
    scale = max_edge / max(w, h)
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def print_table(rows, headers) -> None:
    """打印简单的对齐文本表。"""
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join("{:<%d}" % w for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for r in rows:
        print(fmt.format(*[str(c) for c in r]))


# ============================================================
# 子命令：verify
# ============================================================
def cmd_verify(args) -> int:
    print(f"校验文件: {RAW_ZIP}")
    if not RAW_ZIP.exists():
        log_line(f"[失败] 文件不存在: {RAW_ZIP}")
        log_line("       请从 ScienceDB (DOI 10.57760/sciencedb.19893) 下载 train.zip 放到 raw/ 目录")
        return 1

    size = RAW_ZIP.stat().st_size
    size_gb = size / (1024 ** 3)
    print(f"大小: {size:,} 字节 ({size_gb:.2f} GB)，期望约 {EXPECTED_SIZE_GB} GB")

    print("计算 MD5（29.7GB 文件可能需要几分钟）...")
    digest = md5_of_file(RAW_ZIP)
    ok = digest.lower() == EXPECTED_MD5.lower()
    print(f"MD5:  {digest}")
    print(f"期望: {EXPECTED_MD5}")
    if ok:
        log_line(f"[通过] MD5 校验成功 ({size_gb:.2f} GB)")
    else:
        log_line("[失败] MD5 不匹配，文件可能损坏或不完整，请重新下载")
    return 0 if ok else 1


# ============================================================
# 子命令：extract
# ============================================================
def cmd_extract(args) -> int:
    if not RAW_ZIP.exists():
        log_line(f"[错误] 未找到 {RAW_ZIP}，请先下载并放入 raw/ 目录")
        return 1

    classes_marker = EXTRACTED_DIR / "classes.txt"
    if classes_marker.exists():
        log_line(f"[跳过] {EXTRACTED_DIR} 已存在（classes.txt 在），不重复解压")
        return 0

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    log_line(f"开始解压 {RAW_ZIP} -> {EXTRACTED_DIR}")

    t0 = time.time()
    count = 0
    try:
        with zipfile.ZipFile(RAW_ZIP, "r") as zf:
            for info in zf.infolist():
                # 防 zip-slip：拒绝绝对路径和 .. 逃逸
                rel = Path(info.filename)
                if rel.is_absolute() or ".." in rel.parts:
                    log_line(f"[警告] 跳过可疑条目: {info.filename}")
                    continue
                target = EXTRACTED_DIR / rel
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1 << 20)
                count += 1
                if count % 500 == 0:
                    print(f"  已解压 {count} 个文件... ({time.time() - t0:.0f}s)", flush=True)
    except zipfile.BadZipFile:
        log_line("[错误] train.zip 不是有效的 ZIP 文件，可能下载不完整")
        return 1

    log_line(f"[完成] 解压 {count} 个文件，用时 {time.time() - t0:.0f}s -> {EXTRACTED_DIR}")
    if not classes_marker.exists():
        log_line("[警告] 解压完成但未找到 classes.txt，请检查 zip 内部结构")
    return 0


# ============================================================
# 子命令：sample
# ============================================================
def cmd_sample(args) -> int:
    images_dir = EXTRACTED_DIR / "images"
    labels_dir = EXTRACTED_DIR / "labels"

    if not labels_dir.is_dir() or not images_dir.is_dir():
        log_line(f"[错误] 未找到 {images_dir} 或 {labels_dir}，请先运行 extract")
        return 1

    gyu_classes = read_gyu_classes(EXTRACTED_DIR)
    log_line(f"GYU classes.txt ({len(gyu_classes)} 类): {gyu_classes}")
    id_map = build_id_map(gyu_classes, args.holes_map)

    # ---- 扫描全量标签，统计每张图的主要类（出现框数最多的类）----
    label_files = list_label_files(labels_dir)
    if not label_files:
        log_line(f"[错误] {labels_dir} 中没有标签文件")
        return 1

    img_primary = {}        # image_stem -> 统一类别索引
    class_boxes = Counter() # 统一类别索引 -> 框数
    skipped_boxes = 0

    for lp in label_files:
        boxes = parse_label_file(lp)
        per_class = Counter()
        for cid, _coords in boxes:
            if cid in id_map:
                per_class[id_map[cid]] += 1
                class_boxes[id_map[cid]] += 1
            else:
                skipped_boxes += 1
        if not per_class:
            continue
        primary = per_class.most_common(1)[0][0]
        img_primary[lp.stem] = primary

    if skipped_boxes:
        log_line(f"[提示] 共 {skipped_boxes} 个框因类别被 skip/未知而未计入")

    by_class = defaultdict(list)
    for stem, cls in img_primary.items():
        by_class[cls].append(stem)

    rows = []
    for cls_idx, name in enumerate(UNIFIED_CLASSES):
        stems = by_class.get(cls_idx, [])
        rows.append([name, len(stems), class_boxes.get(cls_idx, 0)])
    print("\n[extracted 全量统计] 每类图片数（按主要类计）/ 框数")
    print_table(rows, ["统一类别", "图片数", "框数"])

    # ---- 分层抽样 ----
    rng = random.Random(RANDOM_SEED)
    sampled = {}  # stem -> 统一类别索引
    warn_short = []
    for cls_idx, name in enumerate(UNIFIED_CLASSES):
        stems = sorted(by_class.get(cls_idx, []))
        rng.shuffle(stems)
        take = stems[: args.per_class]
        if len(stems) < args.per_class:
            warn_short.append(f"{name}: 仅 {len(stems)} 张（不足 {args.per_class}）")
        for s in take:
            sampled[s] = cls_idx

    for w in warn_short:
        log_line(f"[警告] {w}")

    # ---- 输出 sampled/（清空旧产物后重写，保证幂等）----
    out_images = SAMPLED_DIR / "images"
    out_labels = SAMPLED_DIR / "labels"
    for d in (out_images, out_labels):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    fail_missing_img = 0
    resized_cnt = 0
    kept_cnt = 0
    t0 = time.time()

    for i, (stem, cls_idx) in enumerate(sorted(sampled.items()), 1):
        label_src = labels_dir / (stem + ".txt")
        img_src = find_image_for_label(label_src, images_dir)
        if img_src is None:
            log_line(f"[警告] 找不到图片 {stem}.*，跳过")
            fail_missing_img += 1
            continue

        # 缩放图片（最长边 MAX_EDGE，等比；标签是归一化坐标，无需变换）
        with Image.open(img_src) as im:
            im = im.convert("RGB")
            if max(im.size) > MAX_EDGE:
                im = resize_max_edge(im, MAX_EDGE)
                resized_cnt += 1
            else:
                kept_cnt += 1
            im.save(out_images / (stem + ".jpg"), "JPEG", quality=JPEG_QUALITY)

        # 重写标签 class_id，坐标原样保留
        lines = []
        for cid, coords in parse_label_file(label_src):
            if cid not in id_map:
                continue
            coords_str = " ".join(f"{v:.6f}" for v in coords)
            lines.append(f"{id_map[cid]} {coords_str}")
        with open(out_labels / (stem + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

        if i % 200 == 0:
            print(f"  已处理 {i}/{len(sampled)} 张... ({time.time() - t0:.0f}s)", flush=True)

    # ---- data.yaml ----
    data_yaml = SAMPLED_DIR / "data.yaml"
    with open(data_yaml, "w", encoding="utf-8") as f:
        f.write(f"path: {SAMPLED_DIR.as_posix()}\n")
        f.write("train: images\n")
        f.write("val: images\n")
        f.write(f"nc: {len(UNIFIED_CLASSES)}\n")
        f.write("names:\n")
        for name in UNIFIED_CLASSES:
            f.write(f"  - {name}\n")

    # ---- 抽样统计 ----
    samp_by_class = Counter(sampled.values())
    rows = []
    for cls_idx, name in enumerate(UNIFIED_CLASSES):
        rows.append([name, samp_by_class.get(cls_idx, 0), class_boxes.get(cls_idx, 0)])
    rows.append(["合计", len(sampled) - fail_missing_img, ""])

    print(f"\n[sampled 抽样结果] per-class={args.per_class}, seed={RANDOM_SEED}, "
          f"holes-map={args.holes_map}")
    print_table(rows, ["统一类别", "抽样图片数", "extracted 框数"])
    print(f"缩放 >{MAX_EDGE}px: {resized_cnt} 张；原尺寸保留: {kept_cnt} 张；"
          f"缺图跳过: {fail_missing_img} 张")
    print(f"输出: {out_images} ({len(list(out_images.iterdir()))} 张)")
    print(f"输出: {out_labels} ({len(list(out_labels.iterdir()))} 个)")
    print(f"输出: {data_yaml}")

    log_line(f"[完成] sample: 共抽样 {len(sampled) - fail_missing_img} 张 -> {SAMPLED_DIR}")
    return 0


# ============================================================
# 子命令：report
# ============================================================
def cmd_report(args) -> int:
    images_dir = EXTRACTED_DIR / "images"
    labels_dir = EXTRACTED_DIR / "labels"

    if not EXTRACTED_DIR.is_dir() or not labels_dir.is_dir() or not images_dir.is_dir():
        print(f"尚未解压：{EXTRACTED_DIR} 不存在或为空。")
        print("请先执行：")
        print("  1. 用浏览器从 ScienceDB 下载 train.zip（DOI 10.57760/sciencedb.19893）")
        print(f"  2. 放到 {DATASET_DIR / 'raw'}")
        print("  3. python training/prepare_gyu_dataset.py verify")
        print("  4. python training/prepare_gyu_dataset.py extract")
        return 1

    try:
        gyu_classes = read_gyu_classes(EXTRACTED_DIR)
    except (FileNotFoundError, ValueError) as e:
        print(f"无法读取类别定义: {e}")
        return 1

    id_map = build_id_map(gyu_classes, "剥落")

    label_files = list_label_files(labels_dir)
    if not label_files:
        print(f"{labels_dir} 中没有标签文件，数据可能尚未解压完整。")
        return 1

    print(f"GYU 类别 ({len(gyu_classes)}): {gyu_classes}")
    print(f"图片目录: {images_dir}")
    print(f"标签文件数: {len(label_files)}")

    # 每类图数（主要类）与框数
    img_primary = {}
    class_boxes = Counter()
    for lp in label_files:
        per_class = Counter()
        for cid, _ in parse_label_file(lp):
            if cid in id_map:
                per_class[id_map[cid]] += 1
                class_boxes[id_map[cid]] += 1
        if per_class:
            img_primary[lp.stem] = per_class.most_common(1)[0][0]

    by_class = defaultdict(int)
    for cls in img_primary.values():
        by_class[cls] += 1

    rows = []
    for cls_idx, name in enumerate(UNIFIED_CLASSES):
        rows.append([name, by_class.get(cls_idx, 0), class_boxes.get(cls_idx, 0)])
    rows.append(["合计", len(img_primary), sum(class_boxes.values())])
    print("\n[每类统计] 图片数按主要类计数（一张图多类时计入框数最多的类）")
    print_table(rows, ["统一类别", "图片数", "框数"])

    # 图片尺寸分布（抽样最多 500 张）
    stems = sorted(img_primary.keys())[:500]
    size_buckets = Counter()
    for stem in stems:
        img = find_image_for_label(labels_dir / (stem + ".txt"), images_dir)
        if img is None:
            continue
        try:
            with Image.open(img) as im:
                w, h = im.size
        except Exception:
            continue
        longest = max(w, h)
        if longest <= 640:
            size_buckets["<=640"] += 1
        elif longest <= 1280:
            size_buckets["641-1280"] += 1
        elif longest <= 2560:
            size_buckets["1281-2560"] += 1
        else:
            size_buckets[">2560"] += 1

    if size_buckets:
        print(f"\n[图片尺寸分布] 抽样 {sum(size_buckets.values())} 张（按最长边分档）")
        for bucket in ["<=640", "641-1280", "1281-2560", ">2560"]:
            if size_buckets.get(bucket):
                print(f"  {bucket}: {size_buckets[bucket]}")
    else:
        print("\n[图片尺寸分布] 未能读取任何图片尺寸")

    return 0


# ============================================================
# 入口
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="GYU-DET 数据集处理管线（verify / extract / sample / report）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dataset-dir", type=Path, default=None,
                        help="gyu_det 数据集根目录（默认 桥梁病害识别/datasets/gyu_det）")

    sub.add_parser("verify", parents=[common], help="校验 raw/train.zip 的 MD5 与大小")

    sub.add_parser("extract", parents=[common], help="流式解压到 extracted/train/（已存在则跳过）")

    p_sample = sub.add_parser("sample", parents=[common], help="分层抽样 + 缩放，输出到 sampled/")
    p_sample.add_argument("--per-class", type=int, default=450,
                          help="每类抽样图片数（默认 450；某类不足则全取并警告）")
    p_sample.add_argument("--holes-map", choices=["剥落", "其他", "skip"], default="剥落",
                          help="holes 类别映射目标（默认 剥落；skip 表示丢弃该类标注）")

    sub.add_parser("report", parents=[common], help="打印 extracted 全量统计（空目录时友好提示）")

    args = parser.parse_args()

    resolve_dirs(args.dataset_dir)

    handlers = {
        "verify": cmd_verify,
        "extract": cmd_extract,
        "sample": cmd_sample,
        "report": cmd_report,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
