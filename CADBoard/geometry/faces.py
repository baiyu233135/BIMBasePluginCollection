# -*- coding: utf-8 -*-
"""
面模板定义 - Phase 3

定义各种参数化组件的面集合，以及面↔组件参数的映射规则。

面的结构:
- name: 面名称 (top/bottom/front/back/left/right)
- plane: 投影平面标记 (xy/xz/yz)，画板统一用XY平面显示
- element_type: 该面在画板中对应的元素类型
- param_map: {面元素属性: 组件参数}，用于面修改→组件参数反推
- generator(params): 根据组件参数生成面元素实例
- update_params(elem, old_elem, params): 根据面元素变化更新组件参数

所有面元素在画板上都以XY平面显示，但语义上代表不同投影。
"""

import math
from typing import Dict, Callable, Any

# 动态面生成器中直接使用，需要模块级导入
from geometry.elements import PolylineElement, RectangleElement

# 面名称显示映射：内部英文标识 -> 中文显示名
FACE_NAME_LABELS = {
    'top': '俯视图',
    'bottom': '底视图',
    'front': '主视图',
    'back': '后视图',
    'left': '左视图',
    'right': '右视图',
    'side_a': '直角边1面',
    'side_b': '直角边2面',
    'hypotenuse': '斜面',
    'side': '侧视图',
    'unroll': '展开图',
    'side0': '侧面0',
    'side1': '侧面1',
    'side2': '侧面2',
    'side3': '侧面3',
}


def _box_front_update(elem, old, params):
    """Box front面(对应XZ平面,压平显示): x→x, z→y, length→width, height→height"""
    dx = elem.x - old['x']
    dw = elem.width - old['width']
    params['x'] += dx
    params['length'] += dw
    # 使用面元素的当前绝对高度计算新的z_top
    params['z_top'] = params['z_bottom'] + elem.height
    return params


def _box_left_update(elem, old, params):
    """Box left面(对应YZ平面,压平显示): y→x, z→y, width→width, height→height"""
    dx = elem.x - old['x']
    dw = elem.width - old['width']
    params['y'] += dx
    params['width'] += dw
    # 使用面元素的当前绝对高度计算新的z_top
    params['z_top'] = params['z_bottom'] + elem.height
    return params


def _box_top_update(elem, old, params):
    """Box top面(对应XY平面): x→x, y→y, width→length, height→width"""
    dx = elem.x - old['x']
    dy = elem.y - old['y']
    dw = elem.width - old['width']
    dh = elem.height - old['height']
    params['x'] += dx
    params['y'] += dy
    params['length'] += dw
    params['width'] += dh
    return params


def _circle_top_update(elem, old, params):
    """圆顶面: cx→cx, cy→cy, radius→radius"""
    params['cx'] = elem.cx
    params['cy'] = elem.cy
    params['radius'] = elem.radius
    return params


def _circle_side_update(elem, old, params):
    """圆柱侧面展开: width→周长, height→高"""
    dw = elem.width - old['width']
    old_r = params['radius']
    old_c = 2 * math.pi * old_r
    new_c = old_c + dw
    if new_c > 0:
        params['radius'] = new_c / (2 * math.pi)
    # 使用面元素的当前绝对高度计算新的z_top
    params['z_top'] = params['z_bottom'] + elem.height
    return params


def _polygon_top_update(elem, old, params):
    """多边形顶面: points变化→px0/py0...变化"""
    if hasattr(elem, 'points') and elem.points:
        for i, (px, py) in enumerate(elem.points):
            params[f'px{i}'] = float(px)
            params[f'py{i}'] = float(py)
        params['point_count'] = len(elem.points)
    return params


def _polygon_side_update(elem, old, params):
    """多边形侧面: height→z_top-z_bottom"""
    params['z_top'] = params.get('z_bottom', 0) + elem.height
    return params


def _line_top_update(elem, old, params):
    """线段投影: x1/y1/x2/y2直接映射"""
    params['x1'] = elem.x1
    params['y1'] = elem.y1
    params['x2'] = elem.x2
    params['y2'] = elem.y2
    return params


def _arc_top_update(elem, old, params):
    """圆弧顶面: cx/cy/radius/angles直接映射"""
    params['cx'] = elem.cx
    params['cy'] = elem.cy
    params['radius'] = elem.radius
    params['start_angle'] = elem.start_angle
    params['end_angle'] = elem.end_angle
    return params


def _ellipse_top_update(elem, old, params):
    """椭圆顶面: cx/cy/rx/ry直接映射"""
    params['cx'] = elem.cx
    params['cy'] = elem.cy
    params['rx'] = elem.rx
    params['ry'] = elem.ry
    return params


