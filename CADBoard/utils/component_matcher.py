# -*- coding: utf-8 -*-
"""
识别结果 ↔ 本地组件模板匹配器

把多模态 LLM 返回的松散 JSON 转换为 CADBoard 可用的组件类型与参数。
"""

from typing import Dict, Tuple, Any


# 引桥桥墩默认参数（与 bimbase_sync.ApproachPierComponent.DEFAULT_PARAMS 保持一致）
APPROACH_PIER_DEFAULTS = {
    '盖梁总长': 1930.0,
    '盖梁总高': 300.0,
    '盖梁宽': 300.0,
    '墩柱直径': 250.0,
    '墩柱间距': 1140.0,
    '墩高': 1200.0,
    '系梁根数': 2,
}

# 索缆锚锭默认参数（与 bimbase_sync.CableAnchorComponent.DEFAULT_PARAMS 保持一致）
CABLE_ANCHOR_DEFAULTS = {
    '锚块总长': 5450.0,
    '锚块总高': 2039.0,
    '锚块宽度': 1200.0,
    '承台长度': 5680.0,
    '承台宽度': 1600.0,
    '承台高度': 400.0,
    '底柱半径': 170.0,
    '底柱高度': 1000.0,
    '底柱数量': 7.0,
    '底柱排数': 2.0,
    '系梁数量': 0.0,
}

# 门式桥墩默认参数（与 组件测试/门式桥墩.py 保持一致）
GATE_PIER_DEFAULTS = {
    '盖梁总长': 4700.0,
    '盖梁总高': 400.0,
    '盖梁宽': 1000.0,
    '墩高': 5000.0,
    '墩柱间距': 3500.0,
    '柱顶宽': 1200.0,
    '柱底宽': 1400.0,
    '柱顶厚': 1000.0,
    '柱底厚': 1200.0,
    '系梁根数': 1,
}

# 承台及桩基默认参数（与 组件测试/承台及桩基.py 保持一致）
PILE_FOUNDATION_DEFAULTS = {
    '承台长': 5500.0,
    '承台宽': 2350.0,
    '承台高': 500.0,
    '桩径': 250.0,
    '桩长': 5000.0,
    '桩间距': 630.0,
    '桩列数': 9,
    '桩排数': 4,
}


COMPONENT_TEMPLATES = {
    '引桥桥墩': {
        'display_name': '引桥桥墩',
        'default_params': dict(APPROACH_PIER_DEFAULTS),
        'required': ['盖梁总长', '盖梁总高', '盖梁宽', '墩高', '墩柱直径'],
        'optional': list(APPROACH_PIER_DEFAULTS.keys()),
    },
    '索缆锚锭': {
        'display_name': '索缆锚锭',
        'default_params': dict(CABLE_ANCHOR_DEFAULTS),
        'required': ['锚块总长', '锚块总高', '锚块宽度', '承台长度', '承台宽度'],
        'optional': list(CABLE_ANCHOR_DEFAULTS.keys()),
    },
    '门式桥墩': {
        'display_name': '门式桥墩',
        'default_params': dict(GATE_PIER_DEFAULTS),
        'required': ['盖梁总长', '盖梁总高', '盖梁宽', '墩高', '墩柱间距'],
        'optional': list(GATE_PIER_DEFAULTS.keys()),
    },
    '承台及桩基': {
        'display_name': '承台及桩基',
        'default_params': dict(PILE_FOUNDATION_DEFAULTS),
        'required': ['承台长', '承台宽', '承台高', '桩径', '桩长'],
        'optional': list(PILE_FOUNDATION_DEFAULTS.keys()),
    },
}


def _normalize_value(raw: Any) -> Tuple[float, str]:
    """从 LLM 可能返回的多种形式中提取数值与单位。"""
    unit = 'mm'
    value = None

    if isinstance(raw, dict):
        value = raw.get('value')
        unit = raw.get('unit', 'mm')
    elif isinstance(raw, (int, float)):
        value = raw
    elif isinstance(raw, str):
        s = raw.strip().replace(',', '')
        # 尝试提取尾部单位
        import re
        m = re.search(r'([\d\.]+)\s*([a-zA-Z]*)', s)
        if m:
            try:
                value = float(m.group(1))
            except ValueError:
                value = None
            u = m.group(2).lower()
            if u in ('mm', 'cm', 'm'):
                unit = u
    if value is None:
        try:
            value = float(raw)
        except Exception:
            value = None
    return value, unit


def _convert_to_mm(value: float, unit: str) -> float:
    """统一转换为毫米。"""
    unit = (unit or 'mm').lower()
    if unit == 'm':
        return value * 1000.0
    if unit == 'cm':
        return value * 10.0
    return value


def match_recognized_result(recognized: Dict, component_hint: str = None) -> Tuple[str, Dict, float, str]:
    """
    将 LLM 返回结果匹配为本地组件参数。

    返回: (component_type, params, confidence, notes)
    """
    comp_type = recognized.get('component_type', '') or component_hint or ''
    comp_type = comp_type.strip()

    # 名称归一化（注意顺序：先判门式，避免 '门式桥墩' 落入 '桥墩'→引桥桥墩；
    # 承台/桩基分支排除含 '锚' 的名称，避免影响 '锚'→索缆锚锭）
    if '门式' in comp_type or comp_type.lower() in ('gate pier', 'portal pier'):
        comp_type = '门式桥墩'
    elif '桥墩' in comp_type or comp_type.lower() in ('pier', 'approach pier'):
        comp_type = '引桥桥墩'
    if ('承台' in comp_type or '桩基' in comp_type) and '锚' not in comp_type:
        comp_type = '承台及桩基'
    if '锚锭' in comp_type or '锚' in comp_type or comp_type.lower() in ('anchor', 'cable anchor'):
        comp_type = '索缆锚锭'

    confidence = float(recognized.get('confidence', 0.0) or 0.0)
    notes = recognized.get('notes', '') or ''

    if comp_type not in COMPONENT_TEMPLATES:
        # 类型识别失败且提供了明确提示时，回退到提示类型
        if component_hint and component_hint in COMPONENT_TEMPLATES:
            comp_type = component_hint
            notes = (notes + f"\n注意：AI 返回的 component_type 无法识别（'{recognized.get('component_type', '')}'），已按提示类型 '{component_hint}' 处理。").strip()
        else:
            return '', {}, confidence, f"未识别的构件类型: {comp_type}"

    template = COMPONENT_TEMPLATES[comp_type]
    params = dict(template['default_params'])

    # 识别结果中的参数字段可能是平铺或嵌套 {value, unit}
    candidate_params = recognized.get('parameters', {}) or recognized

    filled = []
    for key in template['optional']:
        if key in candidate_params:
            raw = candidate_params[key]
            value, unit = _normalize_value(raw)
            if value is not None:
                params[key] = _convert_to_mm(value, unit)
                filled.append(key)

    # 对缺失的关键必填参数做提示
    missing = [k for k in template['required'] if k not in filled]
    if missing:
        notes = (notes + f"\n注意：以下关键参数未识别到，已使用默认值：{', '.join(missing)}").strip()

    return comp_type, params, confidence, notes
