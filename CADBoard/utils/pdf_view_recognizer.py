# -*- coding: utf-8 -*-
"""
PDF三视图智能识别器

功能：分析导入的PDF线条元素，识别三视图布局，
      自动推断组件类型和参数，创建参数化组件。

识别逻辑：
1. 收集所有未关联组件的线条元素
2. 按空间位置聚类为3个视图区域
3. 根据标准三视图布局（第一角投影）判断视图类型
4. 从每个视图提取尺寸（包围盒）
5. 根据3视图尺寸关系推断组件类型和参数
"""

import math
from typing import List, Tuple, Dict, Optional


def recognize_three_views(elements) -> Optional[Dict]:
    """
    智能识别三视图布局
    
    Args:
        elements: 画板元素列表
        
    Returns:
        {
            'component_type': '长方体'|'圆柱'|'正方体'等,
            'component_params': {...},
            'views': {
                'top': {'elements': [...], 'bounds': (x1,y1,x2,y2)},
                'front': {'elements': [...], 'bounds': (x1,y1,x2,y2)},
                'left': {'elements': [...], 'bounds': (x1,y1,x2,y2)},
            }
        }
        或 None（无法识别）
    """
    # 1. 筛选可用的几何元素（排除文本点、已关联组件的、不可见的、极短的）
    usable = []
    for e in elements:
        if not getattr(e, 'visible', True):
            continue
        if getattr(e, 'component_type', ''):
            continue
        if getattr(e, 'face_info', {}):
            continue
        # 排除文本标注点（有text_content的PointElement）
        if getattr(e, 'text_content', ''):
            continue
        # 排除纯点元素（无几何意义）
        et = getattr(e, 'element_type', None)
        if et and getattr(et, 'value', '') == '点':
            continue
        # 只考虑有get_bounds的几何元素
        if not hasattr(e, 'get_bounds'):
            continue
        # 排除极短线段（可能是尺寸标注线、箭头等）
        b = e.get_bounds()
        bw = b[2] - b[0]
        bh = b[3] - b[1]
        # 如果元素的包围盒非常小（<1mm），可能是标注符号
        if bw < 1.0 and bh < 1.0:
            continue
        usable.append(e)
    
    if len(usable) < 3:
        return None
    
    # v1.5 P3: 严格限制：简单三视图的元素数量通常在几十到几百之间
    if len(usable) > 500:
        return None
    
    # 2. 计算每个元素的包围盒中心点
    centers = []
    for e in usable:
        b = e.get_bounds()
        cx = (b[0] + b[2]) / 2
        cy = (b[1] + b[3]) / 2
        centers.append((cx, cy, e, b))
    
    # 2.1 过滤外框/背景矩形（避免巨大外框干扰视图分组）
    centers = _filter_outer_frame(centers)
    if len(centers) < 2:
        return None
    
    # 3. 按空间位置聚类为视图组（支持上二下一、上一下二等非标准布局）
    groups = _split_into_three_views(centers)
    if not groups:
        return None
    
    # 4. 识别每个组是什么视图
    view_types = _identify_view_types(groups)
    if not view_types:
        return None
    
    # 5. 计算每个视图的尺寸
    views = {}
    for view_name, group in view_types.items():
        if not group:
            continue
        elems = [item[2] for item in group]
        bounds = _group_bounds(group)
        views[view_name] = {
            'elements': elems,
            'bounds': bounds,
            'width': bounds[2] - bounds[0],
            'height': bounds[3] - bounds[1],
        }
    
    if len(views) < 2:
        return None
    
    # v1.5 P3: 单个视图元素数量上限检查（超过200个说明不是简单三视图）
    for vn, vd in views.items():
        if len(vd['elements']) > 200:
            return None
    
    # v1.5 P3: 视图尺寸合理性检查（简单几何体的视图尺寸应在5~1000mm范围内）
    for vn, vd in views.items():
        w, h = vd['width'], vd['height']
        if w < 5 or h < 5 or w > 1000 or h > 1000:
            return None
    
    # 6. 推断组件类型和参数
    result = _infer_component_from_views(views)
    if result:
        result['views'] = views
        result['all_elements'] = usable
    
    return result