def _point_top_update(elem, old, params):
    """点投影: x/y直接映射"""
    params['x'] = elem.x
    params['y'] = elem.y
    return params


def _polyline_top_update(elem, old, params):
    """多段线投影: points变化→px0/py0...变化"""
    if hasattr(elem, 'points') and elem.points:
        for i, (px, py) in enumerate(elem.points):
            params[f'px{i}'] = float(px)
            params[f'py{i}'] = float(py)
        params['point_count'] = len(elem.points)
    return params


def _prism_top_update(elem, old, params):
    """三棱柱顶面/底面: points变化→直角边1/直角边2变化"""
    if hasattr(elem, 'points') and len(elem.points) >= 3:
        xs = [p[0] for p in elem.points]
        ys = [p[1] for p in elem.points]
        non_zero_x = [x for x in xs if abs(x) > 0.01]
        non_zero_y = [y for y in ys if abs(y) > 0.01]
        if non_zero_x:
            params['直角边1'] = max(non_zero_x)
        if non_zero_y:
            params['直角边2'] = max(non_zero_y)
    return params


def _prism_side_a_update(elem, old, params):
    """三棱柱侧面a (直角边1×高度): width→直角边1, height→高度"""
    dw = elem.width - old['width']
    params['直角边1'] += dw
    params['高度'] = elem.height
    return params


def _prism_side_b_update(elem, old, params):
    """三棱柱侧面b (直角边2×高度): width→直角边2, height→高度"""
    dw = elem.width - old['width']
    params['直角边2'] += dw
    params['高度'] = elem.height
    return params


def _prism_side_hypotenuse_update(elem, old, params):
    """三棱柱斜面 (√(直角边1²+直角边2²)×高度): width→hypotenuse按比例缩放直角边1/直角边2, height→高度"""
    params['高度'] = elem.height
    old_hyp = old['width']
    new_hyp = elem.width
    if old_hyp > 0 and new_hyp > 0 and abs(new_hyp - old_hyp) > 0.01:
        ratio = new_hyp / old_hyp
        params['直角边1'] = params.get('直角边1', 100) * ratio
        params['直角边2'] = params.get('直角边2', 100) * ratio
    return params


# ========== 圆柱面更新函数 ==========

def _cylinder_top_update(elem, old, params):
    """圆柱顶面/底面: radius变化→半径变化"""
    params['半径'] = elem.radius
    return params

def _cylinder_side_update(elem, old, params):
    """圆柱侧面展开: width→周长(2πr), height→高度"""
    params['高度'] = elem.height
    new_c = elem.width
    if new_c > 0:
        params['半径'] = new_c / (2 * math.pi)
    return params

def _cylinder_front_update(elem, old, params):
    """圆柱前视图: width→直径(2r), height→高度"""
    params['高度'] = elem.height
    new_d = elem.width
    if new_d > 0:
        params['半径'] = new_d / 2
    return params

def _cylinder_left_update(elem, old, params):
    """圆柱左视图: width→直径(2r), height→高度"""
    params['高度'] = elem.height
    new_d = elem.width
    if new_d > 0:
        params['半径'] = new_d / 2
    return params


# ========== 正方体面更新函数 ==========

def _cube_top_update(elem, old, params):
    """正方体顶面/底面: width/height→边长"""
    params['边长'] = elem.width
    return params

def _cube_front_update(elem, old, params):
    """正方体前视图: width/height→边长"""
    params['边长'] = elem.width
    return params

def _cube_left_update(elem, old, params):
    """正方体左视图: width/height→边长"""
    params['边长'] = elem.width
    return params


# ========== 长方体面更新函数 ==========

def _cuboid_top_update(elem, old, params):
    """长方体顶面: width→长度, height→宽度"""
    params['长度'] = elem.width
    params['宽度'] = elem.height
    return params

def _cuboid_front_update(elem, old, params):
    """长方体前视图: width→长度, height→高度"""
    params['长度'] = elem.width
    params['高度'] = elem.height
    return params

def _cuboid_left_update(elem, old, params):
    """长方体左视图: width→宽度, height→高度"""
    params['宽度'] = elem.width
    params['高度'] = elem.height
    return params


# ========== 引桥桥墩面更新函数 ==========

def _pier_top_update(elem, old, params):
    """引桥桥墩俯视图: width→盖梁总长, height→盖梁宽"""
    params['盖梁总长'] = elem.width
    params['盖梁宽'] = elem.height
    return params


