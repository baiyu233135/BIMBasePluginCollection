# -*- coding: utf-8 -*-
"""用桥梁病害 YOLO 模型为隧道照片生成伪标注（YOLO 格式）。

流程：
1. 读取 by_disease 下 141 张隧道照片 + labels.csv 的图片级报告标签；
2. 用桥梁模型 disease_yolov8n.pt 推理（CPU, conf=0.25, imgsz=640）；
3. 融合：模型检出框保留；若报告有标签则覆盖框类别（报告为权威图片级标签）；
   模型无检出但报告有标签 -> 生成覆盖全图 80% 的中心兜底框；
   无框无标签 -> 跳过并统计；
4. 输出 YOLO 格式到 datasets/tunnel_pseudo_yolo/，类别沿用桥梁 7 类顺序；
   每张图的来源信息写入 pseudo_label_report.json（YOLO 标签行内不允许注释）。
"""
import csv
import json
import os
import shutil
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 隧道病害识别/
PROJ = os.path.dirname(ROOT)                                                # pythonplugin/
MODEL_PATH = os.path.join(PROJ, '桥梁病害识别', 'models', 'disease_yolov8n.pt')
TUNNEL_DS = os.path.join(ROOT, 'datasets', 'tunnel_disease')
OUT_DIR = os.path.join(ROOT, 'datasets', 'tunnel_pseudo_yolo')

CONF = 0.25
IMGSZ = 640

BRIDGE_NAMES = ['裂缝', '剥落', '露筋', '蜂窝麻面', '渗水', '锈蚀', '已修复']
CLASS_INDEX = {n: i for i, n in enumerate(BRIDGE_NAMES)}

# 隧道报告标签 -> 桥梁 7 类（其他/未知一律归入剥落）
TUNNEL_TO_BRIDGE = {
    '裂缝': '裂缝',
    '渗水': '渗水',
    '剥落': '剥落',
}
FALLBACK_CLASS = '剥落'


def collect_images():
    """返回 {文件名: (绝对路径, 报告归一类)}"""
    by_disease = os.path.join(TUNNEL_DS, 'by_disease')
    path_by_name = {}
    for d in sorted(os.listdir(by_disease)):
        for f in sorted(os.listdir(os.path.join(by_disease, d))):
            path_by_name[f] = os.path.join(by_disease, d, f)
    report_by_name = {}
    with open(os.path.join(TUNNEL_DS, 'labels.csv'), encoding='utf-8-sig') as fp:
        for row in csv.DictReader(fp):
            report_by_name[os.path.basename(row['图片相对路径'].strip())] = row['病害归一类'].strip()
    items = []
    for name, path in sorted(path_by_name.items()):
        items.append((name, path, report_by_name.get(name)))
    return items


def main():
    from ultralytics import YOLO

    model = YOLO(MODEL_PATH)
    items = collect_images()
    print(f'隧道图片: {len(items)} 张, 模型: {MODEL_PATH}')

    os.makedirs(os.path.join(OUT_DIR, 'images'), exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, 'labels'), exist_ok=True)

    report = []
    skipped = []
    box_counter = Counter()       # 按最终类别统计输出框数
    src_counter = Counter()       # 框来源: model / report_override / report_fallback
    fallback_imgs = 0

    for name, path, report_label in items:
        stem = os.path.splitext(name)[0]
        result = model.predict(path, conf=CONF, imgsz=IMGSZ, device='cpu', verbose=False)[0]
        det = result.boxes
        boxes = []  # (cls_id, x_center, y_center, w, h) 归一化
        if det is not None and len(det) > 0:
            xywhn = det.xywhn.cpu().numpy()
            clss = det.cls.cpu().numpy().astype(int)
            for (x, y, w, h), c in zip(xywhn, clss):
                boxes.append([int(c), float(x), float(y), float(w), float(h)])

        mapped = TUNNEL_TO_BRIDGE.get(report_label, FALLBACK_CLASS) if report_label else None

        if boxes:
            if mapped is not None:
                for b in boxes:
                    b[0] = CLASS_INDEX[mapped]
                src = 'report_override'
            else:
                src = 'model'
            for b in boxes:
                box_counter[BRIDGE_NAMES[b[0]]] += 1
                src_counter[src] += 1
        elif mapped is not None:
            # 兜底：覆盖全图 80% 的中心框
            boxes.append([CLASS_INDEX[mapped], 0.5, 0.5, 0.8, 0.8])
            box_counter[mapped] += 1
            src_counter['report_fallback'] += 1
            fallback_imgs += 1
            src = 'report_fallback'
        else:
            skipped.append(name)
            report.append({'file': name, 'report_label': None, 'skipped': True,
                           'num_model_boxes': 0, 'num_output_boxes': 0, 'source': None})
            continue

        # 复制图片 + 写 YOLO 标签
        shutil.copy2(path, os.path.join(OUT_DIR, 'images', name))
        with open(os.path.join(OUT_DIR, 'labels', stem + '.txt'), 'w', encoding='utf-8') as fp:
            for c, x, y, w, h in boxes:
                fp.write(f'{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n')

        report.append({'file': name, 'report_label': report_label, 'mapped_class': mapped,
                       'skipped': False, 'num_model_boxes': int(0 if src == 'report_fallback' else len(boxes)),
                       'num_output_boxes': len(boxes), 'source': src})

    with open(os.path.join(OUT_DIR, 'pseudo_label_report.json'), 'w', encoding='utf-8') as fp:
        json.dump({'model': MODEL_PATH, 'conf': CONF, 'imgsz': IMGSZ,
                   'num_images': len(items), 'num_skipped': len(skipped),
                   'skipped_files': skipped, 'fallback_images': fallback_imgs,
                   'box_counts_by_class': dict(box_counter),
                   'box_counts_by_source': dict(src_counter),
                   'images': report}, fp, ensure_ascii=False, indent=2)

    # data.yaml（类别顺序与桥梁一致）
    with open(os.path.join(OUT_DIR, 'data.yaml'), 'w', encoding='utf-8') as fp:
        fp.write(f'path: {os.path.abspath(OUT_DIR).replace(os.sep, "/")}\n')
        fp.write('train: images\nval: images\nnc: 7\nnames:\n')
        for n in BRIDGE_NAMES:
            fp.write(f'  - {n}\n')

    print(f'完成: {len(items) - len(skipped)} 张有标注, 跳过 {len(skipped)} 张, 兜底框图片 {fallback_imgs} 张')
    print('输出框类别分布:', dict(box_counter))
    print('框来源分布:', dict(src_counter))
    if skipped:
        print('跳过:', skipped)


if __name__ == '__main__':
    sys.exit(main())
