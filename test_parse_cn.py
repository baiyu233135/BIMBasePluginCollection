import re

class LocalCommandParser:
    ELEMENT_MAP = {
        '圆': 'circle', '圆形': 'circle', 'circle': 'circle', 'c': 'circle',
        '矩形': 'rectangle', '长方形': 'rectangle', 'rect': 'rectangle', 'rec': 'rectangle',
        '直线': 'line', '线段': 'line', 'line': 'line', 'l': 'line',
        '圆弧': 'arc', 'arc': 'arc', 'a': 'arc',
        '多段线': 'polyline', 'pline': 'polyline', 'pl': 'polyline',
        '多边形': 'polygon', 'polygon': 'polygon',
        '椭圆': 'ellipse', 'ellipse': 'ellipse',
        '点': 'point', 'point': 'point', 'po': 'point',
        '样条': 'spline', 'spline': 'spline',
        '圆柱': '圆柱', '圆柱体': '圆柱',
        '正方体': '正方体', '立方体': '正方体',
        '长方体': '长方体', '拉伸体': '长方体',
        '球体': '球体', 'sphere': '球体', '球': '球体',
        '直角三棱柱': '直角三棱柱', '三棱柱': '直角三棱柱',
        '引桥桥墩': '引桥桥墩', '桥墩': '引桥桥墩',
        '索缆锚锭': '索缆锚锭', '锚锭': '索缆锚锭',
    }
    ACTION_MAP = {
        '画': 'draw', '绘制': 'draw', '创建': 'draw', '画一个': 'draw',
        '删除': 'delete', '移除': 'delete', 'del': 'delete', 'erase': 'delete',
        '复制': 'copy', '拷贝': 'copy', 'co': 'copy',
        '移动': 'move',
        '旋转': 'rotate', 'ro': 'rotate',
        '缩放': 'scale', 'sc': 'scale',
        '镜像': 'mirror', 'mi': 'mirror',
        '偏移': 'offset',
        '拉伸': 'stretch',
        '修剪': 'trim', 'tr': 'trim',
        '延伸': 'extend', 'ex': 'extend',
        '圆角': 'fillet',
        '倒角': 'chamfer', '倒斜角': 'chamfer', 'cha': 'chamfer',
        '阵列': 'array', 'ar': 'array',
        '打断': 'break', 'br': 'break',
        '合并': 'join',
        '分解': 'explode',
        '同步': 'sync',
    }
    FACE_NAME_MAP = {
        '顶面': 'top', 'top': 'top', '俯视图': 'top', '上面': 'top',
        '前视图': 'side_a', 'side_a': 'side_a', '侧面a': 'side_a', '前视': 'side_a',
        '左视图': 'side_b', 'side_b': 'side_b', '侧面b': 'side_b', '左视': 'side_b',
        '底面': 'bottom', 'bottom': 'bottom',
        '所有面': 'all', '全部面': 'all', 'all': 'all',
    }
    AXIS_MAP = {'x轴': 'x', 'y轴': 'y', 'z轴': 'z', 'x': 'x', 'y': 'y', 'z': 'z'}
    SOLID_TYPES = {'圆柱', '正方体', '长方体', '球体', '直角三棱柱', '引桥桥墩', '索缆锚锭'}
    _CN_NUMBERS = {
        '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    }

    @classmethod
    def _parse_value_str(cls, val_str):
        val_str = str(val_str).strip()
        if val_str in cls._CN_NUMBERS:
            return float(cls._CN_NUMBERS[val_str])
        return float(val_str)

    @classmethod
    def _extract_position(cls, text):
        patterns = [
            r'(?:放在|在|坐标|位置|同步到|到)\s*(?:bimbase\s*)?\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'(?:放在|在|坐标|位置|同步到|到)\s*(?:bimbase\s*)?\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'(?:放在|在|坐标|位置|同步到|到)\s*(?:bimbase\s*)?(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',
            r'(?:放在|在|坐标|位置|同步到|到)\s*(?:bimbase\s*)?(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',
            r'\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                pos = {'x': float(m.group(1)), 'y': float(m.group(2))}
                if m.lastindex >= 3:
                    pos['z'] = float(m.group(3))
                return pos
        return None

    @classmethod
    def parse(cls, text):
        text = text.strip().lower().replace('，', ',').replace('（', '(').replace('）', ')')
        if '重新生成面' in text or 'regenerate face' in text or '生成面' in text:
            return {'action': 'agent', 'tool': 'regenerate_faces', 'params': {}}
        if '应用面修改' in text or 'apply face' in text:
            return {'action': 'agent', 'tool': 'apply_face_changes', 'params': {}}
        if '查询状态' in text or 'query state' in text or '状态' in text:
            return {'action': 'agent', 'tool': 'query_state', 'params': {}}
        if '退出面编辑' in text or '退出面' in text:
            return {'action': 'agent', 'tool': 'exit_face_edit', 'params': {}}
        axis_cmd = cls._parse_axis_create(text)
        if axis_cmd:
            return axis_cmd
        action = None
        for cn, en in cls.ACTION_MAP.items():
            if cn.lower() in text:
                action = en
                break
        if not action:
            return cls._parse_modify(text)
        if action == 'delete':
            target = cls._parse_target(text)
            return {'action': 'delete', 'target': target}
        if '同步' in text or 'sync' in text:
            modify_cmd = cls._parse_modify(text)
            if modify_cmd:
                params = modify_cmd.get('params', {})
                if params.get('changes') or params.get('position'):
                    return modify_cmd
                if modify_cmd.get('changes') or modify_cmd.get('position'):
                    return modify_cmd
            result = {'action': 'sync'}
            position = cls._extract_position(text)
            if position:
                result['position'] = position
            return result
        elem_type = None
        for cn, cmd in cls.ELEMENT_MAP.items():
            if cn.lower() in text:
                elem_type = cmd
                break
        if action == 'draw' and not elem_type:
            return None
        if action != 'draw' and not elem_type:
            return {'action': action, 'params': {}}
        params = cls._extract_params(text)
        return {'action': 'create' if action == 'draw' else action, 'element': elem_type, 'params': params}

    @classmethod
    def _parse_axis_create(cls, text):
        return None

    @classmethod
    def _extract_params(cls, text):
        return {}

    @classmethod
    def _parse_modify(cls, text):
        position = cls._extract_position(text)
        _VAL = r'([+-]?(?:\d+\.?\d*|[一二两三四五六七八九十]+))'
        pat_with_de = rf'(?:把|将|让)\s*(.+?)\s*的\s*(\S+?)\s*(?:改成|变成|设为|改为|增加|加长|加宽|加高|加大|减少|缩短|减小)\s*{_VAL}'
        m = re.search(pat_with_de, text)
        if m:
            target_text = m.group(1).strip()
            prop_text = m.group(2).strip()
            val_str = m.group(3).strip()
        else:
            pat_without_de = rf'(?:把|将|让)\s*(.*?)\s*(?:改成|变成|设为|改为|增加|加长|加宽|加高|加大|减少|缩短|减小)\s*{_VAL}'
            m = re.search(pat_without_de, text)
            if m:
                combined_text = m.group(1).strip()
                val_str = m.group(2).strip()
                target_text, prop_text = cls._split_target_prop(combined_text)
            else:
                prop_only_pat = rf'(高度|宽度|半径|长度|大小|深度|厚度|边长|直角边1|直角边2|h|a|b|r|墩高|盖梁总长|盖梁总高|盖梁宽|墩柱直径|墩柱间距|系梁根数|系梁数量|锚块总长|锚块总高|锚块宽度|承台长度|承台宽度|承台高度|底柱半径|底柱高度|底柱数量|底柱排数|底柱|低柱半径|低柱高度|低柱数量|低柱排数)\s*(?:改成|变成|设为|改为|增加|加长|加宽|加高|加大|减少|缩短|减小)\s*{_VAL}'
                m = re.search(prop_only_pat, text)
                if m:
                    target_text = ''
                    prop_text = m.group(1).strip()
                    val_str = m.group(2).strip()
                else:
                    return None
        target = cls._parse_target_text(target_text)
        prop = cls._parse_property_text(prop_text)
        if not prop:
            return None
        changes = {prop: cls._parse_value_str(val_str)}
        if 'component_type' in target or 'component' in target:
            agent_params = {'target': target, 'changes': changes, 'path': 'auto'}
            if position:
                agent_params['position'] = position
            return {'action': 'agent', 'tool': 'modify_component', 'params': agent_params}
        COMPLEX_PARAMS = {
            '墩高', '盖梁总长', '盖梁总高', '盖梁宽', '墩柱直径', '墩柱间距', '系梁根数',
            '锚块总长', '锚块总高', '锚块宽度', '承台长度', '承台宽度', '承台高度',
            '底柱半径', '底柱高度', '底柱数量', '底柱排数', '系梁数量',
        }
        if prop in COMPLEX_PARAMS:
            agent_params = {'target': {'component': True}, 'changes': changes, 'path': 'auto'}
            if position:
                agent_params['position'] = position
            return {'action': 'agent', 'tool': 'modify_component', 'params': agent_params}
        GEOM_PARAMS = {'width', 'height', 'radius', 'depth', 'size', 'length', 'thickness', 'a', 'b', 'h'}
        if prop in GEOM_PARAMS:
            agent_params = {'target': target, 'changes': changes, 'path': 'auto'}
            if position:
                agent_params['position'] = position
            return {'action': 'agent', 'tool': 'modify_component', 'params': agent_params}
        result = {'action': 'modify', 'target': target, 'changes': changes}
        if position:
            result['position'] = position
        return result

    @classmethod
    def _split_target_prop(cls, combined_text):
        if not combined_text:
            return '', ''
        cn_props = [
            '高度', '长度', '宽度', '深度', '半径', '厚度', '颜色', '线宽', '线型', '边长',
            '墩高', '盖梁总长', '盖梁总高', '盖梁宽', '墩柱直径', '墩柱间距', '系梁根数', '系梁数量',
            '锚块总长', '锚块总高', '锚块宽度', '承台长度', '承台宽度', '承台高度',
            '底柱半径', '底柱高度', '底柱数量', '底柱排数', '低柱半径', '低柱高度', '低柱数量', '低柱排数',
            '底柱',
        ]
        for prop in sorted(cn_props, key=len, reverse=True):
            if combined_text.endswith(prop):
                return combined_text[:-len(prop)].strip(), prop
            if combined_text.startswith(prop):
                return combined_text[len(prop):].strip(), prop
        en_props = ['height', 'width', 'length', 'depth', 'radius', 'thickness', 'color', 'size']
        text_lower = combined_text.lower()
        for prop in sorted(en_props, key=len, reverse=True):
            if text_lower.endswith(prop):
                return combined_text[:-len(prop)].strip(), prop
            if text_lower.startswith(prop):
                return combined_text[len(prop):].strip(), prop
        return combined_text, ''

    @classmethod
    def _parse_target_text(cls, text):
        text = text.strip()
        order_match = re.search(r'第\s*(\d+)\s*个', text)
        if order_match:
            idx = int(order_match.group(1)) - 1
            elem_type = None
            for cn, cmd in cls.ELEMENT_MAP.items():
                if cn.lower() in text:
                    elem_type = cmd
                    break
            if elem_type:
                if elem_type in cls.SOLID_TYPES:
                    return {'component_type': elem_type, 'index': idx}
                return {'element_type': elem_type, 'index': idx}
            return {'index': idx}
        for cn, face_name in cls.FACE_NAME_MAP.items():
            if cn.lower() in text:
                return {'face_name': face_name}
        component_type_map = {
            '三棱柱': '直角三棱柱', '拉伸盒': 'SweepBoxComponent',
            '圆柱': '圆柱', '正方体': '正方体', '长方体': '长方体',
            '多边形': 'Polygon3DComponent', '圆弧': 'Arc3DComponent',
            '椭圆': 'Ellipse3DComponent', '引桥桥墩': '引桥桥墩',
            '桥墩': '引桥桥墩', '索缆锚锭': '索缆锚锭',
        }
        for cn, ct in component_type_map.items():
            if cn in text:
                return {'component_type': ct}
        if '组件' in text or '源组件' in text:
            return {'component': True}
        if '选中' in text:
            return {'index': 'selected'}
        for cn, cmd in cls.ELEMENT_MAP.items():
            if cn.lower() in text:
                return {'element_type': cmd}
        return {'index': 'selected'}

    @classmethod
    def _parse_property_text(cls, text):
        complex_params = {
            '墩高': '墩高',
            '盖梁总长': '盖梁总长', '盖梁总高': '盖梁总高', '盖梁宽': '盖梁宽',
            '墩柱直径': '墩柱直径', '墩柱间距': '墩柱间距',
            '系梁根数': '系梁根数', '系梁数量': '系梁根数',
            '锚块总长': '锚块总长', '锚块总高': '锚块总高', '锚块宽度': '锚块宽度',
            '承台长度': '承台长度', '承台宽度': '承台宽度', '承台高度': '承台高度',
            '底柱半径': '底柱半径', '底柱高度': '底柱高度',
            '底柱数量': '底柱数量', '底柱排数': '底柱排数',
            '低柱半径': '底柱半径', '低柱高度': '底柱高度',
            '低柱数量': '底柱数量', '低柱排数': '底柱排数',
            '底柱': '底柱排数',
        }
        for cn in sorted(complex_params.keys(), key=len, reverse=True):
            if cn in text:
                return complex_params[cn]
        prop_map = {
            '长': 'width', '长度': 'width', 'length': 'width',
            '宽': 'width', '宽度': 'width', 'width': 'width',
            '高': 'height', '高度': 'height', 'height': 'height',
            '半径': 'radius', 'r': 'radius',
            '厚度': 'thickness',
            'x': 'x', 'y': 'y', 'cx': 'cx', 'cy': 'cy',
            'z_end': 'z_end', 'z_start': 'z_start',
            '颜色': 'color', 'color': 'color',
            '线宽': 'line_width', '线型': 'line_type',
            'a': 'a', 'b': 'b', 'h': 'h',
        }
        for cn in sorted(prop_map.keys(), key=len, reverse=True):
            if cn in text:
                return prop_map[cn]
        return text

texts = [
    '把这个组件的底柱改为一，并同步到bimbase(985,211,951)的位置',
    '把低柱排数改为一，同步到bimbase(800,200,986)的位置',
    '把这个组件的底柱排数改为1',
]
for t in texts:
    print(repr(t), '->', LocalCommandParser.parse(t))
