# -*- coding: utf-8 -*-
"""
从 Word 巡检报告中提取病害照片并自动分类。

功能：
1. 使用 zipfile + lxml 直接读取 .docx / .docm 文件内部结构。
2. 导出 word/media/ 下所有图片到 datasets/bridge_disease/raw/all/。
3. 根据图片所在段落附近的题注文字，识别构件类型、病害类型、拍摄类型。
4. 将图片复制到 by_component/、by_disease/ 分类目录。
5. 按 8:2 划分训练集和测试集（按病害类型分层）。
6. 生成 labels.json 和 labels.csv。

优势：
- 不依赖 Microsoft Word COM，避免宏安全、文件锁定、进程残留等问题。
- 兼容 .docx 和 .docm。
"""

import os
import sys
import re
import json
import csv
import shutil
import random
import zipfile
from pathlib import Path
from collections import defaultdict
from xml.etree import ElementTree as ET

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent  # 桥隧病害识别/
DATASET_DIR = BASE_DIR / "datasets" / "bridge_disease"
RAW_DIR = DATASET_DIR / "raw"
BY_COMPONENT_DIR = DATASET_DIR / "by_component"
BY_DISEASE_DIR = DATASET_DIR / "by_disease"
SPLIT_DIR = DATASET_DIR / "split"

PROJECT_ROOT = BASE_DIR.parent

SOURCE_DOCS = [
    Path("数据参考源/桥隧数据源/6.docm"),
    Path("数据参考源/桥隧数据源/7.docm"),
    Path("数据参考源/桥隧数据源/第8册.docx"),
    Path("数据参考源/桥隧数据源/第9册.docx"),
]

# 病害关键词
DISEASE_KEYWORDS = {
    "裂缝": ["裂缝", "裂纹", "开裂", "龟裂", "网状裂缝", "泛白吸附裂缝", "横向裂缝", "纵向裂缝", "竖向裂缝", "斜向裂缝"],
    "剥落": ["剥落", "掉角", "破损", "缺损", "剥离", "露骨料", "混凝土破损"],
    "露筋": ["露筋", "锈胀漏筋", "钢筋外露", "钢筋锈蚀"],
    "蜂窝麻面": ["蜂窝", "麻面", "孔洞", "蜂窝麻面"],
    "渗水": ["渗水", "渗漏", "水渍", "泛白", "泛碱", "析白"],
    "锈蚀": ["锈蚀", "生锈", "腐蚀", "钢构件锈蚀", "涂层脱落"],
}

# 构件关键词
COMPONENT_KEYWORDS = {
    "T梁": ["T梁", "T型梁", "梁底", "翼缘板", "腹板", "马蹄", "齿块", "锚固区"],
    "横隔板": ["横隔板"],
    "湿接缝": ["湿接缝"],
    "墩柱": ["墩柱", "桥墩", "墩身", "柱式桥墩", "薄壁墩"],
}

# 桥梁整体/现场照关键词
OVERVIEW_KEYWORDS = ["全景", "总体", "立面", "正面", "底面", "全貌", "远景", "近景", "正面照", "立面照", "桥底", "总体照片"]

TRAIN_RATIO = 0.8
RANDOM_SEED = 42

