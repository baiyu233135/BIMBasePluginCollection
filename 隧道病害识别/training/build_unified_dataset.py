# -*- coding: utf-8 -*-
"""合并桥梁人工标注集 + 隧道伪标注集，构建统一 YOLO 训练集。

- 桥梁: datasets(桥)/bridge_disease_merged_yolo 的 train+val 全量 873 张（不改动原数据）
- 隧道: datasets/tunnel_pseudo_yolo 141 张（伪标注）
- 8:2 分层划分：按每张图框数最多的类别分层（sklearn 不可用，手写分层抽样），
  同一图片只进一个 split；图片复制（非硬链接）。
- 输出: 桥梁病害识别/datasets/bridge_tunnel_unified_yolo/
"""
import os
import random
import shutil
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 隧道病害识别/
PROJ = os.path.dirname(ROOT)                                                # pythonplugin/
BRIDGE_DS = os.path.join(PROJ, '桥梁病害识别', 'datasets', 'bridge_disease_merged_yolo')
TUNNEL_DS = os.path.join(ROOT, 'datasets', 'tunnel_pseudo_yolo')
OUT_DIR = os.path.join(PROJ, '桥梁病害识别', 'datasets', 'bridge_tunnel_unified_yolo')

BRIDGE_NAMES = ['裂缝', '剥落', '露筋', '蜂窝麻面', '渗水', '锈蚀', '已修复']
VAL_RATIO = 0.2
SEED = 42

IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def read_label_counts(label_path):
    """返回 {cls_id: box_count}；文件不存在或空则返回空 dict"""
    counts = Counter()
    if os.path.exists(label_path):
        with open(label_path, encoding='utf-8') as fp:
            for line in fp:
                parts = line.split()
                if parts:
                    counts[int(parts[0])] += 1
    return counts


def collect_split(split):
    """从桥梁 merged 集的一个 split 收集样本"""
    items = []
    img_dir = os.path.join(BRIDGE_DS, 'images', split)
    for f in sorted(os.listdir(img_dir)):
        if os.path.splitext(f)[1].lower() not in IMG_EXTS:
            continue
        stem = os.path.splitext(f)[0]
        label_path = os.path.join(BRIDGE_DS, 'labels', split, stem + '.txt')
        counts = read_label_counts(label_path)
        items.append({'image': os.path.join(img_dir, f),
                      'label': label_path if os.path.exists(label_path) else None,
                      'counts': counts, 'source': 'bridge'})
    return items


def collect_tunnel():
    items = []
    img_dir = os.path.join(TUNNEL_DS, 'images')
    for f in sorted(os.listdir(img_dir)):
        if os.path.splitext(f)[1].lower() not in IMG_EXTS:
            continue
        stem = os.path.splitext(f)[0]
        label_path = os.path.join(TUNNEL_DS, 'labels', stem + '.txt')
        items.append({'image': os.path.join(img_dir, f), 'label': label_path,
                      'counts': read_label_counts(label_path), 'source': 'tunnel'})
    return items


def dominant_class(counts):
    """框数最多的类别（分层键）；空标签取 -1"""
    if not counts:
        return -1
    return max(sorted(counts), key=lambda c: (counts[c], -c))


def stratified_split(items, val_ratio, seed):
    """按 dominant class 分层，每层内随机 8:2"""
    rng = random.Random(seed)
    by_cls = defaultdict(list)
    for it in items:
        by_cls[dominant_class(it['counts'])].append(it)
    train, val = [], []
    for c in sorted(by_cls):
        layer = by_cls[c]
        rng.shuffle(layer)
        n_val = max(1, round(len(layer) * val_ratio)) if len(layer) > 1 else 0
        val.extend(layer[:n_val])
        train.extend(layer[n_val:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def write_split(name, items):
    img_out = os.path.join(OUT_DIR, 'images', name)
    lab_out = os.path.join(OUT_DIR, 'labels', name)
    os.makedirs(img_out, exist_ok=True)
    os.makedirs(lab_out, exist_ok=True)
    for it in items:
        fname = os.path.basename(it['image'])
        shutil.copy2(it['image'], os.path.join(img_out, fname))
        if it['label'] and os.path.exists(it['label']):
            shutil.copy2(it['label'], os.path.join(lab_out, os.path.splitext(fname)[0] + '.txt'))


def print_stats(name, items):
    box_counter = Counter()
    empty = 0
    src_counter = Counter()
    for it in items:
        src_counter[it['source']] += 1
        if not it['counts']:
            empty += 1
        box_counter.update(it['counts'])
    total_boxes = sum(box_counter.values())
    per_class = {BRIDGE_NAMES[c]: box_counter.get(c, 0) for c in range(len(BRIDGE_NAMES))}
    print(f'{name}: {len(items)} 张 (bridge {src_counter["bridge"]}, tunnel {src_counter["tunnel"]}), '
          f'{total_boxes} 框, 空标签 {empty} 张')
    print(f'  每类框数: {per_class}')
    return per_class


def main():
    bridge = collect_split('train') + collect_split('val')
    tunnel = collect_tunnel()
    print(f'桥梁: {len(bridge)} 张, 隧道伪标注: {len(tunnel)} 张')

    items = bridge + tunnel
    train, val = stratified_split(items, VAL_RATIO, SEED)
    print(f'划分: train {len(train)} / val {len(val)} (val 占比 {len(val)/len(items):.1%})')

    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    write_split('train', train)
    write_split('val', val)

    with open(os.path.join(OUT_DIR, 'data.yaml'), 'w', encoding='utf-8') as fp:
        fp.write(f'path: {os.path.abspath(OUT_DIR).replace(os.sep, "/")}\n')
        fp.write('train: images/train\nval: images/val\nnc: 7\nnames:\n')
        for n in BRIDGE_NAMES:
            fp.write(f'  - {n}\n')

    # ---- 校验 ----
    errors = []
    for split in ('train', 'val'):
        imgs = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(OUT_DIR, 'images', split))}
        labs = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(OUT_DIR, 'labels', split))}
        if imgs != labs:
            errors.append(f'{split}: images/labels 不配 (多图 {imgs - labs}, 多标签 {labs - imgs})')
        exts = {os.path.splitext(f)[1].lower() for f in os.listdir(os.path.join(OUT_DIR, 'images', split))}
        if not exts <= IMG_EXTS:
            errors.append(f'{split}: 异常文件 {exts - IMG_EXTS}')
    # 确认隧道 141 张全部落入统一集
    tunnel_stems = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(TUNNEL_DS, 'images'))}
    out_stems = set()
    for split in ('train', 'val'):
        out_stems |= {os.path.splitext(f)[0] for f in os.listdir(os.path.join(OUT_DIR, 'images', split))}
    missing = tunnel_stems - out_stems
    if missing:
        errors.append(f'隧道图片缺失 {len(missing)}: {sorted(missing)[:5]}')

    print('\n==== 统一集统计 ====')
    print_stats('train', train)
    print_stats('val', val)
    print(f'\ndata.yaml: {os.path.join(OUT_DIR, "data.yaml")}')
    if errors:
        print('校验失败:')
        for e in errors:
            print(' -', e)
        return 1
    print('校验通过: images/labels 一一配对, 无空标签混入, 隧道 141 张全部入集')
    return 0


if __name__ == '__main__':
    sys.exit(main())