def _filter_outer_frame(centers, ratio_w=0.80, ratio_h=0.80, ratio_area=0.65):
    """过滤掉占页面大部分面积的疑似外框/背景矩形"""
    if not centers:
        return centers
    min_x = min(c[3][0] for c in centers)
    min_y = min(c[3][1] for c in centers)
    max_x = max(c[3][2] for c in centers)
    max_y = max(c[3][3] for c in centers)
    page_w = max(max_x - min_x, 1.0)
    page_h = max(max_y - min_y, 1.0)
    page_area = page_w * page_h
    filtered = []
    for c in centers:
        b = c[3]
        bw = b[2] - b[0]
        bh = b[3] - b[1]
        area = bw * bh
        is_frame = (bw > ratio_w * page_w and bh > ratio_h * page_h) or \
                   (area > ratio_area * page_area)
        if not is_frame:
            filtered.append(c)
    return filtered


def _split_by_gap(items, key_func, gap_min=15.0):
    """按最大间隙将 items 分成两组，间隙小于阈值时返回 None"""
    if len(items) < 2:
        return None
    sorted_items = sorted(items, key=key_func)
    gaps = []
    for i in range(len(sorted_items) - 1):
        gap = key_func(sorted_items[i + 1]) - key_func(sorted_items[i])
        gaps.append((gap, i))
    gaps.sort(reverse=True)
    if not gaps or gaps[0][0] < gap_min:
        return None
    idx = gaps[0][1]
    return sorted_items[:idx + 1], sorted_items[idx + 1:]


def _split_into_three_views(centers):
    """将元素中心点分为2~3个视图组，支持上二下一/上一下二/标准三视图"""
    if len(centers) < 2:
        return None
    
    # 策略1: 先按Y方向（行）分割，再对行内按X方向（列）分割
    # 使用 -Y 排序，使 Y 较大（图纸上方）的组在前，对应 front/left
    row_split = _split_by_gap(centers, lambda c: -c[1], gap_min=15.0)
    if row_split:
        top_row, bottom_row = row_split
        top_col_split = _split_by_gap(top_row, lambda c: c[0], gap_min=15.0)
        bot_col_split = _split_by_gap(bottom_row, lambda c: c[0], gap_min=15.0)
        
        # 上二下一：图纸上方两视图（front + left），下方一视图（top）
        if top_col_split:
            g1, g2 = top_col_split
            if len(g1) >= 1 and len(g2) >= 1:
                return {'front': g1, 'left': g2, 'top': bottom_row}
        # 上一下二：图纸上方一视图（front），下方两视图（top + left）
        if bot_col_split:
            g1, g2 = bot_col_split
            if len(g1) >= 1 and len(g2) >= 1:
                return {'front': top_row, 'top': g1, 'left': g2}
        # 只有上下两行，按两视图处理
        return {'front': top_row, 'top': bottom_row}
    
    # 策略2: 先按X方向（列）分割，再对列内按Y方向（行）分割
    col_split = _split_by_gap(centers, lambda c: c[0], gap_min=15.0)
    if col_split:
        left_col, right_col = col_split
        left_row_split = _split_by_gap(left_col, lambda c: -c[1], gap_min=15.0)
        right_row_split = _split_by_gap(right_col, lambda c: -c[1], gap_min=15.0)
        
        if left_row_split:
            g1, g2 = left_row_split
            if len(g1) >= 1 and len(g2) >= 1:
                return {'front': g1, 'top': g2, 'left': right_col}
        if right_row_split:
            g1, g2 = right_row_split
            if len(g1) >= 1 and len(g2) >= 1:
                return {'front': left_col, 'top': g1, 'left': g2}
        return {'front': left_col, 'left': right_col}
    
    # 策略3: 回退到旧的三间隙标准三视图分割
    n = len(centers)
    y_sorted = sorted(centers, key=lambda x: x[1], reverse=True)
    y_gaps = []
    for i in range(n - 1):
        gap = y_sorted[i][1] - y_sorted[i + 1][1]
        y_gaps.append((gap, i))
    y_gaps.sort(reverse=True)
    
    if len(y_gaps) >= 2 and y_gaps[0][0] > 20 and y_gaps[1][0] > 20:
        idx1 = y_gaps[0][1]
        idx2 = y_gaps[1][1]
        if idx2 < idx1:
            idx1, idx2 = idx2, idx1
        top = y_sorted[:idx1 + 1]
        mid = y_sorted[idx1 + 1:idx2 + 1]
        bottom = y_sorted[idx2 + 1:]
        return {'top': top, 'mid': mid, 'bottom': bottom}
    
    x_sorted = sorted(centers, key=lambda x: x[0])
    x_gaps = []
    for i in range(n - 1):
        gap = x_sorted[i + 1][0] - x_sorted[i][0]
        x_gaps.append((gap, i))
    x_gaps.sort(reverse=True)
    
    if len(x_gaps) >= 2 and x_gaps[0][0] > 20 and x_gaps[1][0] > 20:
        idx1 = x_gaps[0][1]
        idx2 = x_gaps[1][1]
        if idx2 < idx1:
            idx1, idx2 = idx2, idx1
        left = x_sorted[:idx1 + 1]
        mid = x_sorted[idx1 + 1:idx2 + 1]
        right = x_sorted[idx2 + 1:]
        return {'left': left, 'mid': mid, 'right': right}
    
    return None