def _pier_front_update(elem, old, params):
    """引桥桥墩主视图: width→盖梁总长, height→墩高+盖梁总高"""
    params['盖梁总长'] = elem.width
    new_total_h = elem.height
    cap_h = params.get('盖梁总高', 300)
    new_col_h = max(0, new_total_h - cap_h)
    params['墩高'] = new_col_h
    return params


def _pier_left_update(elem, old, params):
    """引桥桥墩左视图: width→盖梁宽, height→墩高+盖梁总高"""
    params['盖梁宽'] = elem.width
    new_total_h = elem.height
    cap_h = params.get('盖梁总高', 300)
    new_col_h = max(0, new_total_h - cap_h)
    params['墩高'] = new_col_h
    return params


# ========== 动态面生成器 ==========

def _polygon_dynamic_faces(params, component_id):
    """为多边形生成侧面：只生成最多2个侧面（前视图/左视图），避免面过多"""
    faces = {}
    count = params.get('point_count', 0)
    pts = []
    for i in range(count):
        px = params.get(f'px{i}')
        py = params.get(f'py{i}')
        if px is not None and py is not None:
            pts.append((float(px), float(py)))
    if len(pts) < 2:
        return faces
    z_bottom = params.get('z_bottom', 0)
    z_top = params.get('z_top', 100)
    h = z_top - z_bottom
    # 最多生成2个侧面，作为前视图和左视图的代表
    max_sides = 2
    for i in range(min(len(pts), max_sides)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        edge_len = math.hypot(x2 - x1, y2 - y1)
        elem = RectangleElement(0, z_bottom, edge_len, h)
        elem.component_type = 'Polygon3DComponent'
        elem.component_params = dict(params)
        elem.face_info = {
            'face_name': f'side{i}',
            'plane': 'side',
            'snap_plane': 'side',
            'component_id': component_id,
            'edge_index': i,
        }
        elem.is_3d = False
        elem.style.color = (255, 80, 80)
        elem.style.line_type = 'dashed'
        elem.style.line_width = 1.0
        faces[f'side{i}'] = elem
    return faces


def _prism_dynamic_faces(params, component_id):
    """为直角三棱柱生成完整面：俯视图(top) + 底视图(bottom) + 前视图(side_a) + 左视图(side_b) + 斜面(hypotenuse)"""
    faces = {}
    a = float(params.get('直角边1', 100))
    b = float(params.get('直角边2', 100))
    h = float(params.get('高度', 200))
    z_bottom = params.get('z_bottom', 0)
    # 俯视图/底视图：直角三角形
    pts = [(0, 0), (a, 0), (0, b)]
    for fn, plane in [('top', 'xy'), ('bottom', 'xy')]:
        elem = PolylineElement(pts, closed=True)
        elem.component_type = '直角三棱柱'
        elem.component_params = dict(params)
        elem.face_info = {
            'face_name': fn,
            'plane': plane,
            'snap_plane': plane,
            'component_id': component_id,
        }
        elem.is_3d = False
        elem.style.color = (255, 80, 80)
        elem.style.line_type = 'dashed'
        elem.style.line_width = 1.0
        faces[fn] = elem

    # 前视图 (沿 X 轴): 矩形 直角边1 × 高度
    side_a = RectangleElement(0, z_bottom, a, h)
    side_a.component_type = '直角三棱柱'
    side_a.component_params = dict(params)
    side_a.face_info = {
        'face_name': 'side_a',
        'plane': 'xz',
        'snap_plane': 'xz',
        'component_id': component_id,
    }
    side_a.is_3d = False
    side_a.style.color = (255, 80, 80)
    side_a.style.line_type = 'dashed'
    side_a.style.line_width = 1.0
    faces['side_a'] = side_a

    # 左视图 (沿 Y 轴): 矩形 直角边2 × 高度
    side_b = RectangleElement(0, z_bottom, b, h)
    side_b.component_type = '直角三棱柱'
    side_b.component_params = dict(params)
    side_b.face_info = {
        'face_name': 'side_b',
        'plane': 'yz',
        'snap_plane': 'yz',
        'component_id': component_id,
    }
    side_b.is_3d = False
    side_b.style.color = (255, 80, 80)
    side_b.style.line_type = 'dashed'
    side_b.style.line_width = 1.0
    faces['side_b'] = side_b

    # 斜面
    hyp = RectangleElement(0, z_bottom, math.hypot(a, b), h)
    hyp.component_type = '直角三棱柱'
    hyp.component_params = dict(params)
    hyp.face_info = {
        'face_name': 'hypotenuse',
        'plane': 'side',
        'snap_plane': 'side',
        'component_id': component_id,
    }
    hyp.is_3d = False
    hyp.style.color = (255, 80, 80)
    hyp.style.line_type = 'dashed'
    hyp.style.line_width = 1.0
    faces['hypotenuse'] = hyp

    return faces


# ========== 面模板注册表 ==========

FACE_TEMPLATES = {
    'SweepBoxComponent': {
        # 三视图：俯视图(top) + 前视图(front) + 左视图(left)
        'top': {
            'plane': 'xy',
            'description': '俯视图 (XY)',
            'generator': lambda p: _make_rect(p['x'], p['y'], p['length'], p['width']),
            'update_params': _box_top_update,
            'snap_plane': 'xy',
        },
        'front': {
            'plane': 'xz',
            'description': '前视图 (XZ)',
            'generator': lambda p: _make_rect(p['x'], p['z_bottom'], p['length'], p['z_top'] - p['z_bottom']),
            'update_params': _box_front_update,
            'snap_plane': 'xz',
        },
        'left': {
            'plane': 'yz',
            'description': '左视图 (YZ)',
            'generator': lambda p: _make_rect(p['y'], p['z_bottom'], p['width'], p['z_top'] - p['z_bottom']),
            'update_params': _box_left_update,
            'snap_plane': 'yz',
        },
    },
    'Circle3DComponent': {
        # 三视图：俯视图(top) + 前视图/左视图(side，侧面展开)
        'top': {
            'plane': 'xy',
            'description': '俯视图圆 (XY)',
            'generator': lambda p: _make_circle(p['cx'], p['cy'], p['radius']),
            'update_params': _circle_top_update,
            'snap_plane': 'xy',
        },
        'side': {
            'plane': 'unroll',
            'description': '前/左视图 (圆周×高)',
            'generator': lambda p: _make_rect(0, p['z_bottom'], 2 * math.pi * p['radius'], p['z_top'] - p['z_bottom']),
            'update_params': _circle_side_update,
            'snap_plane': 'unroll',
        },
    },
    'Polygon3DComponent': {
        # 俯视图 + 最多2个侧面代表前视图/左视图
        'top': {
            'plane': 'xy',
            'description': '俯视图 (XY)',
            'generator': lambda p: _make_polygon(p),
            'update_params': _polygon_top_update,
            'snap_plane': 'xy',
        },
    },
    'Line3DComponent': {
        'top': {
            'plane': 'xy',
            'description': '投影 (XY)',
            'generator': lambda p: _make_line(p['x1'], p['y1'], p['x2'], p['y2']),
            'update_params': _line_top_update,
            'snap_plane': 'xy',
        },
    },
    'Arc3DComponent': {
        'top': {
            'plane': 'xy',
            'description': '投影 (XY)',
            'generator': lambda p: _make_arc(p['cx'], p['cy'], p['radius'], p['start_angle'], p['end_angle']),
            'update_params': _arc_top_update,
            'snap_plane': 'xy',
        },
    },
    'Ellipse3DComponent': {
        'top': {
            'plane': 'xy',
            'description': '顶面 (XY)',
            'generator': lambda p: _make_ellipse(p['cx'], p['cy'], p['rx'], p['ry']),
            'update_params': _ellipse_top_update,
            'snap_plane': 'xy',
        },
    },
    'Point3DComponent': {
        'top': {
            'plane': 'xy',
            'description': '投影 (XY)',
            'generator': lambda p: _make_circle(p.get('x', 0), p.get('y', 0), p.get('radius', 5)),
            'update_params': _point_top_update,
            'snap_plane': 'xy',
        },
    },
    'Polyline3DComponent': {
        'top': {
            'plane': 'xy',
            'description': '投影 (XY)',
            'generator': lambda p: _make_polyline(p),
            'update_params': _polyline_top_update,
            'snap_plane': 'xy',
        },
    },
    '直角三棱柱': {
        # 完整面：俯视图(top) + 底视图(bottom) + 前视图(side_a) + 左视图(side_b) + 斜面(hypotenuse)
        'top': {
            'plane': 'xy',
            'description': '俯视图三角形 (XY)',
            'generator': lambda p: _make_prism_top(p),
            'update_params': _prism_top_update,
            'snap_plane': 'xy',
        },
        'bottom': {
            'plane': 'xy',
            'description': '底视图三角形 (XY)',
            'generator': lambda p: _make_prism_top(p),
            'update_params': _prism_top_update,
            'snap_plane': 'xy',
        },
        'side_a': {
            'plane': 'xz',
            'description': '前视图 (直角边1×高度)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['直角边1'], p['高度']),
            'update_params': _prism_side_a_update,
            'snap_plane': 'xz',
        },
        'side_b': {
            'plane': 'yz',
            'description': '左视图 (直角边2×高度)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['直角边2'], p['高度']),
            'update_params': _prism_side_b_update,
            'snap_plane': 'yz',
        },
        'hypotenuse': {
            'plane': 'side',
            'description': '斜面 (√(直角边1²+直角边2²)×高度)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), math.hypot(p['直角边1'], p['直角边2']), p['高度']),
            'update_params': _prism_side_hypotenuse_update,
            'snap_plane': 'side',
        },
    },
    '圆柱': {
        # 三视图：俯视图(top) + 主视图(front) + 左视图(left)
        # 完整模式额外包含：底视图(bottom) + 侧面展开(unroll)
        'top': {
            'plane': 'xy',
            'description': '俯视图圆 (XY)',
            'generator': lambda p: _make_circle(0, 0, p['半径']),
            'update_params': _cylinder_top_update,
            'snap_plane': 'xy',
        },
        'bottom': {
            'plane': 'xy',
            'description': '底视图圆 (XY)',
            'generator': lambda p: _make_circle(0, 0, p['半径']),
            'update_params': _cylinder_top_update,
            'snap_plane': 'xy',
        },
        'front': {
            'plane': 'xz',
            'description': '前视图 (直径×高度)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), 2 * p['半径'], p['高度']),
            'update_params': _cylinder_front_update,
            'snap_plane': 'xz',
        },
        'left': {
            'plane': 'yz',
            'description': '左视图 (直径×高度)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), 2 * p['半径'], p['高度']),
            'update_params': _cylinder_left_update,
            'snap_plane': 'yz',
        },
        'side': {
            'plane': 'unroll',
            'description': '侧面展开 (周长×高度)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), 2 * math.pi * p['半径'], p['高度']),
            'update_params': _cylinder_side_update,
            'snap_plane': 'unroll',
        },
    },
    '正方体': {
        # 六面体：上下前后左右
        'top': {
            'plane': 'xy',
            'description': '俯视图 (XY)',
            'generator': lambda p: _make_rect(0, 0, p['边长'], p['边长']),
            'update_params': _cube_top_update,
            'snap_plane': 'xy',
        },
        'bottom': {
            'plane': 'xy',
            'description': '底视图 (XY)',
            'generator': lambda p: _make_rect(0, 0, p['边长'], p['边长']),
            'update_params': _cube_top_update,
            'snap_plane': 'xy',
        },
        'front': {
            'plane': 'xz',
            'description': '前视图 (XZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['边长'], p['边长']),
            'update_params': _cube_front_update,
            'snap_plane': 'xz',
        },
        'back': {
            'plane': 'xz',
            'description': '后视图 (XZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['边长'], p['边长']),
            'update_params': _cube_front_update,
            'snap_plane': 'xz',
        },
        'left': {
            'plane': 'yz',
            'description': '左视图 (YZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['边长'], p['边长']),
            'update_params': _cube_left_update,
            'snap_plane': 'yz',
        },
        'right': {
            'plane': 'yz',
            'description': '右视图 (YZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['边长'], p['边长']),
            'update_params': _cube_left_update,
            'snap_plane': 'yz',
        },
    },
    '长方体': {
        # 六面体：上下前后左右
        'top': {
            'plane': 'xy',
            'description': '俯视图 (XY)',
            'generator': lambda p: _make_rect(0, 0, p['长度'], p['宽度']),
            'update_params': _cuboid_top_update,
            'snap_plane': 'xy',
        },
        'bottom': {
            'plane': 'xy',
            'description': '底视图 (XY)',
            'generator': lambda p: _make_rect(0, 0, p['长度'], p['宽度']),
            'update_params': _cuboid_top_update,
            'snap_plane': 'xy',
        },
        'front': {
            'plane': 'xz',
            'description': '前视图 (XZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['长度'], p['高度']),
            'update_params': _cuboid_front_update,
            'snap_plane': 'xz',
        },
        'back': {
            'plane': 'xz',
            'description': '后视图 (XZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['长度'], p['高度']),
            'update_params': _cuboid_front_update,
            'snap_plane': 'xz',
        },
        'left': {
            'plane': 'yz',
            'description': '左视图 (YZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['宽度'], p['高度']),
            'update_params': _cuboid_left_update,
            'snap_plane': 'yz',
        },
        'right': {
            'plane': 'yz',
            'description': '右视图 (YZ)',
            'generator': lambda p: _make_rect(0, p.get('z_bottom', 0), p['宽度'], p['高度']),
            'update_params': _cuboid_left_update,
            'snap_plane': 'yz',
        },
    },
    '引桥桥墩': {
        # 三视图：俯视图 + 主视图 + 左视图
        'top': {
            'plane': 'xy',
            'description': '俯视图 (盖梁顶面)',
            'generator': lambda p: _make_rect(0, 0, p.get('盖梁总长', 1930), p.get('盖梁宽', 300)),
            'update_params': _pier_top_update,
            'snap_plane': 'xy',
        },
        'front': {
            'plane': 'xz',
            'description': '主视图 (盖梁+墩柱正面)',
            'generator': lambda p: _make_rect(
                0, p.get('z_bottom', 0),
                p.get('盖梁总长', 1930),
                p.get('墩高', 1200) + p.get('盖梁总高', 300)
            ),
            'update_params': _pier_front_update,
            'snap_plane': 'xz',
        },
        'left': {
            'plane': 'yz',
            'description': '左视图 (盖梁+墩柱侧面)',
            'generator': lambda p: _make_rect(
                0, p.get('z_bottom', 0),
                p.get('盖梁宽', 300),
                p.get('墩高', 1200) + p.get('盖梁总高', 300)
            ),
            'update_params': _pier_left_update,
            'snap_plane': 'yz',
        },
    },
}


# ========== 元素工厂函数 ==========

def _make_rect(x, y, w, h):
    from geometry.elements import RectangleElement
    return RectangleElement(float(x), float(y), float(w), float(h))


def _make_prism_top(p):
    """生成直角三棱柱的顶面/底面三角形"""
    from geometry.elements import PolylineElement
    a = float(p.get('直角边1', 100))
    b = float(p.get('直角边2', 100))
    pts = [(0, 0), (a, 0), (0, b)]
    return PolylineElement(pts, closed=True)


def _make_circle(cx, cy, r):
    from geometry.elements import CircleElement
    return CircleElement(float(cx), float(cy), float(r))


def _make_polygon(params):
    from geometry.elements import PolylineElement
    count = params.get('point_count', 0)
    pts = []
    for i in range(count):
        px = params.get(f'px{i}')
        py = params.get(f'py{i}')
        if px is not None and py is not None:
            pts.append((float(px), float(py)))
    return PolylineElement(pts, closed=True)


def _make_line(x1, y1, x2, y2):
    from geometry.elements import LineElement
    return LineElement(float(x1), float(y1), float(x2), float(y2))


def _make_arc(cx, cy, r, sa, ea):
    from geometry.elements import ArcElement
    return ArcElement(float(cx), float(cy), float(r), float(sa), float(ea))


def _make_ellipse(cx, cy, rx, ry):
    from geometry.elements import EllipseElement
    return EllipseElement(float(cx), float(cy), float(rx), float(ry))


def _make_polyline(params):
    from geometry.elements import PolylineElement
    count = params.get('point_count', 0)
    pts = []
    for i in range(count):
        px = params.get(f'px{i}')
        py = params.get(f'py{i}')
        if px is not None and py is not None:
            pts.append((float(px), float(py)))
    return PolylineElement(pts, closed=False)




# ========== 面管理器 ==========

class FaceManager:
    """管理组件的面元素生成与参数反推"""

    @classmethod
    def get_face_names(cls, component_type):
        """获取组件类型的所有面名称"""
        template = FACE_TEMPLATES.get(component_type)
        if not template:
            return []
        return list(template.keys())

    @classmethod
    def get_face_template(cls, component_type, face_name):
        """获取指定面的模板"""
        template = FACE_TEMPLATES.get(component_type)
        if not template:
            return None
        return template.get(face_name)

    @classmethod
    def generate_face_element(cls, component_type, face_name, params):
        """
        根据组件参数生成面元素
        返回: (element, face_info_dict)
        """
        template = cls.get_face_template(component_type, face_name)
        if not template:
            return None
        try:
            elem = template['generator'](params)
            elem.component_type = component_type
            elem.component_params = dict(params)
            elem.face_info = {
                'face_name': face_name,
                'plane': template.get('plane', 'xy'),
                'snap_plane': template.get('snap_plane', 'xy'),
            }
            elem.is_3d = False  # 面元素本身是2D
            # 面元素使用特殊样式以便区分
            elem.style.color = (255, 80, 80)
            elem.style.line_type = 'dashed'
            elem.style.line_width = 1.0
            return elem
        except Exception as e:
            print(f"[FaceManager] 生成面元素失败: {component_type}/{face_name} - {e}")
            return None

    @classmethod
    def _layout_faces(cls, faces):
        """给面元素添加偏移，避免重叠。
        标准三视图布局（第一角投影法）：
        - 主视图(front/side_a, XZ平面)：左上（屏幕上方，Y值最大）
        - 左视图(left/side_b, YZ平面)：右上（与主视图高平齐）
        - 俯视图(top, XY平面)：左下（与主视图长对正，Y值最小）
        同时记录每个面的 layout_offset，以便后续面修改对比时抵消偏移。
        """
        if not faces:
            return
        try:
            spacing = 50
            
            # 按投影平面分类
            front_faces = []   # xz 平面 → 主视图
            top_faces = []     # xy 平面 → 俯视图
            left_faces = []    # yz 平面 → 左视图
            other_faces = []
            
            for name, elem in faces.items():
                plane = elem.face_info.get('plane', 'xy')
                if plane == 'xz':
                    front_faces.append((name, elem))
                elif plane == 'yz':
                    left_faces.append((name, elem))
                elif plane == 'xy':
                    top_faces.append((name, elem))
                else:
                    other_faces.append((name, elem))
            
            # 取每类第一个作为代表
            front = front_faces[0] if front_faces else None
            top = top_faces[0] if top_faces else None
            left = left_faces[0] if left_faces else None
            
            # 计算各面尺寸，用于确定布局锚点
            front_w = front_h = 0
            if front:
                fb = front[1].get_bounds()
                front_w = fb[2] - fb[0]
                front_h = fb[3] - fb[1]
            
            top_w = top_h = 0
            if top:
                tb = top[1].get_bounds()
                top_w = tb[2] - tb[0]
                top_h = tb[3] - tb[1]
            
            # 布局锚点（世界坐标Y向上，屏幕上方=更大Y值）
            # 让俯视图底部接近Y=0，主视图在上方，左视图与主视图同高
            anchor_x = spacing
            anchor_y = spacing + top_h + spacing + front_h  # 主视图顶部对齐位置
            
            # 主视图（XZ平面）：左上角对齐到 (anchor_x, anchor_y)
            if front:
                name, elem = front
                fb = elem.get_bounds()
                dx = anchor_x - fb[0]
                dy = anchor_y - fb[3]  # fb[3]=max_y，让顶部对齐anchor_y
                elem.translate(dx, dy)
                elem.face_info['layout_offset'] = (dx, dy)
                front_w = fb[2] - fb[0]
                front_h = fb[3] - fb[1]
            else:
                front_w = front_h = 0
            
            # 俯视图（XY平面）：放在主视图正下方，X方向对齐
            if top:
                name, elem = top
                tb = elem.get_bounds()
                if front:
                    dx = anchor_x - tb[0]  # X与主视图对齐
                    dy = (anchor_y - front_h - spacing) - tb[3]  # 顶部在主视图底部下方
                else:
                    dx = anchor_x - tb[0]
                    dy = anchor_y - tb[3]
                elem.translate(dx, dy)
                elem.face_info['layout_offset'] = (dx, dy)
            
            # 左视图（YZ平面）：放在主视图右侧，顶部与主视图顶部对齐
            if left:
                name, elem = left
                lb = elem.get_bounds()
                if front:
                    dx = (anchor_x + front_w + spacing) - lb[0]
                    dy = anchor_y - lb[3]  # 顶部与主视图顶部对齐
                else:
                    dx = anchor_x - lb[0]
                    dy = anchor_y - lb[3]
                elem.translate(dx, dy)
                elem.face_info['layout_offset'] = (dx, dy)
            
            # 处理剩余的面（垂直排列在左视图右侧）
            used = set()
            if front: used.add(front[0])
            if top: used.add(top[0])
            if left: used.add(left[0])
            remaining = [(n, e) for n, e in faces.items() if n not in used]
            
            if remaining:
                if left:
                    y_cursor = left[1].get_bounds()[1]
                    x_start = left[1].get_bounds()[2] + spacing
                elif front:
                    y_cursor = anchor_y - front_h
                    x_start = anchor_x + front_w + spacing
                else:
                    y_cursor = anchor_y
                    x_start = anchor_x
                    
                for name, elem in remaining:
                    bb = elem.get_bounds()
                    dx = x_start - bb[0]
                    dy = y_cursor - bb[1]
                    elem.translate(dx, dy)
                    elem.face_info['layout_offset'] = (dx, dy)
                    y_cursor += (bb[3] - bb[1]) + 20
        except Exception as e:
            print(f"[FaceManager] _layout_faces error: {e}")

    # 智能模式映射：组件类型 -> 推荐模式
    SMART_MODE_MAP = {
        '直角三棱柱': '三视图',
        '圆柱': '三视图',
        '正方体': '完整',
        '长方体': '完整',
    }

    @classmethod
    def generate_all_faces(cls, component_type, params, component_id=None, mode='三视图'):
        """
        生成组件的所有面元素
        mode: '三视图' 只生成3个标准投影面（主视/俯视/左视）
              '完整'   生成组件定义的所有面
              '智能'   根据组件类型自动选择最合适的模式
        返回: {face_name: element}
        """
        faces = {}
        all_face_names = cls.get_face_names(component_type)
        
        # 智能模式：按组件类型自动决定
        if mode == '智能':
            mode = cls.SMART_MODE_MAP.get(component_type, '三视图')
        
        # 确定要生成哪些面
        if mode == '三视图':
            # 标准三视图：只取 xy(俯视), xz(主视), yz(左视) 三个投影平面
            standard_planes = {'xy', 'xz', 'yz'}
            seen_planes = set()
            for face_name in all_face_names:
                template = cls.get_face_template(component_type, face_name)
                plane = template.get('plane', 'xy') if template else 'xy'
                if plane in standard_planes and plane not in seen_planes:
                    seen_planes.add(plane)
                    elem = cls.generate_face_element(component_type, face_name, params)
                    if elem:
                        if component_id:
                            elem.face_info['component_id'] = component_id
                        faces[face_name] = elem
        else:
            # 完整模式：生成所有定义的面
            for face_name in all_face_names:
                elem = cls.generate_face_element(component_type, face_name, params)
                if elem:
                    if component_id:
                        elem.face_info['component_id'] = component_id
                    faces[face_name] = elem

        # 动态生成额外面（仅在完整模式下）
        if mode != '三视图':
            # 动态生成多边形侧面
            if component_type == 'Polygon3DComponent' and params.get('point_count', 0) > 2:
                dynamic = _polygon_dynamic_faces(params, component_id)
                faces.update(dynamic)

            # 动态生成三棱柱面（兼容旧逻辑）
            if component_type == '直角三棱柱':
                dynamic = _prism_dynamic_faces(params, component_id)
                # 只补充静态模板中不存在的面
                for k, v in dynamic.items():
                    if k not in faces:
                        faces[k] = v

        # 布局偏移，避免重叠
        cls._layout_faces(faces)
        return faces

    @classmethod
    def update_params_from_face(cls, component_type, face_name, elem, old_state, params):
        """
        根据面元素的变化更新组件参数
        old_state: {x, y, width, height, cx, cy, radius, ...} 变化前的状态
        返回: 更新后的参数字典（新对象，不修改原params）
        """
        template = cls.get_face_template(component_type, face_name)
        updater = None
        if template:
            updater = template.get('update_params')
        else:
            # 动态面 fallback
            if component_type == 'Polygon3DComponent' and face_name.startswith('side'):
                updater = _polygon_side_update
            elif component_type == '直角三棱柱' and face_name.startswith('side'):
                # 直角三棱柱 的动态面已经在静态模板中，不应该走到这里
                pass
        if not updater:
            return params
        new_params = dict(params)
        try:
            return updater(elem, old_state, new_params)
        except Exception as e:
            print(f"[FaceManager] 参数反推失败: {component_type}/{face_name} - {e}")
            return params

    @classmethod
    def capture_element_state(cls, elem):
        """捕获元素的当前几何状态（用于后续对比变化）"""
        state = {}
        et = elem.__class__.__name__
        if et == 'RectangleElement':
            state['x'] = elem.x
            state['y'] = elem.y
            state['width'] = elem.width
            state['height'] = elem.height
        elif et == 'CircleElement':
            state['cx'] = elem.cx
            state['cy'] = elem.cy
            state['radius'] = elem.radius
        elif et == 'PolylineElement':
            state['points'] = list(elem.points)
        elif et == 'LineElement':
            state['x1'] = elem.x1
            state['y1'] = elem.y1
            state['x2'] = elem.x2
            state['y2'] = elem.y2
        elif et == 'ArcElement':
            state['cx'] = elem.cx
            state['cy'] = elem.cy
            state['radius'] = elem.radius
            state['start_angle'] = elem.start_angle
            state['end_angle'] = elem.end_angle
        elif et == 'EllipseElement':
            state['cx'] = elem.cx
            state['cy'] = elem.cy
            state['rx'] = elem.rx
            state['ry'] = elem.ry
        elif et == 'PointElement':
            state['x'] = elem.x
            state['y'] = elem.y
        return state


# 快捷函数
def get_component_faces(component_type):
    return FaceManager.get_face_names(component_type)


def generate_faces(component_type, params, component_id=None):
    return FaceManager.generate_all_faces(component_type, params, component_id)
