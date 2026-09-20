# -*- coding: utf-8 -*-
"""
传统计算机视觉异常区域检测（隧道版）

针对隧道衬砌、洞门、检修道等混凝土构件照片，在不依赖深度学习模型的情况下，
融合多种图像处理策略自动圈出异常区域（裂缝、渗水、剥落、污渍等）。

输出统一为 class_name="异常区域"，不区分具体病害类型。
"""

import os
import cv2
import numpy as np
from typing import List, Tuple, Optional
from disease_detector import DiseaseResult


# 默认参数（针对隧道混凝土病害照片调优）
DEFAULT_MIN_AREA = 120
DEFAULT_MAX_AREA_RATIO = 0.65
DEFAULT_EDGE_MARGIN = 3
DEFAULT_NMS_IOU = 0.25
DEFAULT_MAX_BOXES = 10


def _imread_unicode(path: str):
    """兼容中文路径的 cv2.imread"""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _detect_sky_mask(hsv: np.ndarray, v: np.ndarray, s: np.ndarray) -> np.ndarray:
    """
    粗略检测天空/背景区域，用于减少误检。
    天空通常具有高亮度、低饱和、偏蓝/白的特点。
    """
    h, w = hsv.shape[:2]
    h_ch = hsv[:, :, 0].astype(np.float32)
    s_ch = s.astype(np.float32)
    v_ch = v.astype(np.float32)

    mask = np.zeros((h, w), dtype=np.uint8)

    # 高亮低饱和：白色/浅灰天空
    bright_sky = (v_ch > 180) & (s_ch < 50)
    # 偏蓝天空
    blue_sky = (h_ch > 90) & (h_ch < 130) & (s_ch > 20) & (s_ch < 100) & (v_ch > 100)

    mask[bright_sky | blue_sky] = 255

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return mask


def _method_crack(gray: np.ndarray) -> np.ndarray:
    """黑帽变换：检测细长裂缝"""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    _, mask = cv2.threshold(blackhat, 8, 255, cv2.THRESH_BINARY)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    return mask


def _method_adaptive(gray: np.ndarray) -> np.ndarray:
    """多尺度自适应阈值：检测不同大小的暗区"""
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    combined = np.zeros((h, w), dtype=np.uint8)
    for bs, c in [(31, 5), (51, 10), (71, 15)]:
        bs = bs if bs % 2 == 1 else bs + 1
        mask = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, bs, c
        )
        combined = cv2.bitwise_or(combined, mask)
    return combined


def _method_kmeans(img: np.ndarray) -> np.ndarray:
    """K-Means 颜色聚类：检测颜色明显异常的区域（最暗/最亮类）"""
    h, w = img.shape[:2]
    scale = 0.5
    small = cv2.resize(img, None, fx=scale, fy=scale)
    sh, sw = small.shape[:2]
    pixels = small.reshape((-1, 3)).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    lab_centers = cv2.cvtColor(
        centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB
    ).reshape(-1, 3)
    lum = lab_centers[:, 0]
    dark_class = int(np.argmin(lum))
    bright_class = int(np.argmax(lum))

    mask_dark = (labels.reshape(sh, sw) == dark_class).astype(np.uint8) * 255
    mask_bright = (labels.reshape(sh, sw) == bright_class).astype(np.uint8) * 255
    mask_small = cv2.bitwise_or(mask_dark, mask_bright)
    mask = cv2.resize(mask_small, (w, h), interpolation=cv2.INTER_NEAREST)
    return mask


def _method_texture(gray: np.ndarray) -> np.ndarray:
    """局部纹理差异：检测剥落露骨料等粗糙区域"""
    h, w = gray.shape
    mean = cv2.blur(gray.astype(np.float32), (15, 15))
    mean_sq = cv2.blur(gray.astype(np.float32) ** 2, (15, 15))
    std = np.sqrt(np.maximum(mean_sq - mean ** 2, 0))

    local_mean_std = cv2.blur(std, (41, 41))
    diff = std - local_mean_std

    mask = np.zeros((h, w), dtype=np.uint8)
    mask[diff > np.percentile(diff, 78)] = 255
    return mask


