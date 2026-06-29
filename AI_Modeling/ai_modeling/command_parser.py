# -*- coding: utf-8 -*-
"""本地自然语言命令解析器 - AI建模专用"""
import re


class ModelingCommandParser:
    """解析用户自然语言指令为结构化命令"""

    # 组件类型映射
    COMPONENT_MAP = {
        '圆柱': 'cylinder', '圆柱体': 'cylinder', '圆柱子': 'cylinder',
        '长方体': 'box', '长方': 'box', '盒子': 'box',
        '正方体': 'cube', '立方体': 'cube', '正方形': 'cube',
        '球体': 'sphere', '球': 'sphere', '圆球': 'sphere',
        '圆锥': 'cone', '圆锥体': 'cone', '锥体': 'cone',
    }

    # 操作映射
    ACTION_MAP = {
        '生成': 'create', '创建': 'create', '画': 'create', '绘制': 'create', '画一个': 'create',
        '布置': 'create', '放置': 'create', '摆': 'create',
        '修改': 'modify', '改': 'modify', '调整': 'modify', '更新': 'modify',
        '删除': 'delete', '移除': 'delete',
    }

    # 方向映射（相对坐标）
    DIRECTION_MAP = {
        '上': ('z', +1), '上方': ('z', +1), '上面': ('z', +1), '之上': ('z', +1),
        '下': ('z', -1), '下方': ('z', -1), '下面': ('z', -1), '之下': ('z', -1),
        '左': ('x', -1), '左方': ('x', -1), '左边': ('x', -1),
        '右': ('x', +1), '右方': ('x', +1), '右边': ('x', +1),
        '前': ('y', +1), '前方': ('y', +1), '前面': ('y', +1),
        '后': ('y', -1), '后方': ('y', -1), '后面': ('y', -1),
    }

    # 阵列关键词
    ARRAY_PATTERNS = [
        r'沿\s*([XYZxyz])\s*轴?\s*每隔\s*(\d+\.?\d*)\s*(?:mm)?\s*生成?\s*(\d+)\s*个',
        r'沿\s*([XYZxyz])\s*轴?\s*间距\s*(\d+\.?\d*)\s*(?:mm)?\s*(\d+)\s*个',
        r'([\d]+)\s*×\s*([\d]+)\s*方阵',
        r'([\d]+)\s*乘\s*([\d]+)\s*',
        r'([\d]+)\s*行\s*([\d]+)\s*列',
    ]

    @classmethod
    def parse(cls, text):
        """
        解析自然语言，返回结构化命令字典
        返回: {
            'action': 'create'|'modify'|'delete',
            'component_type': 'cylinder'|'box'|'cube'|'sphere'|'cone',
            'params': {参数},
            'position': {'mode': 'absolute'|'relative'|'selected', ...},
            'array': {'mode': 'linear'|'rectangular'|'polar', ...} or None,
            'target': {'mode': 'selected'|'last'|'index', ...},  # 用于modify/delete
        }
        """
        text = text.strip().lower().replace('，', ',').replace('（', '(').replace('）', ')')

        result = {
            'action': None,
            'component_type': None,
            'params': {},
            'position': {'mode': 'absolute', 'x': 0, 'y': 0, 'z': 0},
            'array': None,
            'route': None,
            'path': None,
            'target': None,
        }

        # 1. 检测操作
        for cn, en in cls.ACTION_MAP.items():
            if cn.lower() in text:
                result['action'] = en
                break
        if not result['action']:
            # 默认假设是创建
            result['action'] = 'create'

        # 2. 检测沿组件路径布置（如“沿选中正方体的顶面前边放圆柱”）
        path_info = cls._extract_component_path(text)
        if path_info:
            result['path'] = path_info

        # 3. 检测组件类型
        # 如果是沿组件路径布置，目标组件类型通常是路径描述之后的“小构件”
        if path_info:
            child_type = cls._extract_child_component_type(text, path_info)
            if child_type:
                result['component_type'] = child_type
        if not result['component_type']:
            for cn, en in cls.COMPONENT_MAP.items():
                if cn.lower() in text:
                    result['component_type'] = en
                    break

        # 4. 修改/删除操作的目标检测
        if result['action'] in ('modify', 'delete'):
            result['target'] = cls._parse_target(text)
            # 修改操作也需要组件类型（可选）
            if not result['component_type']:
                # 尝试从目标推断
                pass
            result['params'] = cls._extract_params(text)
            return result

        # 4. 创建操作必须有组件类型
        if result['action'] == 'create' and not result['component_type']:
            # 可能是纯阵列或位置描述，但没有说是什么组件
            return None

        # 5. 提取参数（半径/长/宽/高/边长等）
        result['params'] = cls._extract_params(text)

        # 6. 提取位置信息
        result['position'] = cls._extract_position(text)

        # 7. 提取阵列信息
        result['array'] = cls._extract_array(text)

        # 8. 提取路线信息（沿路线布置）
        result['route'] = cls._extract_route(text)

        return result

    @classmethod
    def _extract_component_path(cls, text):
        """
        检测“沿选中正方体的顶面前边放圆柱”这类沿组件路径布置。
        返回: {
            'host_type': 'cube'|'cylinder'|... 或 None（表示使用当前选中组件）,
            'path_desc': '顶面前边',
            'spacing': float or None,
            'count': int or None,
        } or None
        """
        # 必须以“沿”开头，并包含后续放置动作
        if '沿' not in text:
            return None

        # 允许的主机组件中文类型
        host_types = list(cls.COMPONENT_MAP.keys()) + ['正方体', '长方体', '圆柱体']
        host_pat = r'((?:' + '|'.join(re.escape(h) for h in host_types) + r'))?'
        # 路径描述：从“沿...的”到“每隔/间距/放/生成/布置/放置/摆”之前
        full_pat = r'沿\s*(?:选中|当前|该)?\s*' + host_pat + r'\s*(?:的|之)?\s*(.+?)\s*(?:每隔|间距|间隔|放|生成|布置|放置|摆|共)'
        m = re.search(full_pat, text)
        if not m:
            return None

        host_cn = m.group(1).strip() if m.group(1) else None
        host_type = cls.COMPONENT_MAP.get(host_cn) if host_cn else None
        path_desc = m.group(2).strip()
        if not path_desc:
            return None

        # 排除被“沿直线/曲线/圆弧/路线”或显式几何参数（圆心/半径/起点/终点等）误匹配的情况
        route_keywords = ('直线', '曲线', '圆弧', '路线', '圆心', '半径', '起点', '终点', '角度', '坐标', '轴')
        if path_desc in ('直线', '曲线', '圆弧', '路线') or any(kw in path_desc for kw in route_keywords):
            return None

        spacing, count = cls._extract_route_spacing(text)
        return {
            'host_type': host_type,
            'path_desc': path_desc,
            'spacing': spacing,
            'count': count,
        }

    @classmethod
    def _extract_child_component_type(cls, text, path_info):
        """在沿组件路径语句中，提取被放置的小构件类型"""
        # 从路径描述之后开始查找第一个组件类型
        # 简单策略：找到“放/生成/布置/放置”之后的组件名
        marker_match = re.search(r'(放|生成|布置|放置|摆)\s*(?:一个|些|若干)?\s*(半径|直径|边长|长|高)?\s*', text)
        start = marker_match.end() if marker_match else 0
        sub = text[start:]
        for cn, en in cls.COMPONENT_MAP.items():
            if cn.lower() in sub:
                return en
        return None

    @classmethod
    def _extract_params(cls, text):
        """提取几何参数"""
        params = {}

        # 半径 / r
        r_patterns = [
            r'半径\s*(\d+\.?\d*)',
            r'[rR]\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*的?半径',
        ]
        for pat in r_patterns:
            m = re.search(pat, text)
            if m:
                params['radius'] = float(m.group(1))
                break

        # 长度 / 长（负向环视，避免把“边长”误识别为 length）
        len_patterns = [
            r'(?<!边)长\s*(\d+\.?\d*)',
            r'长度\s*(\d+\.?\d*)',
        ]
        for pat in len_patterns:
            m = re.search(pat, text)
            if m:
                params['length'] = float(m.group(1))
                break

        # 宽度 / 宽
        wid_patterns = [
            r'宽\s*(\d+\.?\d*)',
            r'宽度\s*(\d+\.?\d*)',
        ]
        for pat in wid_patterns:
            m = re.search(pat, text)
            if m:
                params['width'] = float(m.group(1))
                break

        # 高度 / 高
        h_patterns = [
            r'高\s*(\d+\.?\d*)',
            r'高度\s*(\d+\.?\d*)',
        ]
        for pat in h_patterns:
            m = re.search(pat, text)
            if m:
                params['height'] = float(m.group(1))
                break

        # 边长（正方体）
        a_patterns = [
            r'边长\s*(\d+\.?\d*)',
        ]
        for pat in a_patterns:
            m = re.search(pat, text)
            if m:
                params['size'] = float(m.group(1))
                break

        return params

    @classmethod
    def _extract_position(cls, text):
        """提取位置信息。若用户未指定任何位置，返回 'manual' 模式，由调用方弹窗询问。"""
        pos = {'mode': 'manual'}

        # 绝对坐标: (1000,2000,500) / 1000,2000,500
        abs_3d_patterns = [
            r'在?\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'坐标\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
        ]
        for pat in abs_3d_patterns:
            m = re.search(pat, text)
            if m:
                pos['mode'] = 'absolute'
                pos['x'] = float(m.group(1))
                pos['y'] = float(m.group(2))
                pos['z'] = float(m.group(3))
                return pos

        # 2D坐标（z默认为0）: (1000,2000)
        abs_2d_patterns = [
            r'在?\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'坐标\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
        ]
        for pat in abs_2d_patterns:
            m = re.search(pat, text)
            if m:
                pos['mode'] = 'absolute'
                pos['x'] = float(m.group(1))
                pos['y'] = float(m.group(2))
                pos['z'] = 0
                return pos

        # 相对坐标: "在选中的实体上方500mm" / "在当前位置前方1000"
        rel_pattern = r'在?(?:选中|当前|它|该组件)?(?:的)?\s*(上|下|左|右|前|后|上方|下方|左边|右边|前方|后方|之上|之下)\s*(\d+\.?\d*)\s*(?:mm)?'
        m = re.search(rel_pattern, text)
        if m:
            dir_text = m.group(1)
            distance = float(m.group(2))
            axis, sign = cls.DIRECTION_MAP.get(dir_text, ('z', 1))
            pos['mode'] = 'relative'
            pos['axis'] = axis
            pos['distance'] = distance * sign
            return pos

        # 检测"选中"关键词（位置模式为 selected，坐标后续从选中实体读取）
        if '选中' in text or '当前' in text:
            pos['mode'] = 'selected'
            return pos

        return pos

    @classmethod
    def _extract_array(cls, text):
        """提取阵列参数"""
        # 线性阵列：沿X轴每隔10mm生成一个圆柱，共5个 / 沿X轴生成5个圆柱，每隔10mm一个
        linear_pat = r'沿\s*([xyzXYZ])\s*轴?'
        m = re.search(linear_pat, text)
        if m:
            axis = m.group(1).lower()
            spacing, count = cls._extract_route_spacing(text)
            # 如果没找到数量，再单独尝试“N个”
            if count is None:
                count_m = re.search(r'(\d+)\s*个', text)
                if count_m:
                    count = int(count_m.group(1))
            if spacing is not None or count is not None:
                # 默认间距 1000mm
                if spacing is None:
                    spacing = 1000.0
                # 默认数量 2
                if count is None:
                    count = 2
                return {
                    'mode': 'linear',
                    'axis': axis,
                    'spacing': float(spacing),
                    'count': int(count),
                }

        # 矩形阵列
        rect_patterns = [
            r'(\d+)\s*×\s*(\d+)\s*(?:方阵|阵列)',
            r'(\d+)\s*行\s*(\d+)\s*列',
        ]
        for pat in rect_patterns:
            m = re.search(pat, text)
            if m:
                rows = int(m.group(1))
                cols = int(m.group(2))
                # 尝试提取间距
                spacing_pat = r'间距\s*(\d+\.?\d*)\s*(?:mm)?'
                sm = re.search(spacing_pat, text)
                spacing = float(sm.group(1)) if sm else 1000
                return {
                    'mode': 'rectangular',
                    'rows': rows,
                    'cols': cols,
                    'row_spacing': spacing,
                    'col_spacing': spacing,
                }

        return None

    @classmethod
    def _extract_route(cls, text):
        """
        提取路线信息（沿路线布置）。
        返回: {
            'mode': 'line' | 'selected_line' | 'selected_curve' | 'arc',
            'start': (x,y,z) or None,
            'end': (x,y,z) or None,
            'center': (x,y,z) or None,
            'radius': float or None,
            'start_angle': float or None,
            'end_angle': float or None,
            'axis': 'x'|'y'|'z' or None,
            'length': float or None,
            'spacing': float or None,
            'count': int or None,
        } or None
        """
        spacing, count = cls._extract_route_spacing(text)

        # 0. 选中的曲线（参数化曲线组件或原始曲线），必须出现“选中/当前/该”+“曲线/圆弧”
        if re.search(r'(?:沿|沿着)\s*(?:选中|当前|该)', text) and ('曲线' in text or '圆弧' in text):
            if spacing or count:
                return {'mode': 'selected_curve', 'start': None, 'end': None,
                        'center': None, 'radius': None, 'start_angle': None, 'end_angle': None,
                        'axis': None, 'length': None, 'spacing': spacing, 'count': count}

        # 1. 显式圆弧：圆心(0,0,0)半径500从0°到180°的圆弧
        arc_center_3d = r'圆心\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)'
        arc_center_2d = r'圆心\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)'
        arc_radius = r'半径\s*(\d+\.?\d*)'
        arc_angles = r'从\s*(-?\d+\.?\d*)\s*[°度]\s*到\s*(-?\d+\.?\d*)\s*[°度]'
        if '圆弧' in text or '圆心' in text:
            m_center = re.search(arc_center_3d, text) or re.search(arc_center_2d, text)
            m_radius = re.search(arc_radius, text)
            m_angles = re.search(arc_angles, text)
            if m_center and m_radius and m_angles:
                if m_center.re.pattern == arc_center_3d:
                    center = tuple(float(m_center.group(i)) for i in range(1, 4))
                else:
                    center = (float(m_center.group(1)), float(m_center.group(2)), 0.0)
                radius = float(m_radius.group(1))
                start_angle = float(m_angles.group(1))
                end_angle = float(m_angles.group(2))
                axis = cls._extract_axis_hint(text) or 'z'
                return {'mode': 'arc', 'start': None, 'end': None,
                        'center': center, 'radius': radius,
                        'start_angle': start_angle, 'end_angle': end_angle,
                        'axis': axis, 'length': None, 'spacing': spacing, 'count': count}

        # 2. 直线路线：从(0,0,0)到(100000,0,0)
        line_pat = r'(?:从|起点)?\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)\s*到\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)'
        m = re.search(line_pat, text)
        if m:
            start = tuple(float(m.group(i)) for i in range(1, 4))
            end = tuple(float(m.group(i)) for i in range(4, 7))
            spacing, count = cls._extract_route_spacing(text)
            return {'mode': 'line', 'start': start, 'end': end, 'axis': None, 'length': None, 'spacing': spacing, 'count': count}

        # 2. 沿某轴的直线，长度："沿X轴长度100m的直线"
        axis_len_pat = r'沿\s*([xyz])\s*轴?\s*(?:长度|长)?\s*(\d+\.?\d*)\s*(?:m|米|mm)?\s*(?:的?直线|路线)'
        m = re.search(axis_len_pat, text)
        if m:
            axis = m.group(1)
            length = cls._parse_length_with_unit(m.group(2), text)
            start = (0.0, 0.0, 0.0)
            if axis == 'x':
                end = (start[0] + length, start[1], start[2])
            elif axis == 'y':
                end = (start[0], start[1] + length, start[2])
            else:
                end = (start[0], start[1], start[2] + length)
            spacing, count = cls._extract_route_spacing(text)
            return {'mode': 'line', 'start': start, 'end': end, 'axis': axis, 'length': length, 'spacing': spacing, 'count': count}

        # 3. 通用"长度100m的直线" / "长度为100m的直线" / "100m长的直线" / "直线长度100m"，未指定轴默认 X
        generic_len_pats = [
            r'(?:长度|长)\s*为?\s*(\d+\.?\d*)\s*(?:m|米|mm)?\s*(?:的?直线|路线)',
            r'(\d+\.?\d*)\s*(?:m|米|mm)?\s*(?:长|长度)\s*(?:的?直线|路线)',
            r'(?:直线|路线)\s*(?:长度|长)\s*为?\s*(\d+\.?\d*)\s*(?:m|米|mm)?',
        ]
        for pat in generic_len_pats:
            m = re.search(pat, text)
            if m:
                length = cls._parse_length_with_unit(m.group(1), text)
                axis = cls._extract_axis_hint(text) or 'x'
                start = (0.0, 0.0, 0.0)
                if axis == 'x':
                    end = (start[0] + length, start[1], start[2])
                elif axis == 'y':
                    end = (start[0], start[1] + length, start[2])
                else:
                    end = (start[0], start[1], start[2] + length)
                spacing, count = cls._extract_route_spacing(text)
                return {'mode': 'line', 'start': start, 'end': end, 'axis': axis, 'length': length, 'spacing': spacing, 'count': count}

        # 4. 沿 BIMBase 中已选中的线（仅当明确出现"选中/当前/该"时才读取 BIMBase 选中实体）
        if re.search(r'(?:沿|沿着)\s*(?:选中|当前|该)', text) and ('线' in text or '路线' in text):
            spacing, count = cls._extract_route_spacing(text)
            if spacing or count:
                return {'mode': 'selected_line', 'start': None, 'end': None, 'axis': None, 'length': None, 'spacing': spacing, 'count': count}

        # 5. 仅"沿路线"且带间距/数量，使用默认直线
        if '沿路线' in text or '沿着路线' in text:
            spacing, count = cls._extract_route_spacing(text)
            if spacing or count:
                return {'mode': 'line', 'start': None, 'end': None, 'axis': 'x', 'length': 100000.0, 'spacing': spacing, 'count': count}

        return None

    @classmethod
    def _extract_route_spacing(cls, text):
        """提取路线布置间距或数量（两者可同时存在）"""
        spacing = None
        count = None

        # 每隔 X mm/m/米
        spacing_pat = r'(?:每隔|间距|间隔)\s*(\d+\.?\d*)\s*(?:m|米|mm)?'
        m = re.search(spacing_pat, text)
        if m:
            spacing = cls._parse_length_with_unit(m.group(1), text)

        # 共 N 个
        count_pat = r'(?:共|生成)\s*(\d+)\s*个'
        m = re.search(count_pat, text)
        if m:
            count = int(m.group(1))

        return spacing, count

    @classmethod
    def _extract_axis_hint(cls, text):
        """从文本中提取轴线提示"""
        if re.search(r'[xyz]\s*轴', text):
            m = re.search(r'([xyz])\s*轴', text)
            return m.group(1)
        return None

    @classmethod
    def _parse_length_with_unit(cls, num_str, text):
        """把带单位的数字转为 mm"""
        val = float(num_str)
        # 如果数字后紧跟 m/米（且不是 mm），且数值较小（<10000），认为是米，转 mm
        if re.search(re.escape(num_str) + r'\s*(?:m|米)(?!m)', text) and val < 10000:
            val *= 1000
        return val

    @classmethod
    def _parse_target(cls, text):
        """解析修改/删除的目标"""
        if '选中' in text or '当前' in text:
            return {'mode': 'selected'}
        # 检测 "第N个"
        m = re.search(r'第\s*(\d+)\s*个', text)
        if m:
            return {'mode': 'index', 'index': int(m.group(1)) - 1}
        # 检测 "最后一个"
        if '最后一个' in text or '最近一个' in text:
            return {'mode': 'last'}
        # 默认选中
        return {'mode': 'selected'}
