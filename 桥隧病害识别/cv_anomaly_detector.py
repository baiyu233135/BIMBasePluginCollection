# -*- coding: utf-8 -*-
"""
传统计算机视觉异常区域检测

针对 T 梁等混凝土构件照片，在不依赖深度学习模型的情况下，
使用黑帽变换 + 多尺度自适应阈值 + 形态学处理，自动圈出图像中的
异常区域（裂缝、渗水、污渍、剥落等）。

输出统一为 class_name="异常区域"，不区分具体病害类型。
"""

import os
import cv2
import numpy as np
from typing import List, Tuple, Optional
from disease_detector import DiseaseResult


# 默认参数（针对 554×378 级别的 T 梁照片调优）
DEFAULT_MIN_AREA = 80
DEFAULT_MAX_AREA_RATIO = 0.65
DEFAULT_EDGE_MARGIN = 3
DEFAULT_BLACKHAT_KERNEL = 15
DEFAULT_BLACKHAT_THRESH = 10
DEFAULT_ADAPTIVE_BLOCK_SIZES = [31, 51, 71]
DEFAULT_ADAPTIVE_C_VALUES = [5, 10, 15]
DEFAULT_CLOSE_KERNEL = 7
DEFAULT_CLOSE_ITERATIONS = 2
DEFAULT_NMS_IOU = 0.25


def _imread_unicode(path: str):
    """兼容中文路径的 cv2.imread"""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite_unicode(path: str, img: np.ndarray) -> bool:
    """兼容中文路径的 cv2.imwrite"""
    ext = os.path.splitext(path)[1].lstrip('.') or 'jpg'
    ok, buf = cv2.imencode(f".{ext}", img)
    if ok:
        buf.tofile(path)
        return True
    return False


def _merge_overlapping_boxes(results: List[DiseaseResult],
                             overlap_thresh: float = 0.25) -> List[DiseaseResult]:
    """简化 NMS 合并重叠检测框"""
    if not results:
        return results

    # 按置信度/面积排序
    sorted_results = sorted(results, key=lambda r: r.confidence, reverse=True)
    merged = []
    used = set()

    for i, r1 in enumerate(sorted_results):
        if i in used:
            continue
        x1, y1, x2, y2 = r1.bbox
        area1 = (x2 - x1) * (y2 - y1)
        group = [r1]

        for j, r2 in enumerate(sorted_results[i + 1:], i + 1):
            if j in used:
                continue
            xx1, yy1, xx2, yy2 = r2.bbox
            ix1, iy1 = max(x1, xx1), max(y1, yy1)
            ix2, iy2 = min(x2, xx2), min(y2, yy2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area2 = (xx2 - xx1) * (yy2 - yy1)
            union = area1 + area2 - inter
            iou = inter / union if union > 0 else 0
            if iou > overlap_thresh:
                group.append(r2)
                used.add(j)

        # 合并为最大外接矩形
        all_x1 = [r.bbox[0] for r in group]
        all_y1 = [r.bbox[1] for r in group]
        all_x2 = [r.bbox[2] for r in group]
        all_y2 = [r.bbox[3] for r in group]
        merged_bbox = (min(all_x1), min(all_y1), max(all_x2), max(all_y2))
        max_conf = max(r.confidence for r in group)

        merged.append(DiseaseResult(
            class_name="异常区域",
            confidence=max_conf,
            bbox=merged_bbox,
            image_width=r1.image_width,
            image_height=r1.image_height,
        ))

    return merged


def detect_anomalies_cv(
    image_path: str,
    min_area: int = DEFAULT_MIN_AREA,
    max_area_ratio: float = DEFAULT_MAX_AREA_RATIO,
    edge_margin: int = DEFAULT_EDGE_MARGIN,
    blackhat_kernel: int = DEFAULT_BLACKHAT_KERNEL,
    blackhat_thresh: int = DEFAULT_BLACKHAT_THRESH,
    adaptive_block_sizes: List[int] = None,
    adaptive_c_values: List[int] = None,
    close_kernel: int = DEFAULT_CLOSE_KERNEL,
    close_iterations: int = DEFAULT_CLOSE_ITERATIONS,
    nms_iou: float = DEFAULT_NMS_IOU,
) -> List[DiseaseResult]:
    """
    使用传统 CV 方法检测图片中的异常区域。

    Args:
        image_path: 图片文件路径（支持中文路径）
        min_area: 最小轮廓面积，小于此值的噪声会被过滤
        max_area_ratio: 最大外接矩形占全图面积比例，避免整图误检
        edge_margin: 贴边检测框剔除边距（像素）
        blackhat_kernel: 黑帽变换结构元素大小，越大对宽裂缝越敏感
        blackhat_thresh: 黑帽结果二值化阈值
        adaptive_block_sizes: 自适应阈值块大小列表
        adaptive_c_values: 自适应阈值 C 值列表
        close_kernel: 形态学闭运算核大小
        close_iterations: 形态学闭运算迭代次数
        nms_iou: 重叠框合并 IoU 阈值

    Returns:
        DiseaseResult 列表，class_name 均为 "异常区域"
    """
    if adaptive_block_sizes is None:
        adaptive_block_sizes = DEFAULT_ADAPTIVE_BLOCK_SIZES
    if adaptive_c_values is None:
        adaptive_c_values = DEFAULT_ADAPTIVE_C_VALUES

    img = _imread_unicode(image_path)
    if img is None:
        return []

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1) 黑帽变换：增强比周围暗的细长结构（裂缝）
    bh_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (blackhat_kernel, blackhat_kernel)
    )
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, bh_kernel)
    _, crack_mask = cv2.threshold(blackhat, blackhat_thresh, 255, cv2.THRESH_BINARY)

    # 2) 多尺度自适应阈值：检测大面积暗区（渗水、污渍、剥落）
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    dark_mask = None
    for bs, c in zip(adaptive_block_sizes, adaptive_c_values):
        # 块大小必须是奇数
        bs = bs if bs % 2 == 1 else bs + 1
        mask = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            bs, c
        )
        if dark_mask is None:
            dark_mask = mask
        else:
            dark_mask = cv2.bitwise_or(dark_mask, mask)

    # 3) 合并裂缝与暗区 mask
    combined = cv2.bitwise_or(crack_mask, dark_mask)

    # 4) 形态学闭运算连接断裂区域
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_kernel, close_kernel))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, close_k, iterations=close_iterations)

    # 5) 轮廓提取与过滤
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    results = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        bbox_area = bw * bh
        if bbox_area > w * h * max_area_ratio:
            continue

        # 剔除贴边伪影
        if (x <= edge_margin or y <= edge_margin or
                x + bw >= w - edge_margin or y + bh >= h - edge_margin):
            continue

        # 置信度：基于面积和 bbox 占比综合打分
        bbox_ratio = bbox_area / (w * h)
        conf = min(0.95, 0.45 + 0.001 * area + 2.0 * bbox_ratio)

        results.append(DiseaseResult(
            class_name="异常区域",
            confidence=round(conf, 3),
            bbox=(x, y, x + bw, y + bh),
            image_width=w,
            image_height=h,
        ))

    # 6) 合并重叠框
    results = _merge_overlapping_boxes(results, overlap_thresh=nms_iou)

    # 按置信度排序
    results = sorted(results, key=lambda r: r.confidence, reverse=True)
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

    # 尝试加载中文字体
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

        # 画框
        for t in range(thickness):
            draw.rectangle([x1 - t, y1 - t, x2 + t, y2 + t], outline=color, width=1)

        # 标签背景
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