def _method_edge(gray: np.ndarray) -> np.ndarray:
    """边缘密度：检测有明显边界的病害区域"""
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 120)
    edge_density = cv2.boxFilter(edges.astype(np.float32), -1, (25, 25), normalize=True)

    mask = np.zeros((h, w), dtype=np.uint8)
    mask[edge_density > np.percentile(edge_density, 88)] = 255
    return mask


def _mask_to_boxes(mask: np.ndarray, h: int, w: int,
                   min_area: int = DEFAULT_MIN_AREA,
                   max_area_ratio: float = DEFAULT_MAX_AREA_RATIO,
                   edge_margin: int = DEFAULT_EDGE_MARGIN,
                   filter_aspect_ratio: bool = True) -> List[Tuple]:
    """从二值 mask 中提取检测框"""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        bbox_area = bw * bh
        if bbox_area > w * h * max_area_ratio:
            continue

        # 排除贴边伪影
        if (x <= edge_margin or y <= edge_margin or
                x + bw >= w - edge_margin or y + bh >= h - edge_margin):
            continue

        # 过滤极端长宽比（细长文字笔画等）
        if filter_aspect_ratio:
            ar = max(bw, bh) / (min(bw, bh) + 1e-6)
            if ar > 8.0:
                continue

        conf = min(0.95, 0.45 + 0.001 * area)
        boxes.append((x, y, x + bw, y + bh, conf))

    return boxes


