# -*- coding: utf-8 -*-
"""
PDF矢量导入处理器 - v1.0

使用 PyMuPDF (fitz) 解析PDF中的矢量图形，转换为CAD画板元素。
支持：直线、矩形、多边形填充、路径（贝塞尔曲线采样）

坐标系转换：
- PDF: 原点左上角，Y向下，单位pt（1pt = 1/72 inch ≈ 0.3528mm）
- CAD画板: 原点左下角，Y向上，单位mm
"""

import os
from typing import List, Tuple, Optional


# PDF pt → mm 转换系数
PT_TO_MM = 25.4 / 72.0  # ≈ 0.3528


def import_pdf(file_path: str, log_callback=None) -> Tuple[List, List[str]]:
    """导入PDF文件，返回 (元素列表, 错误列表)"""
    errors = []
    elements = []

    if not os.path.exists(file_path):
        return elements, [f"文件不存在: {file_path}"]

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return elements, ["未安装PyMuPDF。请运行: pip install PyMuPDF"]

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return elements, [f"无法打开PDF文件: {e}"]

    total_lines = 0
    total_quads = 0
    total_texts = 0

    for page_idx, page in enumerate(doc):
        try:
            page_rect = page.rect
            page_width_pt = page_rect.width
            page_height_pt = page_rect.height

            drawings = page.get_drawings()
            if log_callback:
                log_callback(f"PDF第{page_idx+1}页: 发现 {len(drawings)} 个绘图对象")

            for d in drawings:
                items = d.get("items", [])
                color = d.get("color")
                fill = d.get("fill")

                for item in items:
                    itype = item[0]
                    try:
                        if itype == "l":
                            # 直线: ('l', p1, p2)
                            p1, p2 = item[1], item[2]
                            x1, y1 = _to_cad(p1.x, p1.y, page_height_pt)
                            x2, y2 = _to_cad(p2.x, p2.y, page_height_pt)
                            elem = _make_line(x1, y1, x2, y2)
                            if elem:
                                _apply_color(elem, color)
                                elements.append(elem)
                                total_lines += 1

                        elif itype == "re":
                            # 矩形: ('re', rect)
                            rect = item[1]
                            x, y = _to_cad(rect.x0, rect.y0, page_height_pt)
                            x2, y2 = _to_cad(rect.x1, rect.y1, page_height_pt)
                            w, h = abs(x2 - x), abs(y2 - y)
                            # 确保左下角原点
                            lx = min(x, x2)
                            ly = min(y, y2)
                            elem = _make_rect(lx, ly, w, h)
                            if elem:
                                _apply_color(elem, color)
                                elements.append(elem)

                        elif itype == "qu":
                            # 四边形填充: ('qu', quad)
                            # v1.5 P3: 修复点顺序，避免形成交叉对角线
                            quad = item[1]
                            pts = []
                            for p in [quad.ul, quad.ur, quad.lr, quad.ll]:
                                cx, cy = _to_cad(p.x, p.y, page_height_pt)
                                pts.append((cx, cy))
                            # 去重相邻点
                            pts = _dedup_points(pts)
                            if len(pts) >= 3:
                                # 跳过接近页面尺寸的巨大填充（通常是页面背景）
                                bx = [p[0] for p in pts]
                                by = [p[1] for p in pts]
                                bw = max(bx) - min(bx)
                                bh = max(by) - min(by)
                                page_w_mm = page_width_pt * PT_TO_MM
                                page_h_mm = page_height_pt * PT_TO_MM
                                # 如果四边形面积超过页面面积的80%，跳过
                                if bw * bh > 0.8 * page_w_mm * page_h_mm:
                                    pass  # 跳过页面背景填充
                                else:
                                    elem = _make_polyline(pts, closed=True)
                                    if elem:
                                        _apply_color(elem, fill if fill else color)
                                        elements.append(elem)
                                    total_quads += 1

                        elif itype == "c":
                            # 贝塞尔曲线: ('c', p1, p2, p3, p4)
                            # 采样为折线
                            p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                            pts = _sample_bezier(
                                _to_cad_pt(p1, page_height_pt),
                                _to_cad_pt(p2, page_height_pt),
                                _to_cad_pt(p3, page_height_pt),
                                _to_cad_pt(p4, page_height_pt),
                                segments=12
                            )
                            if len(pts) >= 2:
                                elem = _make_polyline(pts, closed=False)
                                if elem:
                                    _apply_color(elem, color)
                                    elements.append(elem)

                    except Exception as e:
                        # 单个元素转换失败，记录但不中断
                        pass

            # ===== PDF文本提取 =====
            try:
                text_blocks = page.get_text("blocks")
                for block in text_blocks:
                    # block格式: (x0, y0, x1, y1, text, block_no, block_type)
                    if len(block) >= 7 and block[6] == 0:  # block_type 0 = 文本
                        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
                        if text and text.strip():
                            # 使用文本块左下角作为锚点
                            cx, cy = _to_cad(x0, y1, page_height_pt)
                            elem = _make_text_point(cx, cy, text.strip())
                            if elem:
                                elements.append(elem)
                                total_texts += 1
            except Exception:
                pass

        except Exception as e:
            errors.append(f"解析第{page_idx+1}页失败: {e}")

    doc.close()

    # 后处理：去重极短线段（PDF中一条线可能被拆成多段）
    elements = _merge_duplicate_lines(elements)

    if log_callback:
        log_callback(f"PDF导入完成: {len(elements)} 个元素 (线={total_lines}, 填充={total_quads}, 文本={total_texts})")

    return elements, errors


