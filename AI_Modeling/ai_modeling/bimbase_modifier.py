# -*- coding: utf-8 -*-
"""
BIMBase 已有组件修改器
通过 noumenon + replace 或 replace_noumenon 修改/替换已有实例
"""
import sys
import os

_plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)


def _log(msg):
    try:
        log_path = os.path.join(_plugin_dir, 'ai_modeling_debug.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        pass


_pyp3d_ok = False
get_all_instancekey = None
get_noumKV_from_instancekey = None
get_noumenon_from_instancekey = None
get_noumenon_on_entityid = None
get_noumenon_from_datakey = None
get_datakey_from_entity = None
get_entityid_from_boxselection = None
get_current_entityId = None
entityid_isvaid = None
entityid_isvalid = None
get_selections = None
get_element_from_boxselect = None
replace_noumenon = None
get_entity_property = None
get_entity_bounds = None

# 逐个从 pyp3d 导入，避免某个 API 不存在导致全部失败
try:
    import pyp3d
    _pyp3d_ok = True
    _api_names = [
        'get_all_instancekey',
        'get_noumKV_from_instancekey',
        'get_noumenon_from_instancekey',
        'get_noumenon_on_entityid',
        'get_noumenon_from_datakey',
        'get_datakey_from_entity',
        'get_entityid_from_boxselection',
        'get_current_entityId',
        'entityid_isvaid',
        'entityid_isvalid',
        'get_selections',
        'get_element_from_boxselect',
        'replace_noumenon',
        'get_entity_property',
        'get_entity_bounds',
    ]
    for _name in _api_names:
        try:
            globals()[_name] = getattr(pyp3d, _name)
        except Exception as _e:
            _log(f"bimbase_modifier import {_name} failed: {_e}")
            globals()[_name] = None
except Exception as _e:
    _log(f"bimbase_modifier import pyp3d failed: {_e}")
    _pyp3d_ok = False

from ai_modeling.component_factory import create_component, COMPONENT_CLASSES


def _is_entity_valid(eid):
    if eid is None:
        return False
    if entityid_isvaid is not None:
        try:
            return bool(entityid_isvaid(eid))
        except Exception:
            pass
    if entityid_isvalid is not None:
        try:
            return bool(entityid_isvalid(eid))
        except Exception:
            pass
    return True


def get_selected_instance_keys():
    """
    获取用户在 BIMBase 中选中的实体对应的 instance keys
    返回: list of instance_key 或 []
    """
    keys = []
    if not _pyp3d_ok:
        return keys

    entity_ids = []
    if get_selections is not None:
        try:
            sel = get_selections()
            if sel:
                entity_ids = list(sel) if not isinstance(sel, (list, tuple)) else list(sel)
        except Exception as e:
            _log(f"get_selections error: {e}")
    if not entity_ids and get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
        except Exception as e:
            _log(f"get_entityid_from_boxselection error: {e}")
    if not entity_ids and get_current_entityId is not None:
        try:
            cur_id = get_current_entityId()
            if cur_id:
                entity_ids = [cur_id]
        except Exception as e:
            _log(f"get_current_entityId error: {e}")

    for eid in entity_ids:
        if not _is_entity_valid(eid):
            continue
        dk = get_datakey_from_entity(eid) if get_datakey_from_entity else None
        if dk is not None:
            keys.append(dk)

    return keys


def get_instance_params(instance_key):
    """获取指定实例的参数字典"""
    if not _pyp3d_ok or get_noumKV_from_instancekey is None:
        return None
    try:
        return get_noumKV_from_instancekey(instance_key)
    except Exception as e:
        _log(f"get_instance_params error: {e}")
        return None


def infer_component_type_from_params(params):
    """从参数字典推断组件类型"""
    if not params:
        return None
    keys = set(params.keys())
    if '半径' in keys and '高度' in keys and '边长' not in keys:
        return 'cylinder'
    if '长度' in keys and '宽度' in keys and '高度' in keys:
        return 'box'
    if '边长' in keys:
        return 'cube'
    if '半径' in keys and '高度' not in keys and '边长' not in keys:
        return 'sphere'
    if '底面半径' in keys and '高度' in keys:
        return 'cone'
    # 英文键兼容
    if 'radius' in keys and 'height' in keys:
        return 'cylinder'
    if 'length' in keys and 'width' in keys and 'height' in keys:
        return 'box'
    if 'size' in keys:
        return 'cube'
    return None


def modify_instance_by_key(instance_key, changes):
    """
    通过 instance_key 修改已有组件参数
    changes: dict，如 {'半径': 200, '高度': 500}
    返回: (success: bool, message: str)
    """
    if not _pyp3d_ok:
        return False, "pyp3d 未加载"

    # 方式1：优先使用 replace_noumenon（如果有）
    if replace_noumenon is not None:
        try:
            old_params = get_instance_params(instance_key)
            comp_type = infer_component_type_from_params(old_params)
            if not comp_type:
                return False, "无法推断组件类型"

            # 合并新参数
            new_params = dict(old_params) if old_params else {}
            for k, v in changes.items():
                new_params[k] = v

            # 创建新组件
            comp = create_component(comp_type, new_params)
            if comp is None:
                return False, "创建新组件失败"

            replace_noumenon(comp, instance_key)
            return True, f"已替换组件参数: {changes}"
        except Exception as e:
            _log(f"replace_noumenon error: {e}")
            # 回退到方式2

    # 方式2：get_noumenon_from_instancekey + 修改 + replace()
    if get_noumenon_from_instancekey is not None:
        try:
            noum = get_noumenon_from_instancekey(instance_key)
            if noum is None:
                return False, "无法获取组件本体"

            modified = False
            for k, v in changes.items():
                try:
                    noum[k] = v
                    modified = True
                except Exception as e2:
                    _log(f"  set {k} failed: {e2}")

            if modified and hasattr(noum, 'replace'):
                noum.replace()
                return True, f"已修改组件参数: {changes}"
            else:
                return False, "参数修改未生效"
        except Exception as e:
            return False, f"修改失败: {e}"

    return False, "没有可用的修改 API"


def modify_selected_component(changes):
    """
    修改当前选中的组件
    changes: dict，如 {'半径': 200}
    返回: (success: bool, message: str)
    """
    keys = get_selected_instance_keys()
    if not keys:
        return False, "未在 BIMBase 中选中任何组件，请先选中要修改的组件"

    results = []
    for ik in keys:
        ok, msg = modify_instance_by_key(ik, changes)
        results.append((ok, msg))

    success_count = sum(1 for ok, _ in results if ok)
    return success_count > 0, f"修改 {success_count}/{len(keys)} 个组件"


def get_selected_component_info():
    """
    获取当前选中组件的信息列表
    返回: [{
        'instance_key': key,
        'type': 'cylinder'|'box'|...,
        'params': {...},
    }, ...]
    """
    infos = []
    keys = get_selected_instance_keys()
    for ik in keys:
        params = get_instance_params(ik)
        comp_type = infer_component_type_from_params(params)
        infos.append({
            'instance_key': ik,
            'type': comp_type,
            'params': params,
        })
    return infos


def _find_id_attr(obj, kind):
    """安全地从对象中读取 ID 属性（kind='model' 或 'element'）"""
    if obj is None:
        return None
    if kind == 'model':
        candidates = ['ModelId', '_ModelId', 'model_id', '_model_id', 'modelid']
    else:
        candidates = ['ElementId', '_ElementId', 'element_id', '_element_id', 'elementid']
    for name in candidates:
        try:
            val = getattr(obj, name, None)
            if val is not None:
                return val
        except Exception:
            continue
    # 若仍失败，用 dir 再扫一次
    try:
        names = dir(obj)
        for name in names:
            low = name.lower().replace('_', '')
            if (kind == 'model' and low == 'modelid') or (kind == 'element' and low == 'elementid'):
                try:
                    val = getattr(obj, name, None)
                    if val is not None:
                        return val
                except Exception:
                    continue
    except Exception as e:
        _log(f"_find_id_attr dir error: {e}")
    return None


def _safe_entity_id(eid):
    """安全读取 entity id 的 ModelId/ElementId，避免访问异常"""
    try:
        _log(f"_safe_entity_id: eid type={type(eid).__name__}")
    except Exception as e:
        _log(f"_safe_entity_id log error: {e}")
    try:
        mid = _find_id_attr(eid, 'model')
        eid_val = _find_id_attr(eid, 'element')
        if mid is None or eid_val is None:
            _log(f"_safe_entity_id: could not read IDs, dir={dir(eid)}")
        return mid, eid_val
    except Exception as e:
        _log(f"_safe_entity_id error: {e}")
        return None, None


def _safe_instance_id(ik):
    """安全读取 instance key 的 ModelId/ElementId"""
    try:
        _log(f"_safe_instance_id: ik type={type(ik).__name__}")
    except Exception as e:
        _log(f"_safe_instance_id log error: {e}")
    try:
        mid = _find_id_attr(ik, 'model')
        eid_val = _find_id_attr(ik, 'element')
        if mid is None or eid_val is None:
            _log(f"_safe_instance_id: could not read IDs, dir={dir(ik)}")
        return mid, eid_val
    except Exception as e:
        _log(f"_safe_instance_id error: {e}")
        return None, None


import re as _re

_number_re = _re.compile(r'-?\d+\.?\d*')


def _parse_number(v):
    """从 float/int/Attr/带单位字符串中提取数值"""
    if v is None:
        return 0.0
    # 优先取 .value（Attr 对象）
    if hasattr(v, 'value'):
        try:
            v = v.value
        except Exception:
            pass
    try:
        return float(v)
    except Exception:
        pass
    if isinstance(v, str):
        s = v.replace(',', '').strip()
        m = _number_re.search(s)
        if m:
            return float(m.group(0))
    raise ValueError(f"无法解析数值: {v!r}")


def _extract_line_endpoints_from_params(params):
    """从参数字典/Noumenon中提取线的两个端点"""
    if params is None:
        return None
    def _to_float(v):
        return _parse_number(v)
    # 英文键
    try:
        if all(k in params for k in ('x1', 'y1', 'z1', 'x2', 'y2', 'z2')):
            p1 = (_to_float(params['x1']), _to_float(params['y1']), _to_float(params['z1']))
            p2 = (_to_float(params['x2']), _to_float(params['y2']), _to_float(params['z2']))
            return p1, p2
    except Exception:
        pass
    # 中文键
    try:
        if all(k in params for k in ('起点X', '起点Y', '起点Z', '终点X', '终点Y', '终点Z')):
            p1 = (_to_float(params['起点X']), _to_float(params['起点Y']), _to_float(params['起点Z']))
            p2 = (_to_float(params['终点X']), _to_float(params['终点Y']), _to_float(params['终点Z']))
            return p1, p2
    except Exception:
        pass
    # 尝试 start_x/start_y/start_z, end_x/end_y/end_z
    try:
        if all(k in params for k in ('start_x', 'start_y', 'start_z', 'end_x', 'end_y', 'end_z')):
            p1 = (_to_float(params['start_x']), _to_float(params['start_y']), _to_float(params['start_z']))
            p2 = (_to_float(params['end_x']), _to_float(params['end_y']), _to_float(params['end_z']))
            return p1, p2
    except Exception:
        pass
    # 尝试 start/end 作为点对象（list/tuple/Vec3）
    try:
        if 'start' in params and 'end' in params:
            s = params['start']
            e = params['end']
            p1 = (float(s[0]), float(s[1]), float(s[2]))
            p2 = (float(e[0]), float(e[1]), float(e[2]))
            return p1, p2
    except Exception:
        pass
    # 尝试 p1/p2
    try:
        if 'p1' in params and 'p2' in params:
            s = params['p1']
            e = params['p2']
            p1 = (float(s[0]), float(s[1]), float(s[2]))
            p2 = (float(e[0]), float(e[1]), float(e[2]))
            return p1, p2
    except Exception:
        pass
    _log(f"_extract_line_endpoints: unsupported keys, preview={_safe_items_preview(params, 10)}")
    return None


def _read_params_from_instancekey(datakey):
    """
    从 P3DInstanceKey 读取参数字典。
    优先 get_noumKV_from_instancekey，若为空则回退到 noumenon.at('ParaCmptProperty') 或遍历 noumenon。
    """
    if datakey is None:
        return None
    params = None
    if get_noumKV_from_instancekey is not None:
        try:
            params = get_noumKV_from_instancekey(datakey)
        except Exception as e:
            _log(f"_read_params_from_instancekey noumKV error: {e}")
    if params and isinstance(params, dict) and len(params) > 0:
        return params
    if get_noumenon_from_instancekey is None:
        return None
    try:
        noum = get_noumenon_from_instancekey(datakey)
        if noum is None:
            return None
        # 尝试参数化组件属性节点
        try:
            prop = noum.at('ParaCmptProperty')
            if prop is not None:
                if hasattr(prop, 'keys'):
                    d = {}
                    for key in prop:
                        d[key] = prop[key]
                    return d
                elif isinstance(prop, dict):
                    return dict(prop)
        except Exception:
            pass
        # 回退：直接遍历 noumenon
        try:
            d = {}
            for key in noum:
                d[key] = noum[key]
            return d
        except Exception:
            pass
    except Exception as e:
        _log(f"_read_params_from_instancekey noumenon error: {e}")
    return None


def _read_params_from_noumenon(noum):
    """从 Noumenon 对象中读取参数化组件的参数字典。"""
    if noum is None:
        return None
    # 优先读取参数化组件属性节点 ParaCmptProperty
    try:
        prop = noum.at('ParaCmptProperty')
        if prop is not None:
            d = {}
            if hasattr(prop, 'keys'):
                for key in prop:
                    d[key] = prop[key]
            elif hasattr(prop, 'items'):
                for key, val in prop.items():
                    d[key] = val
            else:
                for key in prop:
                    d[key] = prop[key]
            if d:
                return d
    except Exception:
        pass
    # 回退：直接遍历 noumenon
    try:
        d = {}
        for key in noum:
            d[key] = noum[key]
        if d:
            return d
    except Exception:
        pass
    try:
        d = {}
        for key, val in noum.items():
            d[key] = val
        if d:
            return d
    except Exception:
        pass
    return None


def _read_params_from_entity(eid):
    """从选中的几何实体 entity id 直接读取参数（优先用 get_noumenon_on_entityid）。"""
    if eid is None:
        return None
    # 方式1：get_noumenon_on_entityid 直接返回实体对应的 noumenon
    if get_noumenon_on_entityid is not None:
        try:
            noum = get_noumenon_on_entityid(eid)
            params = _read_params_from_noumenon(noum)
            if params:
                _log(f"_read_params_from_entity: got params via get_noumenon_on_entityid, keys={_safe_keys(params)}")
                return params
        except Exception as e:
            _log(f"_read_params_from_entity get_noumenon_on_entityid error: {e}")
    # 方式2：datakey -> noumenon / noumKV
    if get_datakey_from_entity is not None:
        try:
            dk = get_datakey_from_entity(eid)
            if dk is not None:
                params = _read_params_from_instancekey(dk)
                if params:
                    _log(f"_read_params_from_entity: got params via datakey, keys={_safe_keys(params)}")
                    return params
                if get_noumenon_from_datakey is not None:
                    try:
                        noum = get_noumenon_from_datakey(dk)
                        params = _read_params_from_noumenon(noum)
                        if params:
                            _log(f"_read_params_from_entity: got params via get_noumenon_from_datakey, keys={_safe_keys(params)}")
                            return params
                    except Exception as e2:
                        _log(f"_read_params_from_entity get_noumenon_from_datakey error: {e2}")
        except Exception as e:
            _log(f"_read_params_from_entity datakey error: {e}")
    return None


def _extract_arc_params_from_params(params):
    """从参数字典/Noumenon中提取圆弧参数（适配 组件测试/曲线.py 的命名）。"""
    if params is None:
        return None
    try:
        keys = set(params.keys())
    except Exception:
        return None
    def _to_float(v):
        return _parse_number(v)
    try:
        required = {'圆心X', '圆心Y', '圆心Z', '半径', '起始角', '终止角'}
        if required.issubset(keys):
            return {
                'center': (_to_float(params['圆心X']), _to_float(params['圆心Y']), _to_float(params['圆心Z'])),
                'radius': _to_float(params['半径']),
                'start_angle': _to_float(params['起始角']),
                'end_angle': _to_float(params['终止角']),
                'axis': 'z',
            }
    except Exception as e:
        _log(f"_extract_arc_params_from_params chinese keys error: {e}")
    # 英文键兼容
    try:
        required_en = {'center_x', 'center_y', 'center_z', 'radius', 'start_angle', 'end_angle'}
        if required_en.issubset(keys):
            return {
                'center': (_to_float(params['center_x']), _to_float(params['center_y']), _to_float(params['center_z'])),
                'radius': _to_float(params['radius']),
                'start_angle': _to_float(params['start_angle']),
                'end_angle': _to_float(params['end_angle']),
                'axis': 'z',
            }
    except Exception as e:
        _log(f"_extract_arc_params_from_params english keys error: {e}")
    return None


def get_selected_curve_arc_params():
    """
    尝试读取 BIMBase 中当前选中曲线（参数化圆弧组件）的圆心、半径、起止角。
    返回: {'center': (x,y,z), 'radius': r, 'start_angle': a1, 'end_angle': a2, 'axis': 'z'} or None
    """
    if not _pyp3d_ok:
        _log("get_selected_curve_arc_params: pyp3d not available")
        return None

    # 收集选中的 entity id / instance key
    entity_ids = []
    if get_selections is not None:
        try:
            sel = get_selections()
            if sel:
                entity_ids = list(sel) if not isinstance(sel, (list, tuple)) else list(sel)
                _log(f"get_selected_curve_arc_params: get_selections returned {len(entity_ids)} objects")
        except Exception as e:
            _log(f"get_selected_curve_arc_params get_selections error: {e}")
    if not entity_ids and get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
            _log(f"get_selected_curve_arc_params: boxselection returned {len(entity_ids)} entities")
        except Exception as e:
            _log(f"get_selected_curve_arc_params boxselection error: {e}")
    if not entity_ids and get_current_entityId is not None:
        try:
            cur_id = get_current_entityId()
            if cur_id is not None and (entityid_isvaid is not None and entityid_isvaid(cur_id) or entityid_isvalid is not None and entityid_isvalid(cur_id)):
                entity_ids = [cur_id]
                _log(f"get_selected_curve_arc_params: current_entityId returned 1 entity")
        except Exception as e:
            _log(f"get_selected_curve_arc_params current_entityId error: {e}")

    if not entity_ids:
        _log("get_selected_curve_arc_params: no entity ids found")
        return None

    # 方式0：直接从 entity id 读取 noumenon/参数
    for eid in entity_ids:
        try:
            params = _read_params_from_entity(eid)
            arc = _extract_arc_params_from_params(params)
            if arc:
                _log(f"get_selected_curve_arc_params: found arc params from entity noumenon: {arc}")
                return arc
        except Exception as e:
            _log(f"get_selected_curve_arc_params entity read error: {e}")

    # 方式0b：直接把 entity id 当 instance key 读
    for eid in entity_ids:
        try:
            params = _read_params_from_instancekey(eid)
            arc = _extract_arc_params_from_params(params)
            if arc:
                _log(f"get_selected_curve_arc_params: found arc params from direct read")
                return arc
        except Exception as e:
            _log(f"get_selected_curve_arc_params direct read error: {e}")

    # 方式1：通过 get_selected_instance_keys() 读取 datakey 参数
    keys = get_selected_instance_keys()
    for ik in keys:
        params = _read_params_from_instancekey(ik)
        arc = _extract_arc_params_from_params(params)
        if arc:
            _log(f"get_selected_curve_arc_params: found arc params from selected instance: {arc}")
            return arc

    # 方式2：按 ModelId/ElementId 扫描所有 instance key（兼容直接点选未返回 datakey 的情况）
    target_ids = []
    for eid in entity_ids:
        mid, eid_val = _safe_entity_id(eid)
        if mid is not None and eid_val is not None:
            target_ids.append((mid, eid_val))

    if get_all_instancekey is not None and target_ids:
        try:
            all_keys = get_all_instancekey() or []
            for ik in all_keys:
                try:
                    mid, eid_val = _safe_instance_id(ik)
                    if (mid, eid_val) in target_ids:
                        params = _read_params_from_instancekey(ik)
                        arc = _extract_arc_params_from_params(params)
                        if arc:
                            _log(f"get_selected_curve_arc_params: found arc params from scanned instance: {arc}")
                            return arc
                except Exception as e:
                    _log(f"get_selected_curve_arc_params scan error: {e}")
        except Exception as e:
            _log(f"get_selected_curve_arc_params get_all_instancekey error: {e}")

    # 方式3：兜底扫描，如果场景中只有一个圆弧/曲线组件，直接使用它
    if get_all_instancekey is not None:
        try:
            arc_candidates = []
            for ik in get_all_instancekey():
                params = _read_params_from_instancekey(ik)
                if _extract_arc_params_from_params(params):
                    arc_candidates.append(ik)
            if len(arc_candidates) == 1:
                params = _read_params_from_instancekey(arc_candidates[0])
                arc = _extract_arc_params_from_params(params)
                _log(f"get_selected_curve_arc_params: fallback using the only arc component in scene: {arc}")
                return arc
            elif len(arc_candidates) > 1:
                _log(f"get_selected_curve_arc_params: fallback found {len(arc_candidates)} arc components, cannot decide")
        except Exception as e:
            _log(f"get_selected_curve_arc_params fallback scan error: {e}")

    _log("get_selected_curve_arc_params: no arc params found")
    return None


def _safe_keys(obj):
    """安全获取类字典对象的键列表"""
    try:
        if obj is None:
            return None
        if hasattr(obj, 'keys'):
            try:
                return list(obj.keys())
            except Exception:
                pass
        if hasattr(obj, 'items'):
            try:
                return [k for k, v in obj.items()]
            except Exception:
                pass
        return [k for k in obj]
    except Exception as e:
        return f"<_safe_keys error: {e}>"


def _safe_items_preview(obj, max_items=20):
    """安全获取类字典对象的前 N 个键值对（避免触发 __bool__）"""
    try:
        if obj is None:
            return None
        result = []
        if hasattr(obj, 'items'):
            try:
                for i, (k, v) in enumerate(obj.items()):
                    if i >= max_items:
                        break
                    result.append(f"{k}={v}")
                return result
            except Exception:
                pass
        if hasattr(obj, 'keys'):
            try:
                for i, k in enumerate(obj.keys()):
                    if i >= max_items:
                        break
                    result.append(f"{k}={obj[k]}")
                return result
            except Exception:
                pass
        return result
    except Exception as e:
        return [f"<_safe_items_preview error: {e}>"]


def get_selected_line_endpoints():
    """
    尝试读取 BIMBase 中当前选中线的两个端点。
    返回: ((x1,y1,z1), (x2,y2,z2)) 或 None
    """
    if not _pyp3d_ok:
        _log("get_selected_line_endpoints: pyp3d not available")
        return None

    # 收集选中的 entity id / instance key
    entity_ids = []
    # 优先使用 get_selections()（项目里 建模/test.py 用的就是这个 API）
    if get_selections is not None:
        try:
            sel = get_selections()
            if sel:
                entity_ids = list(sel) if not isinstance(sel, (list, tuple)) else list(sel)
                _log(f"get_selected_line_endpoints: get_selections returned {len(entity_ids)} objects")
        except Exception as e:
            _log(f"get_selected_line_endpoints get_selections error: {e}")
    if not entity_ids and get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
            _log(f"get_selected_line_endpoints: boxselection returned {len(entity_ids)} entities")
        except Exception as e:
            _log(f"get_selected_line_endpoints boxselection error: {e}")
    if not entity_ids and get_current_entityId is not None:
        try:
            cur_id = get_current_entityId()
            _log(f"get_selected_line_endpoints: current_entityId type={type(cur_id).__name__}")
            if cur_id is not None and (entityid_isvaid is not None and entityid_isvaid(cur_id) or entityid_isvalid is not None and entityid_isvalid(cur_id)):
                entity_ids = [cur_id]
        except Exception as e:
            _log(f"get_selected_line_endpoints current_entityId error: {e}")

    if not entity_ids:
        _log("get_selected_line_endpoints: no entity ids found")
        return None

    # 方式0：直接从 entity id 读取 noumenon/参数（最可能成功）
    for eid in entity_ids:
        try:
            params = _read_params_from_entity(eid)
            _log(f"get_selected_line_endpoints: entity read type={type(params).__name__}, keys={_safe_keys(params)}, items={_safe_items_preview(params, 10)}")
            endpoints = _extract_line_endpoints_from_params(params)
            if endpoints:
                _log(f"get_selected_line_endpoints: found endpoints from entity noumenon: {endpoints[0]} -> {endpoints[1]}")
                return endpoints
        except Exception as e:
            _log(f"get_selected_line_endpoints entity read error: {e}")

    # 方式0b：直接把 entity id 当 instance key 读（某些版本 get_current_entityId 返回的就是 instance key）
    for eid in entity_ids:
        try:
            params = _read_params_from_instancekey(eid)
            _log(f"get_selected_line_endpoints: direct read type={type(params).__name__}, keys={_safe_keys(params)}, items={_safe_items_preview(params, 10)}")
            endpoints = _extract_line_endpoints_from_params(params)
            if endpoints:
                _log(f"get_selected_line_endpoints: found endpoints from direct read: {endpoints[0]} -> {endpoints[1]}")
                return endpoints
        except Exception as e:
            _log(f"get_selected_line_endpoints direct read error: {e}")

    # 读取选中 entity 的 ID
    target_ids = []
    for eid in entity_ids:
        mid, eid_val = _safe_entity_id(eid)
        _log(f"get_selected_line_endpoints: selected entity ModelId={mid}, ElementId={eid_val}")
        if mid is not None and eid_val is not None:
            target_ids.append((mid, eid_val))

    # 方式1：通过 get_all_instancekey() 扫描所有实例，匹配选中实体
    if get_all_instancekey is not None and get_noumKV_from_instancekey is not None:
        try:
            keys = get_all_instancekey() or []
            _log(f"get_selected_line_endpoints: get_all_instancekey returned {len(keys)} keys")
            # 先尝试直接相等匹配（P3DEntityId 与 P3DInstanceKey 可能支持 __eq__）
            matched = None
            for ik in keys:
                try:
                    for eid in entity_ids:
                        try:
                            if ik == eid:
                                _log(f"get_selected_line_endpoints: direct equality matched instancekey type={type(ik).__name__}")
                                matched = ik
                                break
                        except Exception:
                            pass
                    if matched is not None:
                        break
                except Exception as e:
                    _log(f"get_selected_line_endpoints equality match error: {e}")

            # 再尝试按 ModelId/ElementId 匹配
            if matched is None and target_ids:
                for ik in keys:
                    try:
                        mid, eid_val = _safe_instance_id(ik)
                        if (mid, eid_val) in target_ids:
                            _log(f"get_selected_line_endpoints: matched instancekey ModelId={mid}, ElementId={eid_val}")
                            matched = ik
                            break
                    except Exception as e:
                        _log(f"get_selected_line_endpoints scan instancekey error: {e}")

            if matched is not None:
                try:
                    params = _read_params_from_instancekey(matched)
                    _log(f"get_selected_line_endpoints: matched params type={type(params).__name__}, keys={_safe_keys(params)}, items={_safe_items_preview(params, 10)}")
                    endpoints = _extract_line_endpoints_from_params(params)
                    if endpoints:
                        _log(f"get_selected_line_endpoints: found endpoints from matched instance: {endpoints[0]} -> {endpoints[1]}")
                        return endpoints
                except Exception as e:
                    _log(f"get_selected_line_endpoints read matched params error: {e}")
        except Exception as e:
            _log(f"get_selected_line_endpoints get_all_instancekey error: {e}")

    # 方式2：尝试 get_datakey_from_entity + get_noumKV_from_instancekey
    for eid in entity_ids:
        try:
            dk = get_datakey_from_entity(eid) if get_datakey_from_entity is not None else None
            _log(f"get_selected_line_endpoints: datakey type={type(dk).__name__ if dk is not None else None}")
            if dk is not None:
                try:
                    params = _read_params_from_instancekey(dk)
                    _log(f"get_selected_line_endpoints: datakey params type={type(params).__name__}, keys={_safe_keys(params)}, items={_safe_items_preview(params, 10)}")
                    endpoints = _extract_line_endpoints_from_params(params)
                    if endpoints:
                        _log(f"get_selected_line_endpoints: found endpoints from datakey: {endpoints[0]} -> {endpoints[1]}")
                        return endpoints
                except Exception as e:
                    _log(f"get_selected_line_endpoints datakey read error: {e}")
        except Exception as e:
            _log(f"get_selected_line_endpoints datakey error: {e}")

    # 方式3：尝试 get_noumenon_from_instancekey（如果有 datakey）
    for eid in entity_ids:
        try:
            dk = get_datakey_from_entity(eid) if get_datakey_from_entity is not None else None
            if dk is not None and get_noumenon_from_instancekey is not None:
                try:
                    noum = get_noumenon_from_instancekey(dk)
                    _log(f"get_selected_line_endpoints: noumenon type={type(noum).__name__}, keys={_safe_keys(noum)}, items={_safe_items_preview(noum, 10)}")
                    if noum is not None:
                        endpoints = _extract_line_endpoints_from_params(noum)
                        if endpoints:
                            _log(f"get_selected_line_endpoints: found endpoints from noumenon: {endpoints[0]} -> {endpoints[1]}")
                            return endpoints
                except Exception as e:
                    _log(f"get_selected_line_endpoints noumenon error: {e}")
        except Exception as e:
            _log(f"get_selected_line_endpoints datakey2 error: {e}")

    # 方式4：兜底扫描，如果场景中只有一个直线/曲线组件，直接使用它
    if get_all_instancekey is not None:
        try:
            line_candidates = []
            arc_candidates = []
            for ik in get_all_instancekey():
                params = _read_params_from_instancekey(ik)
                if _extract_line_endpoints_from_params(params):
                    line_candidates.append(ik)
                elif _extract_arc_params_from_params(params):
                    arc_candidates.append(ik)
            if len(line_candidates) == 1:
                params = _read_params_from_instancekey(line_candidates[0])
                endpoints = _extract_line_endpoints_from_params(params)
                _log(f"get_selected_line_endpoints: fallback using the only line component in scene: {endpoints}")
                return endpoints
            elif len(line_candidates) > 1:
                _log(f"get_selected_line_endpoints: fallback found {len(line_candidates)} line components, cannot decide")
        except Exception as e:
            _log(f"get_selected_line_endpoints fallback scan error: {e}")

    _log("get_selected_line_endpoints: failed to read line endpoints from all methods")
    return None
