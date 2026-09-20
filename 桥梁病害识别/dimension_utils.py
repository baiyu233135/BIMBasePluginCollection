# -*- coding: utf-8 -*-
"""
损伤几何尺寸量化 — 纯计算模块（不依赖 PyQt5 / pyp3d，可单独导入测试）

标定方式：参照物框选标定。用户在照片上拖框覆盖已知实际长度的参照物，
比例 scale = 参照物实际长度(mm) / 参照物框像素长边，对该照片所有病害框生效。

尺寸计算说明：
- length_mm / width_mm = bbox 像素长/宽边 × scale
- area_mm2 = bbox 像素宽 × 像素高 × scale²
  注意：面积为 bbox 外接矩形面积，真实病害面积通常偏小，
  报告需注明“外接矩形估算，适用于近似矩形病害的对比”。

误差来源：照片镜头畸变、参照物与病害不在同一景深（透视缩放差异）。
"""

from typing import Optional, Tuple


def calc_scale(ref_length_mm: float, bbox: Tuple[float, float, float, float]) -> Optional[float]:
    """根据参照物框计算照片像素比例。

    Args:
        ref_length_mm: 参照物实际长度（mm，>0）
        bbox: 参照物框 (x1, y1, x2, y2)，照片像素坐标

    Returns:
        scale（mm/px，即每像素对应的实际毫米数），取框长边计算；
        输入非法（长度<=0、框退化）时返回 None。
    """
    try:
        ref = float(ref_length_mm)
        x1, y1, x2, y2 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if ref <= 0:
        return None
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    long_edge = max(w, h)
    if long_edge <= 0:
        return None
    return ref / long_edge


def box_dimensions(bbox, scale: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """计算病害框的几何尺寸。

    Args:
        bbox: 病害框 (x1, y1, x2, y2)，照片像素坐标
        scale: 该照片的像素比例（mm/px，calc_scale 的返回值）；None 表示未标定

    Returns:
        (length_mm, width_mm, area_mm2)；
        未标定（scale 为 None）或框退化时三个值均为 None。
        area_mm2 为外接矩形面积（宽×高×scale²），真实病害面积偏小。
    """
    if scale is None:
        return None, None, None
    try:
        s = float(scale)
        x1, y1, x2, y2 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None, None, None
    if s <= 0:
        return None, None, None
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    if w <= 0 or h <= 0:
        return None, None, None
    length_mm = max(w, h) * s
    width_mm = min(w, h) * s
    area_mm2 = w * h * s * s   # 外接矩形面积，真实病害面积偏小
    return length_mm, width_mm, area_mm2