def _identify_view_types(groups):
    """根据布局判断每个组是什么视图"""
    if not groups:
        return None
    
    # 如果分组时已经直接映射为 front/top/left，直接复用
    direct_keys = {'front', 'top', 'left'}
    if direct_keys & set(groups.keys()):
        result = {}
        for k in ('front', 'top', 'left'):
            if k in groups:
                result[k] = groups[k]
        return result if result else None
    
    # 标准三视图布局（第一角投影）：
    #   [front] [left]
    #   [top]
    # 或者：
    #   [front]
    #   [top] [left]
    
    result = {}
    
    if 'top' in groups and 'mid' in groups and 'bottom' in groups:
        # Y方向分割：上=front, 中=可能是left, 下=top
        # 或者上=front, 中=top, 下=可能是其他
        # 需要根据X位置进一步判断
        top_group = groups['top']
        mid_group = groups['mid']
        bottom_group = groups['bottom']
        
        # 比较mid和bottom的X位置
        top_x = _group_center_x(top_group)
        mid_x = _group_center_x(mid_group)
        bottom_x = _group_center_x(bottom_group)
        
        # front通常在上方且在中间
        if abs(top_x - bottom_x) < abs(top_x - mid_x):
            # top和bottom在X方向对齐 → top=front, bottom=top
            result['front'] = top_group
            result['top'] = bottom_group
            result['left'] = mid_group
        else:
            # top和mid在X方向对齐
            result['front'] = top_group
            result['top'] = mid_group
            result['left'] = bottom_group
            
    elif 'left' in groups and 'mid' in groups and 'right' in groups:
        # X方向分割：左=top, 中=front, 右=left
        # 或者根据Y位置判断
        left_group = groups['left']
        mid_group = groups['mid']
        right_group = groups['right']
        
        left_y = _group_center_y(left_group)
        mid_y = _group_center_y(mid_group)
        right_y = _group_center_y(right_group)
        
        # front通常在上方
        if mid_y >= left_y and mid_y >= right_y:
            result['front'] = mid_group
            result['top'] = left_group if left_y < mid_y else right_group
            result['left'] = right_group if left_y < mid_y else left_group
        else:
            result['front'] = mid_group
            result['top'] = left_group
            result['left'] = right_group
    
    return result if result else None


