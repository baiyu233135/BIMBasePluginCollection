# -*- coding: utf-8 -*-
"""
组件路径放置辅助模块
沿宿主组件的棱边/中线等预定义路径布置子组件：
- resolve_path_name: 把"顶面前边/中线/X轴/上边"等路径描述解析为预定义路径名
- get_component_route: 按宿主参数把路径名还原为 Route（世界坐标，单位 mm）
- sample_placement_frames: 沿路径采样（位置 + 切向）
- orient_component: 按路径切向旋转子组件（绕 Z 轴，atan2(dy,dx)，弧度）
- build_oriented_components: 生成带方向的放置列表 [(x, y, z, comp), ...]

预定义路径名：
  x_axis / bottom_center_x  底面中心 X 向直线（"X轴"、"中线"、"下边"）
  top_center_x              顶面中心 X 向直线（"上边"、"顶面中线"）
  top|bottom_front|back|left|right_edge  顶/底面四条棱边
坐标约定（与 DIRECTION_MAP 一致）：前=+Y，后=-Y，左=-X，右=+X，上=+Z；
宿主局部盒为 [0,L]×[0,W]×[0,H]，由参数 x/y/z（或 偏移X/Y/Z）平移到世界坐标。
"""

import math


def _log(msg):
    try:
        import os
        from datetime import datetime
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai_modeling_debug.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] component_path: {msg}\n")
    except Exception:
        pass


def _to_float(v, default=0.0):
    """把 Attr/数值统一转成 float"""
    try:
        if hasattr(v, 'value'):
            v = v.value
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _host_dimensions(host_type, params):
    """从宿主组件参数推断 (长L, 宽W, 高H)（mm），无法推断返回 (None, None, None)"""
    if host_type == 'cube':
        s = _to_float(params.get('边长', params.get('size', 0)))
        if s > 0:
            return s, s, s
    if host_type == 'box':
        L = _to_float(params.get('长度', params.get('length', 0)))
        W = _to_float(params.get('宽度', params.get('width', 0)))
        H = _to_float(params.get('高度', params.get('height', 0)))
        if L > 0 and W > 0 and H > 0:
            return L, W, H
    # 通用键回退（含桥墩类的 盖梁总长/盖梁宽/墩高）
    L = _to_float(params.get('长度', params.get('length', params.get('盖梁总长', 0))))
    W = _to_float(params.get('宽度', params.get('width', params.get('盖梁宽', 0))))
    H = _to_float(params.get('高度', params.get('height', params.get('墩高', 0))))
    if L > 0 and W > 0 and H > 0:
        return L, W, H
    return None, None, None


def sample_placement_frames(host_type, host_params, path_name, spacing=None, count=None, include_end=True):
    """沿组件路径采样放置框架，返回 [((x,y,z), (tx,ty,tz)), ...]，失败返回空列表"""
    route = get_component_route(host_type, host_params, path_name)
    if route is None:
        return []
    return route.sample_frames(spacing=spacing, count=count, include_end=include_end)


def orient_component(child, tangent, comp_type=None):
    """按路线切向旋转组件：绕 Z 轴旋转 atan2(dy,dx)（弧度），返回旋转后的组件。
    切向无旋转量或旋转失败（如离线环境无 pyp3d）时原样返回。"""
    if child is None or tangent is None:
        return child
    try:
        angle = math.atan2(float(tangent[1]), float(tangent[0]))
    except Exception:
        return child
    if abs(angle) < 1e-9:
        return child
    try:
        from pyp3d import rotate, Vec3
        return rotate(Vec3(0, 0, 1), angle) * child
    except Exception as e:
        _log(f"orient_component rotate failed: {e}")
        return child


