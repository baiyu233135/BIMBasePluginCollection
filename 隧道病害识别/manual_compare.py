# -*- coding: utf-8 -*-
"""
人工标注 ↔ 自动识别 对照逻辑（隧道病害识别）

纯逻辑模块，无 Qt 依赖，便于独立测试：
- load_manual_labels: 按 basename 在 YOLO 标注集（images/ + labels/ + data.yaml）
  中查找同名图片与标签，把归一化框换算为像素框；
- match_boxes: IoU 贪心匹配（按 IoU 降序），得出 识别正确/漏检/误检；
- compare_stats: 汇总对照统计（人工标注数/识别一致/漏检/误检/一致率）。

坐标约定与 image_box_widget 一致：照片左上角为原点 (0,0)，单位像素。
"""

import os

# data.yaml 读不到时的类别回退（顺序以 data.yaml names 为准）
DEFAULT_CLASS_NAMES = ["裂缝", "渗水", "剥落", "其他"]

# 标注集内查找图片时尝试的扩展名
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff",
               ".JPG", ".JPEG", ".PNG", ".BMP", ".TIFF")


def _manual_log(msg):
    """写 [MANUAL] 前缀日志到 tunnel_disease_debug.log（失败静默）。"""
    try:
        from datetime import datetime
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "tunnel_disease_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [MANUAL] {msg}\n")
    except Exception:
        pass


def _image_size(image_path):
    """返回 (W, H)；PIL/cv2 均不可用时返回 None。"""
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            return im.size
    except Exception:
        pass
    try:
        import cv2
        im = cv2.imread(image_path)
        if im is not None:
            h, w = im.shape[:2]
            return int(w), int(h)
    except Exception:
        pass
    return None


def _parse_data_yaml_names(yaml_path):
    """解析 data.yaml 的 names（id→类别名）。优先 PyYAML，失败回退简单文本解析。"""
    if not os.path.isfile(yaml_path):
        return list(DEFAULT_CLASS_NAMES)
    # 优先 PyYAML
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        names = data.get("names") if isinstance(data, dict) else None
        if isinstance(names, (list, tuple)) and names:
            return [str(n) for n in names]
        if isinstance(names, dict) and names:
            try:
                ordered = sorted(names.items(), key=lambda kv: int(kv[0]))
            except Exception:
                ordered = list(names.items())
            return [str(v) for _, v in ordered]
    except Exception:
        pass
    # 文本兜底：找 "names:" 行，其后 "- 名称" 列表行；或 "names: [a, b]" 行内列表
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        names = []
        in_names = False
        for line in lines:
            s = line.strip()
            if in_names:
                if s.startswith("- "):
                    names.append(s[2:].strip().strip("\"'"))
                elif s and not s.startswith("#"):
                    break
            elif s.startswith("names:"):
                rest = s[len("names:"):].strip()
                if rest.startswith("["):
                    inner = rest.strip("[]")
                    names = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
                    return names or list(DEFAULT_CLASS_NAMES)
                in_names = True
        if names:
            return names
    except Exception as e:
        _manual_log(f"data.yaml 文本解析失败: {e}")
    return list(DEFAULT_CLASS_NAMES)