def _group_center_x(group):
    if not group:
        return 0
    return sum(item[0] for item in group) / len(group)


def _group_center_y(group):
    if not group:
        return 0
    return sum(item[1] for item in group) / len(group)


def _group_bounds(group):
    """计算一组元素的总体包围盒"""
    min_x = min(item[3][0] for item in group)
    min_y = min(item[3][1] for item in group)
    max_x = max(item[3][2] for item in group)
    max_y = max(item[3][3] for item in group)
    return (min_x, min_y, max_x, max_y)


def _group_contains_triangle(group, tol=1.0):
    """判断一个视图组中是否包含三角形（直角三棱柱的底面特征）"""
    if not group:
        return False
    # 兼容两种输入：分组项 (cx, cy, elem, bounds) 或元素对象列表
    first = group[0]
    if isinstance(first, (tuple, list)) and len(first) >= 3:
        elems = [item[2] for item in group]
    else:
        elems = list(group)
    
    line_segments = []
    for elem in elems:
        pts = getattr(elem, 'points', None)
        # 多段线直接检查是否为三角形
        if pts and len(pts) == 3:
            return True
        if getattr(elem, 'closed', False) and pts and len(pts) == 3:
            return True
        # 收集线段端点
        if hasattr(elem, 'x1') and hasattr(elem, 'y1') and hasattr(elem, 'x2') and hasattr(elem, 'y2'):
            line_segments.append(((elem.x1, elem.y1), (elem.x2, elem.y2)))
    
    # 如果组内恰好有3条线段且构成闭合三角形，也认为是三角形视图
    if len(line_segments) == 3:
        vertices = []
        for (p1, p2) in line_segments:
            found_p1 = False
            found_p2 = False
            for v in vertices:
                if abs(v[0] - p1[0]) < tol and abs(v[1] - p1[1]) < tol:
                    found_p1 = True
                if abs(v[0] - p2[0]) < tol and abs(v[1] - p2[1]) < tol:
                    found_p2 = True
            if not found_p1:
                vertices.append(p1)
            if not found_p2:
                vertices.append(p2)
        if len(vertices) == 3:
            return True
    return False