# Word XML 命名空间
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def ensure_dirs():
    """确保所有输出目录存在。"""
    dirs = [
        RAW_DIR / "all",
        RAW_DIR / "disease_closeup",
        RAW_DIR / "bridge_overview",
        BY_COMPONENT_DIR,
        BY_DISEASE_DIR,
        SPLIT_DIR / "train",
        SPLIT_DIR / "test",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def classify_disease(text: str) -> str:
    """根据文本识别病害类型。"""
    scores = {}
    for disease, keywords in DISEASE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[disease] = score
    if not scores:
        return "未分类"
    return max(scores.items(), key=lambda x: (x[1], len(x[0])))[0]


def classify_component(text: str) -> str:
    """根据文本识别构件类型。"""
    scores = {}
    for comp, keywords in COMPONENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[comp] = score
    if not scores:
        return "其他"
    return max(scores.items(), key=lambda x: (x[1], len(x[0])))[0]


def is_overview_photo(text: str) -> bool:
    """判断是否为桥梁整体/现场照。"""
    return any(kw in text for kw in OVERVIEW_KEYWORDS)


def safe_filename(name: str) -> str:
    """生成安全的文件名。"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()


def get_image_extension(content_type: str) -> str:
    """根据 contentType 返回图片扩展名。"""
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/bmp": ".bmp",
        "image/tiff": ".tif",
        "image/gif": ".gif",
    }
    return mapping.get(content_type, ".png")


def parse_rels(zip_file: zipfile.ZipFile) -> dict:
    """解析 word/_rels/document.xml.rels，得到 rId -> (target, type, contentType)。"""
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in zip_file.namelist():
        return {}

    rels = {}
    root = ET.fromstring(zip_file.read(rels_path))
    for rel in root.findall("rel:Relationship", NAMESPACES):
        rid = rel.get("Id")
        target = rel.get("Target")
        rel_type = rel.get("Type")
        content_type = None
        if target:
            full_path = "word/" + target.replace("\\", "/")
            try:
                content_type = zip_file.getinfo(full_path).compress_type
            except Exception:
                pass
        rels[rid] = {
            "target": target,
            "type": rel_type,
        }
    return rels


def parse_content_types(zip_file: zipfile.ZipFile) -> dict:
    """解析 [Content_Types].xml，得到文件路径 -> contentType。"""
    ct = {}
    if "[Content_Types].xml" not in zip_file.namelist():
        return ct
    root = ET.fromstring(zip_file.read("[Content_Types].xml"))
    for override in root.findall("{http://schemas.openxmlformats.org/package/2006/content-types}Override"):
        part_name = override.get("PartName", "")
        content_type = override.get("ContentType", "")
        ct[part_name.lstrip("/")] = content_type
    return ct


def extract_images_from_doc(doc_path: Path) -> list:
    """从单个 Word 文档中提取图片和附近题注。"""
    abs_doc_path = (PROJECT_ROOT / doc_path).resolve()
    if not abs_doc_path.exists():
        print(f"[跳过] 文件不存在: {abs_doc_path}")
        return []

    doc_name = safe_filename(abs_doc_path.stem)
    print(f"[打开] {abs_doc_path}")

    try:
        zip_file = zipfile.ZipFile(abs_doc_path, "r")
    except zipfile.BadZipFile:
        print(f"[错误] 不是有效的 ZIP/Word 文件: {abs_doc_path}")
        return []

    rels = parse_rels(zip_file)
    content_types = parse_content_types(zip_file)

    # 读取 document.xml
    doc_xml_path = "word/document.xml"
    if doc_xml_path not in zip_file.namelist():
        print(f"[错误] 未找到 {doc_xml_path}")
        return []

    doc_root = ET.fromstring(zip_file.read(doc_xml_path))

    # 提取所有段落文本
    paragraphs = []
    for para in doc_root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        texts = [t.text for t in para.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
        paragraphs.append("".join(texts).strip())

    records = []
    image_idx = 0

    # 遍历所有段落，查找内联图片
    for p_idx, para in enumerate(doc_root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")):
        context_parts = []
        start = max(0, p_idx - 2)
        end = min(len(paragraphs), p_idx + 3)
        context_parts = paragraphs[start:end]
        context = "\n".join(context_parts)

        # 查找段落中的所有 drawing
        for drawing in para.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"):
            # 查找 blip embed
            for blip in drawing.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
                embed_rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                if not embed_rid:
                    continue

                rel_info = rels.get(embed_rid)
                if not rel_info:
                    continue

                target = rel_info["target"]
                media_path = "word/" + target.replace("\\", "/")
                if media_path not in zip_file.namelist():
                    continue

                # 确定扩展名
                content_type = content_types.get(media_path, "")
                ext = get_image_extension(content_type)

                image_idx += 1
                img_name = f"{doc_name}_img_{image_idx:04d}{ext}"
                img_path = RAW_DIR / "all" / img_name

                # 写出图片
                with open(img_path, "wb") as f:
                    f.write(zip_file.read(media_path))

                records.append({
                    "doc": doc_name,
                    "source": str(doc_path.as_posix()),
                    "type": "inline",
                    "index": image_idx,
                    "image_name": img_name,
                    "image_path": str(img_path.relative_to(PROJECT_ROOT).as_posix()),
                    "context": context,
                })

    print(f"[完成] {doc_name}: 提取 {image_idx} 张图片")
    return records


def copy_to_class_dirs(records):
    """根据分类结果复制图片到 by_component/ 和 by_disease/。"""
    for r in records:
        src = PROJECT_ROOT / r["image_path"]
        if not src.exists():
            continue

        comp = r.get("component", "其他")
        disease = r.get("disease", "未分类")
        photo_type = r.get("photo_type", "unknown")

        if photo_type == "unknown":
            continue

        # 按构件复制
        comp_dir = BY_COMPONENT_DIR / comp
        comp_dir.mkdir(exist_ok=True)
        shutil.copy2(str(src), str(comp_dir / src.name))

        # 按病害复制
        disease_dir = BY_DISEASE_DIR / disease
        disease_dir.mkdir(exist_ok=True)
        shutil.copy2(str(src), str(disease_dir / src.name))

        # 同时复制到 raw/disease_closeup 或 raw/bridge_overview
        if photo_type == "disease_closeup":
            shutil.copy2(str(src), str(RAW_DIR / "disease_closeup" / src.name))
        elif photo_type == "bridge_overview":
            shutil.copy2(str(src), str(RAW_DIR / "bridge_overview" / src.name))


def split_train_test(records):
    """按病害类型分层划分训练集和测试集。"""
    random.seed(RANDOM_SEED)

    by_disease = defaultdict(list)
    for r in records:
        if r.get("photo_type") != "disease_closeup":
            continue
        disease = r.get("disease", "未分类")
        by_disease[disease].append(r)

    train_records = []
    test_records = []

    for disease, items in by_disease.items():
        unique = {r["image_name"]: r for r in items}
        items = list(unique.values())
        random.shuffle(items)
        if len(items) == 1:
            train_records.extend(items)
        else:
            n_train = max(1, int(len(items) * TRAIN_RATIO))
            train_records.extend(items[:n_train])
            test_records.extend(items[n_train:])

    return train_records, test_records


def copy_split_records(train_records, test_records):
    """将训练集/测试集图片复制到 split/ 目录。"""
    def copy_set(records, split_name):
        for r in records:
            src = PROJECT_ROOT / r["image_path"]
            if not src.exists():
                continue
            disease = r.get("disease", "未分类")
            comp = r.get("component", "其他")

            d_dir = SPLIT_DIR / split_name / disease
            d_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(d_dir / src.name))

            c_dir = SPLIT_DIR / split_name / comp
            c_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(c_dir / src.name))

    copy_set(train_records, "train")
    copy_set(test_records, "test")


def save_labels(records):
    """保存 labels.json 和 labels.csv。"""
    labels_json = {
        "total": len(records),
        "train_test_split": {
            "train_ratio": TRAIN_RATIO,
            "seed": RANDOM_SEED,
        },
        "disease_classes": list(DISEASE_KEYWORDS.keys()) + ["未分类"],
        "component_classes": list(COMPONENT_KEYWORDS.keys()) + ["其他"],
        "records": records,
    }
    json_path = DATASET_DIR / "labels.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(labels_json, f, ensure_ascii=False, indent=2)

    csv_path = DATASET_DIR / "labels.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "image_name", "source_doc", "component", "disease",
            "photo_type", "context", "image_path"
        ])
        for r in records:
            writer.writerow([
                r.get("image_name", ""),
                r.get("doc", ""),
                r.get("component", ""),
                r.get("disease", ""),
                r.get("photo_type", ""),
                r.get("context", "").replace("\n", " "),
                r.get("image_path", ""),
            ])


def main():
    ensure_dirs()

    all_records = []
    for doc_path in SOURCE_DOCS:
        records = extract_images_from_doc(doc_path)
        all_records.extend(records)

    print(f"\n[汇总] 共提取 {len(all_records)} 张图片")

    # 分类
    for r in all_records:
        context = r.get("context", "")
        r["disease"] = classify_disease(context)
        r["component"] = classify_component(context)
        if is_overview_photo(context):
            r["photo_type"] = "bridge_overview"
        elif r["disease"] != "未分类" or r["component"] != "其他":
            r["photo_type"] = "disease_closeup"
        else:
            r["photo_type"] = "unknown"

    # 统计
    disease_count = defaultdict(int)
    component_count = defaultdict(int)
    photo_type_count = defaultdict(int)
    for r in all_records:
        disease_count[r["disease"]] += 1
        component_count[r["component"]] += 1
        photo_type_count[r["photo_type"]] += 1

    print("\n[病害类型分布]")
    for k, v in sorted(disease_count.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\n[构件类型分布]")
    for k, v in sorted(component_count.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\n[照片类型分布]")
    for k, v in sorted(photo_type_count.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # 复制到分类目录
    copy_to_class_dirs(all_records)

    # 划分训练集/测试集
    train_records, test_records = split_train_test(all_records)
    copy_split_records(train_records, test_records)

    print(f"\n[数据集划分] 训练集: {len(train_records)}, 测试集: {len(test_records)}")

    # 保存标签
    save_labels(all_records)
    print(f"[保存] {DATASET_DIR / 'labels.json'}")
    print(f"[保存] {DATASET_DIR / 'labels.csv'}")

    print("\n[完成] 数据集提取与分类完成")


if __name__ == "__main__":
    main()