def load_manual_labels(image_path, anno_dir):
    """加载与 image_path 同名的人工标注框（照片像素坐标）。

    Args:
        image_path: 用户导入的隧道病害照片路径（只用 basename 匹配）
        anno_dir:   YOLO 标注集目录，内含 images/、labels/、data.yaml

    Returns:
        [(x1, y1, x2, y2, class_name), ...]；无同名图片/标签或解析出 0 个框时返回 None。
    """
    try:
        if not image_path or not anno_dir:
            return None
        base = os.path.splitext(os.path.basename(image_path))[0]

        # 1. 在 anno_dir/images 找同名图片（需要其像素尺寸做归一化换算）
        images_dir = os.path.join(anno_dir, "images")
        labeled_image = None
        for ext in _IMAGE_EXTS:
            cand = os.path.join(images_dir, base + ext)
            if os.path.isfile(cand):
                labeled_image = cand
                break
        if labeled_image is None:
            return None
        size = _image_size(labeled_image)
        if not size:
            _manual_log(f"无法读取标注图片尺寸: {labeled_image}")
            return None
        W, H = int(size[0]), int(size[1])
        if W <= 0 or H <= 0:
            return None

        # 2. 同名标签文件
        label_file = os.path.join(anno_dir, "labels", base + ".txt")
        if not os.path.isfile(label_file):
            return None

        names = _parse_data_yaml_names(os.path.join(anno_dir, "data.yaml"))

        boxes = []
        with open(label_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 5:
                    continue
                try:
                    cls = int(float(parts[0]))
                    cx, cy, bw, bh = (float(parts[1]), float(parts[2]),
                                      float(parts[3]), float(parts[4]))
                except (ValueError, IndexError):
                    continue
                x1 = (cx - bw / 2.0) * W
                y1 = (cy - bh / 2.0) * H
                x2 = (cx + bw / 2.0) * W
                y2 = (cy + bh / 2.0) * H
                # 裁剪到图片范围内
                x1 = max(0.0, min(float(W), x1))
                y1 = max(0.0, min(float(H), y1))
                x2 = max(0.0, min(float(W), x2))
                y2 = max(0.0, min(float(H), y2))
                if x2 - x1 < 1 or y2 - y1 < 1:
                    continue
                class_name = names[cls] if 0 <= cls < len(names) else "类别%d" % cls
                boxes.append((int(x1), int(y1), int(x2), int(y2), class_name))

        if not boxes:
            return None
        return boxes
    except Exception as e:
        _manual_log(f"load_manual_labels 异常 ({os.path.basename(str(image_path))}): {e}")
        return None


def _iou(box_a, box_b):
    """两个框 (x1,y1,x2,y2,...) 的交并比。"""
    ax1, ay1, ax2, ay2 = box_a[:4]
    bx1, by1, bx2, by2 = box_b[:4]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def match_boxes(detections, manuals, iou_thresh=0.5):
    """IoU 贪心匹配（按 IoU 降序，一对一）。

    Args:
        detections: [(x1,y1,x2,y2,...), ...] 自动识别/手动画出的框
        manuals:    [(x1,y1,x2,y2,...), ...] 人工标注框
        iou_thresh: 判定为同一目标的 IoU 阈值

    Returns:
        (det_matches, manual_matches)
        det_matches[i]    = 与第 i 条 detection 匹配的人工标注下标，未匹配为 None
        manual_matches[j] = 与第 j 条 manual 匹配的 detection 下标，未匹配为 None
    """
    pairs = []
    for di, d in enumerate(detections):
        for mi, m in enumerate(manuals):
            iou = _iou(d, m)
            if iou >= iou_thresh:
                pairs.append((iou, di, mi))
    pairs.sort(key=lambda x: -x[0])

    det_matches = [None] * len(detections)
    manual_matches = [None] * len(manuals)
    used_d, used_m = set(), set()
    for _iou_val, di, mi in pairs:
        if di in used_d or mi in used_m:
            continue
        det_matches[di] = mi
        manual_matches[mi] = di
        used_d.add(di)
        used_m.add(mi)
    return det_matches, manual_matches


def compare_stats(manuals, detections, iou_thresh=0.5,
                  det_matches=None, manual_matches=None):
    """对照统计：人工标注数 / 识别一致 / 漏检 / 误检 / 一致率。

    已用 match_boxes 算过匹配时可传入 det_matches/manual_matches 复用结果。

    Returns:
        dict(manual, detection, matched, missed, false_pos, rate)
        rate = matched / manual（无人工标注时为 0.0）
    """
    if det_matches is None or manual_matches is None:
        det_matches, manual_matches = match_boxes(detections, manuals, iou_thresh)

    matched = sum(1 for m in det_matches if m is not None)
    missed = sum(1 for m in manual_matches if m is None)
    false_pos = sum(1 for m in det_matches if m is None)
    total_manual = len(manuals)
    rate = (matched / total_manual) if total_manual else 0.0
    return {
        "manual": total_manual,
        "detection": len(detections),
        "matched": matched,
        "missed": missed,
        "false_pos": false_pos,
        "rate": rate,
    }