def resolve_path_name(host_type, path_desc):
    """将"顶面前边/中线/X轴/上边"等路径描述解析为预定义路径名，无法解析返回 None"""
    if not path_desc:
        return None
    desc = str(path_desc).strip().lower().replace(' ', '')
    if not desc:
        return None

    # 竖向位置：顶/上 → top，底/下 → bottom
    vertical = None
    if '顶' in desc or '上' in desc:
        vertical = 'top'
    elif '底' in desc or '下' in desc:
        vertical = 'bottom'

    # 侧向：前/后/左/右
    side = None
    for cn, en in (('前', 'front'), ('后', 'back'), ('左', 'left'), ('右', 'right')):
        if cn in desc:
            side = en
            break

    # "X轴"：底面中心 X 向直线
    if 'x轴' in desc:
        return 'x_axis'
    # "中线/中心线"：默认底面中心 X 向，"顶面中线"为顶面
    if '中线' in desc or '中心线' in desc:
        return 'top_center_x' if vertical == 'top' else 'x_axis'
    # 棱边："顶面前边"等；未指明顶/底时默认顶面
    if side is not None:
        v = vertical or 'top'
        return f'{v}_{side}_edge'
    # "上边" → 顶面中心 X 向，"下边" → 底面中心 X 向
    if vertical == 'top':
        return 'top_center_x'
    if vertical == 'bottom':
        return 'bottom_center_x'
    return None


def get_component_route(host_type, host_params, path_name):
    """按宿主参数把预定义路径名还原为 Route（世界坐标，mm），失败返回 None"""
    if not path_name:
        return None
    params = host_params or {}
    L, W, H = _host_dimensions(host_type, params)
    if L is None:
        _log(f"get_component_route: cannot determine dimensions for {host_type}")
        return None
    ox = _to_float(params.get('x', params.get('偏移X', 0)))
    oy = _to_float(params.get('y', params.get('偏移Y', 0)))
    oz = _to_float(params.get('z', params.get('偏移Z', 0)))

    y_mid = oy + W / 2.0
    z_top = oz + H
    path_table = {
        'x_axis': ((ox, y_mid, oz), (ox + L, y_mid, oz)),
        'bottom_center_x': ((ox, y_mid, oz), (ox + L, y_mid, oz)),
        'top_center_x': ((ox, y_mid, z_top), (ox + L, y_mid, z_top)),
        'top_front_edge': ((ox, oy + W, z_top), (ox + L, oy + W, z_top)),
        'top_back_edge': ((ox, oy, z_top), (ox + L, oy, z_top)),
        'top_left_edge': ((ox, oy, z_top), (ox, oy + W, z_top)),
        'top_right_edge': ((ox + L, oy, z_top), (ox + L, oy + W, z_top)),
        'bottom_front_edge': ((ox, oy + W, oz), (ox + L, oy + W, oz)),
        'bottom_back_edge': ((ox, oy, oz), (ox + L, oy, oz)),
        'bottom_left_edge': ((ox, oy, oz), (ox, oy + W, oz)),
        'bottom_right_edge': ((ox + L, oy, oz), (ox + L, oy + W, oz)),
    }
    seg = path_table.get(path_name)
    if seg is None:
        _log(f"get_component_route: unknown path '{path_name}' for {host_type}")
        return None
    try:
        from ai_modeling.route import Route
    except ImportError:
        from route import Route  # 兼容直接脚本导入
    return Route.line(seg[0], seg[1])


def build_oriented_components(host_type, host_params, path_desc,
                              child_type, child_params,
                              spacing=None, count=None, include_end=True):
    """沿组件路径生成已定向的子组件放置列表 [(x, y, z, oriented_child_comp), ...]，
    路径不可解析/无采样点/子组件创建失败时返回空列表。"""
    path_name = resolve_path_name(host_type, path_desc)
    if path_name is None:
        _log(f"build_oriented_components: cannot resolve path '{path_desc}' for {host_type}")
        return []
    frames = sample_placement_frames(host_type, host_params, path_name,
                                     spacing=spacing, count=count, include_end=include_end)
    if not frames:
        _log(f"build_oriented_components: no frames for {host_type}.{path_name}")
        return []
    # 延迟导入，避免与 component_factory 循环依赖
    from ai_modeling.component_factory import create_component
    placements = []
    for pos, tangent in frames:
        child = create_component(child_type, child_params)
        if child is None:
            continue
        oriented = orient_component(child, tangent, comp_type=child_type)
        placements.append((pos[0], pos[1], pos[2], oriented))
    return placements