def _infer_component_from_views(views):
    """根据三视图尺寸推断组件类型和参数"""
    top = views.get('top')
    front = views.get('front')
    left = views.get('left')
    
    # 1. 优先根据“是否存在三角形视图”判断直角三棱柱
    tri_view = None
    for vn, vd in views.items():
        if _group_contains_triangle(vd.get('elements', [])):
            tri_view = vn
            break
    if tri_view and len(views) >= 2:
        tri = views[tri_view]
        a = tri['width']
        b = tri['height']
        # 高度取其余矩形视图高度的平均值
        heights = []
        for vn, vd in views.items():
            if vn != tri_view:
                heights.append(vd['height'])
        h = sum(heights) / len(heights) if heights else max(a, b, 100)
        return {
            'component_type': '直角三棱柱',
            'component_params': {
                '直角边1': round(a, 1),
                '直角边2': round(b, 1),
                '高度': round(h, 1),
            },
        }
    
    if not top or not front:
        return None
    
    # 提取尺寸
    top_w = top.get('width', 0)
    top_h = top.get('height', 0)
    front_w = front.get('width', 0)
    front_h = front.get('height', 0)
    left_w = left.get('width', 0) if left else 0
    left_h = left.get('height', 0) if left else 0
    
    # 三视图尺寸关系：
    # 长方体: top=(长,宽), front=(长,高), left=(宽,高)
    # 圆柱: top=(直径,直径圆形), front=(直径,高)
    # 正方体: 三个视图都是正方形且相等
    
    # 判断是否为正方体
    all_dims = [top_w, top_h, front_w, front_h]
    if left:
        all_dims.extend([left_w, left_h])
    
    avg_dim = sum(all_dims) / len(all_dims)
    is_cube = all(abs(d - avg_dim) / max(avg_dim, 1) < 0.15 for d in all_dims)
    
    if is_cube:
        return {
            'component_type': '正方体',
            'component_params': {'边长': round(avg_dim, 1)},
        }
    
    # 判断长方体
    # top和front应该有共同的尺寸（长）
    length_match = abs(top_w - front_w) / max(top_w, front_w, 1) < 0.2
    
    if length_match:
        length = (top_w + front_w) / 2  # 长
        width = top_h  # 宽（从俯视图）
        height = front_h  # 高（从主视图）
        
        if left:
            # 左视图应该是 (宽, 高)
            left_match_w = abs(left_w - width) / max(left_w, width, 1) < 0.3
            left_match_h = abs(left_h - height) / max(left_h, height, 1) < 0.3
            if left_match_w and left_match_h:
                return {
                    'component_type': '长方体',
                    'component_params': {
                        '长度': round(length, 1),
                        '宽度': round(width, 1),
                        '高度': round(height, 1),
                    },
                }
        else:
            # 只有两视图，也尝试推断
            return {
                'component_type': '长方体',
                'component_params': {
                    '长度': round(length, 1),
                    '宽度': round(width, 1),
                    '高度': round(height, 1),
                },
            }
    
    # 判断三棱柱（直角三棱柱）：
    # 俯视图是直角三角形（包围盒近似矩形），主视图和左视图是矩形
    # 尺寸关系：主视图宽 ≈ 俯视图宽（直角边1），左视图宽 ≈ 俯视图高（直角边2）
    #          主视图高 ≈ 左视图高（高度）
    if left and top_w > 5 and top_h > 5 and front_h > 5:
        # 检查三棱柱尺寸关系
        side_a_match = abs(front_w - top_w) / max(front_w, top_w, 1) < 0.2  # 主视图宽 = 俯视图宽
        side_b_match = abs(left_w - top_h) / max(left_w, top_h, 1) < 0.2   # 左视图宽 = 俯视图高
        height_match = abs(front_h - left_h) / max(front_h, left_h, 1) < 0.2  # 主视图高 = 左视图高
        
        if side_a_match and side_b_match and height_match:
            return {
                'component_type': '直角三棱柱',
                'component_params': {
                    '直角边1': round(top_w, 1),
                    '直角边2': round(top_h, 1),
                    '高度': round(front_h, 1),
                },
            }
    
    # 判断圆柱：俯视图是圆（宽≈高），主视图是矩形
    top_is_circle = abs(top_w - top_h) / max(top_w, top_h, 1) < 0.15
    if top_is_circle:
        # 先判断是否为球体：三视图均为等尺寸圆/正方形
        sphere_match = True
        for v in (front, left):
            if not v:
                continue
            if abs(v['width'] - top_w) / max(top_w, 1) > 0.2 or \
               abs(v['height'] - top_w) / max(top_w, 1) > 0.2:
                sphere_match = False
                break
        if sphere_match and front:
            return {
                'component_type': '球体',
                'component_params': {
                    '半径': round(top_w / 2, 1),
                },
            }

        radius = top_w / 2
        height = front_h
        return {
            'component_type': '圆柱',
            'component_params': {
                '半径': round(radius, 1),
                '高度': round(height, 1),
            },
        }
    
    # 默认：长方体
    return {
        'component_type': '长方体',
        'component_params': {
            '长度': round(max(top_w, front_w), 1),
            '宽度': round(min(top_w, top_h), 1),
            '高度': round(front_h, 1),
        },
    }


