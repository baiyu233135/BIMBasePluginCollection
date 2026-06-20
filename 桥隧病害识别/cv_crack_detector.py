# -*- coding: utf-8 -*-
"""
传统计算机视觉裂缝检测 — OpenCV fallback

当YOLO专用病害模型不可用时，使用图像处理方法检测裂缝区域。
基于：灰度转换 → 高斯模糊 → Canny边缘检测 → 轮廓筛选

适用于：混凝土表面裂缝、墙体裂缝等线性病害
"""

import os
import cv2
import numpy as np
from typing import List, Tuple
from disease_detector import DiseaseResult


def detect_cracks_cv(image_path: str, min_length: int = 50, 
                       min_area: int = 100) -> List[DiseaseResult]:
    """
    使用传统CV方法检测图片中的裂缝。
    
    Args:
        image_path: 图片路径
        min_length: 裂缝最小长度（像素）
        min_area: 裂缝最小面积（像素）
    
    Returns:
        DiseaseResult列表（ class_name="裂缝" ）
    """
    img = cv2.imread(image_path)
    if img is None:
        return []
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 高斯模糊去噪
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Canny边缘检测
    edges = cv2.Canny(blurred, 50, 150)
    
    # 形态学操作：连接断裂的边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 查找轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    results = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        
        # 计算轮廓长度
        length = cv2.arcLength(cnt, False)
        if length < min_length:
            continue
        
        # 计算外接矩形
        x, y, bw, bh = cv2.boundingRect(cnt)
        
        # 长宽比筛选：裂缝通常是细长的
        aspect_ratio = max(bw, bh) / (min(bw, bh) + 1e-6)
        if aspect_ratio < 2.0:  # 太胖的不是裂缝
            continue
        
        # 膨胀bbox留边距
        margin = 5
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(w, x + bw + margin)
        y2 = min(h, y + bh + margin)
        
        # 排除贴边的检测框（通常是图片边缘伪影）
        edge_margin = 10
        if x1 <= edge_margin or y1 <= edge_margin or x2 >= w - edge_margin or y2 >= h - edge_margin:
            continue
        
        # 模拟置信度：基于长宽比和面积综合打分
        conf = min(0.95, 0.5 + 0.1 * aspect_ratio + 0.001 * area)
        conf = min(conf, 0.95)
        
        results.append(DiseaseResult(
            class_name="裂缝",
            confidence=round(conf, 3),
            bbox=(x1, y1, x2, y2),
            image_width=w,
            image_height=h,
        ))
    
    # 合并重叠的bbox（NMS简化版）
    results = _merge_overlapping_boxes(results, overlap_thresh=0.3)
    
    # 限制最大检测数量
    results = sorted(results, key=lambda r: r.confidence, reverse=True)[:20]
    
    return results


def _merge_overlapping_boxes(results: List[DiseaseResult], 
                              overlap_thresh: float = 0.3) -> List[DiseaseResult]:
    """简单的重叠框合并"""
    if not results:
        return results
    
    merged = []
    used = set()
    
    for i, r1 in enumerate(results):
        if i in used:
            continue
        
        x1, y1, x2, y2 = r1.bbox
        area1 = (x2 - x1) * (y2 - y1)
        
        # 找所有与r1重叠的框
        group = [r1]
        for j, r2 in enumerate(results[i+1:], i+1):
            if j in used:
                continue
            xx1, yy1, xx2, yy2 = r2.bbox
            
            # 计算IoU
            ix1, iy1 = max(x1, xx1), max(y1, yy1)
            ix2, iy2 = min(x2, xx2), min(y2, yy2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area2 = (xx2 - xx1) * (yy2 - yy1)
            union = area1 + area2 - inter
            iou = inter / union if union > 0 else 0
            
            if iou > overlap_thresh:
                group.append(r2)
                used.add(j)
        
        # 合并为一组的最大bbox
        if len(group) > 1:
            all_x1 = [r.bbox[0] for r in group]
            all_y1 = [r.bbox[1] for r in group]
            all_x2 = [r.bbox[2] for r in group]
            all_y2 = [r.bbox[3] for r in group]
            merged_bbox = (min(all_x1), min(all_y1), max(all_x2), max(all_y2))
            max_conf = max(r.confidence for r in group)
            merged.append(DiseaseResult(
                class_name="裂缝",
                confidence=max_conf,
                bbox=merged_bbox,
                image_width=r1.image_width,
                image_height=r1.image_height,
            ))
        else:
            merged.append(r1)
    
    return merged


def draw_cv_results(image_path: str, results: List[DiseaseResult],
                    output_path: str = None) -> str:
    """
    在图片上绘制CV检测结果（红色框+标签）。
    
    Returns:
        输出图片路径
    """
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    for r in results:
        x1, y1, x2, y2 = r.bbox
        # 红色框
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        # 标签
        label = f"{r.class_name} {r.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(img, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 0, 255), -1)
        cv2.putText(img, label, (x1 + 2, y1 - 4), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    if output_path is None:
        import tempfile
        base = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(tempfile.gettempdir(), f"{base}_cv_detected.jpg")
    
    cv2.imwrite(output_path, img)
    return output_path
