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


COMPONENT_TEMPLATES = {
    '引桥桥墩': {
        'display_name': '引桥桥墩',
        'default_params': dict(APPROACH_PIER_DEFAULTS),
        'required': ['盖梁总长', '盖梁总高', '盖梁宽', '墩高', '墩柱直径'],
        'optional': list(APPROACH_PIER_DEFAULTS.keys()),
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

    # 名称归一化
    if '桥墩' in comp_type or comp_type.lower() in ('pier', 'approach pier'):
        comp_type = '引桥桥墩'

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