def _create_outline_element(comp_type, view_name, cx, cy, params):
    """根据组件类型和视图名称生成标准轮廓元素"""
    from geometry.elements import RectangleElement, CircleElement, PolylineElement

    if comp_type == '长方体':
        L = float(params.get('长度', 200))
        W = float(params.get('宽度', 100))
        H = float(params.get('高度', 150))
        if view_name == 'top':
            return RectangleElement(cx - L / 2, cy - W / 2, L, W)
        elif view_name == 'front':
            return RectangleElement(cx - L / 2, cy - H / 2, L, H)
        elif view_name == 'left':
            return RectangleElement(cx - W / 2, cy - H / 2, W, H)

    elif comp_type == '正方体':
        a = float(params.get('边长', 100))
        return RectangleElement(cx - a / 2, cy - a / 2, a, a)

    elif comp_type == '圆柱':
        r = float(params.get('半径', 50))
        h = float(params.get('高度', 100))
        if view_name == 'top':
            return CircleElement(cx, cy, r)
        else:
            return RectangleElement(cx - r, cy - h / 2, 2 * r, h)

    elif comp_type == '球体':
        r = float(params.get('半径', 50))
        return CircleElement(cx, cy, r)

    elif comp_type == '直角三棱柱':
        a = float(params.get('直角边1', 100))
        b = float(params.get('直角边2', 100))
        h = float(params.get('高度', 200))
        if view_name == 'top':
            pts = [(cx - a / 2, cy - b / 2),
                   (cx + a / 2, cy - b / 2),
                   (cx - a / 2, cy + b / 2)]
            return PolylineElement(pts, closed=True)
        elif view_name == 'front':
            return RectangleElement(cx - a / 2, cy - h / 2, a, h)
        elif view_name == 'left':
            return RectangleElement(cx - b / 2, cy - h / 2, b, h)

    return None


def _lenient_recognize(elements):
    """宽松识别：过滤外框后按空间分组，默认按直角三棱柱绘制轮廓"""
    usable = []
    for e in elements:
        if not getattr(e, 'visible', True):
            continue
        if getattr(e, 'component_type', ''):
            continue
        if getattr(e, 'face_info', {}):
            continue
        if getattr(e, 'text_content', ''):
            continue
        et = getattr(e, 'element_type', None)
        if et and getattr(et, 'value', '') == '点':
            continue
        if not hasattr(e, 'get_bounds'):
            continue
        b = e.get_bounds()
        if (b[2] - b[0]) < 1.0 and (b[3] - b[1]) < 1.0:
            continue
        usable.append(e)
    
    if len(usable) < 2:
        return None
    
    centers = []
    for e in usable:
        b = e.get_bounds()
        cx = (b[0] + b[2]) / 2
        cy = (b[1] + b[3]) / 2
        centers.append((cx, cy, e, b))
    centers = _filter_outer_frame(centers)
    if len(centers) < 2:
        return None
    
    groups = _split_into_three_views(centers)
    if not groups:
        groups = {'front': centers}
    
    views = {}
    for vn, group in groups.items():
        bounds = _group_bounds(group)
        views[vn] = {
            'elements': [item[2] for item in group],
            'bounds': bounds,
            'width': bounds[2] - bounds[0],
            'height': bounds[3] - bounds[1],
        }
    
    # 默认按直角三棱柱推断
    widths = [v['width'] for v in views.values()]
    heights = [v['height'] for v in views.values()]
    a = max(widths) if widths else 100
    b = sorted(widths)[-2] if len(widths) >= 2 else (max(heights) if heights else 100)
    h = max(heights) if heights else 150
    return {
        'component_type': '直角三棱柱',
        'component_params': {
            '直角边1': round(max(a, b), 1),
            '直角边2': round(min(a, b), 1),
            '高度': round(h, 1),
        },
        'views': views,
        'all_elements': usable,
    }