def _nms(boxes: List[Tuple], iou_thresh: float = DEFAULT_NMS_IOU) -> List[Tuple]:
    """简化 NMS 合并重叠检测框"""
    if not boxes:
        return boxes

    boxes = sorted(boxes, key=lambda b: b[4], reverse=True)
    kept = []
    used = set()

    for i, b1 in enumerate(boxes):
        if i in used:
            continue
        x1, y1, x2, y2, c1 = b1
        kept.append(b1)

        for j, b2 in enumerate(boxes[i + 1:], i + 1):
            if j in used:
                continue
            xx1, yy1, xx2, yy2, c2 = b2
            ix1, iy1 = max(x1, xx1), max(y1, yy1)
            ix2, iy2 = min(x2, xx2), min(y2, yy2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = (x2 - x1) * (y2 - y1) + (xx2 - xx1) * (yy2 - yy1) - inter
            iou = inter / (union + 1e-6)
            if iou > iou_thresh:
                used.add(j)

    return kept


def detect_anomalies_cv(
    image_path: str,
    min_area: int = DEFAULT_MIN_AREA,
    max_area_ratio: float = DEFAULT_MAX_AREA_RATIO,
    edge_margin: int = DEFAULT_EDGE_MARGIN,
    nms_iou: float = DEFAULT_NMS_IOU,
    max_boxes: int = DEFAULT_MAX_BOXES,
) -> List[DiseaseResult]:
    """
    使用传统 CV 方法检测图片中的异常区域。

    融合策略：
    - 黑帽变换：细长裂缝
    - 多尺度自适应阈值：不同大小的暗区
    - K-Means 聚类：颜色异常类
    - 局部纹理差异：剥落露骨料等粗糙区域
    - 边缘密度：有明显边界的病害
    - 天空/背景掩码：减少天空误检

    Args:
        image_path: 图片文件路径（支持中文路径）
        min_area: 最小轮廓面积
        max_area_ratio: 最大外接矩形占全图面积比例
        edge_margin: 贴边检测框剔除边距（像素）
        nms_iou: 重叠框合并 IoU 阈值
        max_boxes: 最多返回的检测框数量

    Returns:
        DiseaseResult 列表，class_name 均为 "异常区域"
    """
    img = _imread_unicode(image_path)
    if img is None:
        return []

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    l_channel = lab[:, :, 0]
    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    # 天空/背景掩码
    sky_mask = _detect_sky_mask(hsv, v_channel, s_channel)
    not_sky = cv2.bitwise_not(sky_mask)

    # 各方法检测，并限制在非天空区域
    crack_mask = cv2.bitwise_and(_method_crack(gray), not_sky)
    adaptive_mask = cv2.bitwise_and(_method_adaptive(gray), not_sky)
    kmeans_mask = cv2.bitwise_and(_method_kmeans(img), not_sky)
    texture_mask = cv2.bitwise_and(_method_texture(gray), not_sky)
    edge_mask = cv2.bitwise_and(_method_edge(gray), not_sky)

    # 合并所有 mask
    combined = np.zeros((h, w), dtype=np.uint8)
    combined = cv2.bitwise_or(combined, crack_mask)
    combined = cv2.bitwise_or(combined, adaptive_mask)
    combined = cv2.bitwise_or(combined, kmeans_mask)
    combined = cv2.bitwise_or(combined, texture_mask)
    combined = cv2.bitwise_or(combined, edge_mask)

    # 分别提取框（纹理/边缘方法用更大的最小面积，减少噪声）
    boxes_crack = _mask_to_boxes(crack_mask, h, w, min_area=min_area,
                                  max_area_ratio=max_area_ratio,
                                  edge_margin=edge_margin)
    boxes_adaptive = _mask_to_boxes(adaptive_mask, h, w, min_area=min_area,
                                     max_area_ratio=max_area_ratio,
                                     edge_margin=edge_margin)
    boxes_kmeans = _mask_to_boxes(kmeans_mask, h, w, min_area=min_area * 1.5,
                                   max_area_ratio=max_area_ratio,
                                   edge_margin=edge_margin)
    boxes_texture = _mask_to_boxes(texture_mask, h, w, min_area=min_area * 2.5,
                                    max_area_ratio=max_area_ratio,
                                    edge_margin=edge_margin)
    boxes_edge = _mask_to_boxes(edge_mask, h, w, min_area=min_area * 2.0,
                                 max_area_ratio=max_area_ratio,
                                 edge_margin=edge_margin)

    all_boxes = boxes_crack + boxes_adaptive + boxes_kmeans + boxes_texture + boxes_edge

    # 过滤极端长宽比
    filtered = []
    for b in all_boxes:
        x1, y1, x2, y2, c = b
        bw, bh = x2 - x1, y2 - y1
        ar = max(bw, bh) / (min(bw, bh) + 1e-6)
        if ar > 8.0:
            continue
        filtered.append(b)

    # NMS
    merged = _nms(filtered, iou_thresh=nms_iou)

    # 优先保留面积较大的框，限制数量
    merged = sorted(merged, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    merged = merged[:max_boxes]

    # 按置信度排序
    merged = sorted(merged, key=lambda b: b[4], reverse=True)

    results = []
    for x1, y1, x2, y2, conf in merged:
        results.append(DiseaseResult(
            class_name="异常区域",
            confidence=round(conf, 3),
            bbox=(x1, y1, x2, y2),
            image_width=w,
            image_height=h,
        ))

    return results


def draw_anomaly_results(
    image_path: str,
    results: List[DiseaseResult],
    output_path: Optional[str] = None,
    color: Tuple[int, int, int] = (255, 0, 0),
    thickness: int = 3,
) -> Optional[str]:
    """
    在原图上绘制异常区域检测框（使用 PIL 支持中文标签）。

    Args:
        image_path: 原图路径
        results: detect_anomalies_cv 返回的结果列表
        output_path: 输出路径，None 则保存到临时目录
        color: 框颜色（RGB），默认红色
        thickness: 线宽

    Returns:
        输出图片路径，失败返回 None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    try:
        img = Image.open(image_path).convert('RGB')
    except Exception:
        return None

    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("simhei.ttf", 18)
    except Exception:
        try:
            font = ImageFont.truetype("msyh.ttf", 18)
        except Exception:
            font = ImageFont.load_default()

    for idx, r in enumerate(results, 1):
        x1, y1, x2, y2 = r.bbox
        label = f"异常区域 {r.confidence:.2f}"

        for t in range(thickness):
            draw.rectangle([x1 - t, y1 - t, x2 + t, y2 + t], outline=color, width=1)

        bbox_text = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox_text[2] - bbox_text[0], bbox_text[3] - bbox_text[1]
        draw.rectangle([x1, y1 - th - 6, x1 + tw + 6, y1], fill=color)
        draw.text((x1 + 3, y1 - th - 3), label, fill=(255, 255, 255), font=font)

    if output_path is None:
        import tempfile
        base = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(tempfile.gettempdir(), f"{base}_anomaly.jpg")

    try:
        img.save(output_path, quality=95)
        return output_path
    except Exception:
        return None
