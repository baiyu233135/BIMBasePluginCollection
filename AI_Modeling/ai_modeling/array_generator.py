# -*- coding: utf-8 -*-
"""阵列生成算法"""
import math


def linear_array(base_x, base_y, base_z, count, spacing, axis='x'):
    """
    线性阵列
    axis: 'x', 'y', 'z'
    返回坐标列表 [(x,y,z), ...]
    """
    coords = []
    dx = spacing if axis == 'x' else 0
    dy = spacing if axis == 'y' else 0
    dz = spacing if axis == 'z' else 0
    for i in range(count):
        coords.append((base_x + dx * i, base_y + dy * i, base_z + dz * i))
    return coords


def rectangular_array(base_x, base_y, base_z, rows, cols, row_spacing, col_spacing,
                      row_axis='x', col_axis='y'):
    """
    矩形阵列（网格）
    row_axis: 行方向 ('x' 或 'y')
    col_axis: 列方向 ('y' 或 'x')
    返回坐标列表 [(x,y,z), ...]
    """
    coords = []
    for r in range(rows):
        for c in range(cols):
            dx = r * row_spacing if row_axis == 'x' else c * col_spacing if col_axis == 'x' else 0
            dy = r * row_spacing if row_axis == 'y' else c * col_spacing if col_axis == 'y' else 0
            coords.append((base_x + dx, base_y + dy, base_z))
    return coords


def polar_array(base_x, base_y, base_z, count, radius, start_angle=0, total_angle=360, axis='z'):
    """
    环形/极坐标阵列（围绕指定轴）
    目前只支持绕 Z 轴（axis='z'）
    返回坐标列表 [(x,y,z), ...]
    """
    coords = []
    if count <= 0:
        return coords
    if count == 1:
        return [(base_x + radius, base_y, base_z)]
    angle_step = math.radians(total_angle) / (count - 1) if total_angle < 360 else math.radians(total_angle) / count
    for i in range(count):
        angle = math.radians(start_angle) + angle_step * i
        x = base_x + radius * math.cos(angle)
        y = base_y + radius * math.sin(angle)
        coords.append((x, y, base_z))
    return coords


def parse_array_params(text_dict):
    """
    从解析结果中提取阵列参数
    返回: (mode, params_dict) 或 (None, None)
    """
    # 检测阵列关键词
    arr_keywords = ['阵列', '每隔', '间距', '间距', '间距', '间距',
                    'array', 'spacing', 'interval', 'grid', 'matrix']
    # 简化的检测逻辑：由 command_parser 在更高层处理
    return None, None