def auto_associate_from_pdf_views(board) -> Tuple[bool, str]:
    """
    一键智能识别三视图并绘制标准轮廓。

    【关键设计】
    - 隐藏原始PDF线条
    - 根据推断的组件类型在每个视图区域绘制标准几何轮廓
    - 轮廓元素标记为面元素，不参与BIMBase同步
    - 创建隐藏的源组件元素保存组件类型和参数
    - 直接进入面编辑模式

    Returns: (success, message)
    """
    result = recognize_three_views(board.elements)
    if not result:
        # 严格识别失败时，使用宽松模式兜底，默认按直角三棱柱绘制轮廓
        result = _lenient_recognize(board.elements)
    if not result:
        return False, (
            "无法自动识别三视图布局。\n\n"
            "可能原因：\n"
            "1. 图纸太复杂（元素过多或不是标准三视图）\n"
            "2. 视图之间没有明显的空间分隔\n"
            "3. 包含大量尺寸标注线干扰了识别\n\n"
            "建议：使用'生成面元素'功能，先手动创建组件，再进入面编辑模式。"
        )

    comp_type = result['component_type']
    params = result['component_params']
    views = result['views']

    # 创建源组件元素（隐藏，用于保存组件类型和参数）
    from utils.component_registry import create_element_from_params
    source_elem = create_element_from_params(params, comp_type)
    if not source_elem:
        return False, f"无法创建 {comp_type} 组件"

    source_elem.component_type = comp_type
    source_elem.component_params = dict(params)
    source_elem.visible = False
    board.elements.append(source_elem)
    cid = source_elem.id

    # 隐藏原始PDF线条
    for view_name, view_data in views.items():
        for elem in view_data['elements']:
            elem.visible = False
            elem._pdf_hidden_original = True

    # 绘制标准轮廓面元素
    from geometry.elements import RectangleElement, CircleElement, PolylineElement
    outline_color = {
        'top': (0, 200, 100),
        'front': (255, 100, 100),
        'left': (100, 150, 255),
    }
    created = 0
    first_face = None
    for view_name in ['front', 'top', 'left']:
        view_data = views.get(view_name)
        if not view_data:
            continue
        bx1, by1, bx2, by2 = view_data['bounds']
        cx = (bx1 + bx2) / 2.0
        cy = (by1 + by2) / 2.0
        outline = _create_outline_element(comp_type, view_name, cx, cy, params)
        if outline is None:
            continue
        outline.component_type = comp_type
        outline.component_params = dict(params)
        outline.face_info = {
            'component_id': cid,
            'face_name': view_name,
            'is_pdf_outline': True,
        }
        outline.style.color = outline_color.get(view_name, (200, 200, 200))
        outline.style.line_width = 1.0
        board.elements.append(outline)
        created += 1
        if first_face is None:
            first_face = outline

    # 初始化面组管理器
    if board._face_group is None:
        from utils.face_mapper import ComponentFaceGroup
        board._face_group = ComponentFaceGroup(board)

    # 取消选中所有，选中第一个轮廓
    for e in board.elements:
        e.selected = False
    if first_face:
        first_face.selected = True

    # 自动进入面编辑模式
    board._enter_face_edit_mode(comp_type, cid)
    board._update_property_panel()
    board.viewport.update()

    # PDF 识别后的组件不直接放置，标记为待放置，由用户点击
    # “同步到BIMBase”时通过坐标弹窗输入放置位置。
    source_elem.pdf_recognized = True
    source_elem.pdf_anchor_x = 0.0
    source_elem.pdf_anchor_y = 0.0
    source_elem.pdf_anchor_z = 0.0

    placement_msg = "\n请点击“同步到BIMBase”，在弹出的坐标对话框中输入放置位置。"

    view_desc = ", ".join(f"{k}: {v['width']:.0f}x{v['height']:.0f}" for k, v in views.items())
    return True, (f"已识别 {comp_type}，参数: {params}\n"
                  f"视图尺寸: {view_desc}\n"
                  f"已绘制 {created} 个三视图轮廓（不参与BIMBase同步）"
                  f"{placement_msg}")