def _to_cad(x_pt, y_pt, page_height_pt):
    """PDF坐标 → CAD画板坐标（mm，Y翻转）"""
    return x_pt * PT_TO_MM, (page_height_pt - y_pt) * PT_TO_MM


def _to_cad_pt(p, page_height_pt):
    """fitz Point → CAD坐标元组"""
    return _to_cad(p.x, p.y, page_height_pt)


def _make_line(x1, y1, x2, y2):
    from geometry.elements import LineElement
    return LineElement(float(x1), float(y1), float(x2), float(y2))


def _make_rect(x, y, w, h):
    from geometry.elements import RectangleElement
    if w <= 0 or h <= 0:
        return None
    return RectangleElement(float(x), float(y), float(w), float(h))


def _make_polyline(points, closed=False):
    from geometry.elements import PolylineElement
    if len(points) < 2:
        return None
    return PolylineElement(points, closed=closed)


def _make_text_point(x, y, text):
    """创建文本标注点元素"""
    from geometry.elements import PointElement
    elem = PointElement(float(x), float(y))
    elem.text_content = text  # 附加文本内容，绘制时显示
    elem.style.color = (100, 100, 100)
    return elem


def _apply_color(elem, color):
    """应用PDF颜色到元素样式"""
    if color is None:
        return
    try:
        if isinstance(color, (tuple, list)) and len(color) >= 3:
            r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            elem.style.color = (r, g, b)
        elif hasattr(color, '__iter__'):
            vals = list(color)
            if len(vals) >= 3:
                elem.style.color = (int(vals[0] * 255), int(vals[1] * 255), int(vals[2] * 255))
    except Exception:
        pass


def _sample_bezier(p1, p2, p3, p4, segments=12):
    """三次贝塞尔曲线采样为折线点列"""
    pts = []
    for i in range(segments + 1):
        t = i / segments
        u = 1 - t
        # B(t) = (1-t)^3 P1 + 3(1-t)^2 t P2 + 3(1-t) t^2 P3 + t^3 P4
        x = (u ** 3) * p1[0] + 3 * (u ** 2) * t * p2[0] + 3 * u * (t ** 2) * p3[0] + (t ** 3) * p4[0]
        y = (u ** 3) * p1[1] + 3 * (u ** 2) * t * p2[1] + 3 * u * (t ** 2) * p3[1] + (t ** 3) * p4[1]
        pts.append((float(x), float(y)))
    return pts


def _dedup_points(points, tol=0.01):
    """去除相邻重复点"""
    if not points:
        return points
    result = [points[0]]
    for p in points[1:]:
        last = result[-1]
        if abs(p[0] - last[0]) > tol or abs(p[1] - last[1]) > tol:
            result.append(p)
    return result


def _merge_duplicate_lines(elements, tol=0.1):
    """去重：端点容差内相同的线段合并保留一条"""
    from geometry.elements import LineElement
    lines = []
    others = []
    for e in elements:
        if isinstance(e, LineElement):
            lines.append(e)
        else:
            others.append(e)

    if not lines:
        return others

    # 简单的O(n^2)去重，对于一般PDF足够
    unique = []
    for line in lines:
        is_dup = False
        for u in unique:
            if _same_line(line, u, tol):
                is_dup = True
                break
        if not is_dup:
            unique.append(line)

    return unique + others


def _same_line(a, b, tol):
    """判断两条线段是否相同（端点可互换）"""
    return (
        (abs(a.x1 - b.x1) <= tol and abs(a.y1 - b.y1) <= tol and
         abs(a.x2 - b.x2) <= tol and abs(a.y2 - b.y2) <= tol)
        or
        (abs(a.x1 - b.x2) <= tol and abs(a.y1 - b.y2) <= tol and
         abs(a.x2 - b.x1) <= tol and abs(a.y2 - b.y1) <= tol)
    )


# 兼容类包装器（同 DwgHandler 风格）
class PdfHandler:
    """PDF导入处理器 (兼容类包装器)"""

    def __init__(self):
        pass

    def import_pdf(self, file_path: str) -> List:
        """导入PDF文件，返回元素列表"""
        elements, errors = import_pdf(file_path, log_callback=None)
        if errors:
            for err in errors:
                print(f"[PdfHandler.import_pdf] {err}")
        return elements
