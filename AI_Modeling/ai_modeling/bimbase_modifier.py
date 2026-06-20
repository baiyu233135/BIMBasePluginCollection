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
get_datakey_from_entity = None
get_entityid_from_boxselection = None
get_current_entityId = None
entityid_isvaid = None
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
        'get_datakey_from_entity',
        'get_entityid_from_boxselection',
        'get_current_entityId',
        'entityid_isvaid',
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


def get_selected_instance_keys():
    """
    获取用户在 BIMBase 中选中的实体对应的 instance keys
    返回: list of instance_key 或 []
    """
    keys = []
    if not _pyp3d_ok:
        return keys

    # 方式1：框选
    if get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
            for eid in entity_ids:
                if entityid_isvaid and not entityid_isvaid(eid):
                    continue
                dk = get_datakey_from_entity(eid) if get_datakey_from_entity else None
                if dk is not None:
                    keys.append(dk)
        except Exception as e:
            _log(f"get_entityid_from_boxselection error: {e}")

    # 方式2：当前单个选中
    if not keys and get_current_entityId is not None:
        try:
            cur_id = get_current_entityId()
            if cur_id and entityid_isvaid and entityid_isvaid(cur_id):
                dk = get_datakey_from_entity(cur_id) if get_datakey_from_entity else None
                if dk is not None:
                    keys.append(dk)
        except Exception as e:
            _log(f"get_current_entityId error: {e}")

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


def _extract_line_endpoints_from_params(params):
    """从参数字典/Noumenon中提取线的两个端点"""
    if params is None:
        return None
    # 英文键
    if all(k in params for k in ('x1', 'y1', 'z1', 'x2', 'y2', 'z2')):
        p1 = (float(params['x1']), float(params['y1']), float(params['z1']))
        p2 = (float(params['x2']), float(params['y2']), float(params['z2']))
        return p1, p2
    # 中文键
    if all(k in params for k in ('起点X', '起点Y', '起点Z', '终点X', '终点Y', '终点Z')):
        p1 = (float(params['起点X']), float(params['起点Y']), float(params['起点Z']))
        p2 = (float(params['终点X']), float(params['终点Y']), float(params['终点Z']))
        return p1, p2
    # 尝试 start_x/start_y/start_z, end_x/end_y/end_z
    if all(k in params for k in ('start_x', 'start_y', 'start_z', 'end_x', 'end_y', 'end_z')):
        p1 = (float(params['start_x']), float(params['start_y']), float(params['start_z']))
        p2 = (float(params['end_x']), float(params['end_y']), float(params['end_z']))
        return p1, p2
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

    # 收集选中的 entity id
    entity_ids = []
    if get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
            _log(f"get_selected_line_endpoints: boxselection returned {len(entity_ids)} entities")
        except Exception as e:
            _log(f"get_selected_line_endpoints boxselection error: {e}")
    if not entity_ids and get_current_entityId is not None:
        try:
            cur_id = get_current_entityId()
            _log(f"get_selected_line_endpoints: current_entityId type={type(cur_id).__name__}")
            if cur_id is not None and entityid_isvaid is not None and entityid_isvaid(cur_id):
                entity_ids = [cur_id]
        except Exception as e:
            _log(f"get_selected_line_endpoints current_entityId error: {e}")

    if not entity_ids:
        _log("get_selected_line_endpoints: no entity ids found")
        return None

    # 方式0：如果选中的对象本身就是 P3DInstanceKey，直接用它读取参数
    for eid in entity_ids:
        if type(eid).__name__ == 'P3DInstanceKey':
            _log(f"get_selected_line_endpoints: selected object is P3DInstanceKey, trying direct read")
            if get_noumKV_from_instancekey is not None:
                try:
                    params = get_noumKV_from_instancekey(eid)
                    _log(f"get_selected_line_endpoints: direct noumKV type={type(params).__name__}, keys={_safe_keys(params)}, items={_safe_items_preview(params, 10)}")
                    endpoints = _extract_line_endpoints_from_params(params)
                    if endpoints:
                        _log(f"get_selected_line_endpoints: found endpoints from direct noumKV: {endpoints[0]} -> {endpoints[1]}")
                        return endpoints
                except Exception as e:
                    _log(f"get_selected_line_endpoints direct noumKV error: {e}")
            if get_noumenon_from_instancekey is not None:
                try:
                    noum = get_noumenon_from_instancekey(eid)
                    _log(f"get_selected_line_endpoints: direct noumenon type={type(noum).__name__}, keys={_safe_keys(noum)}, items={_safe_items_preview(noum, 10)}")
                    endpoints = _extract_line_endpoints_from_params(noum)
                    if endpoints:
                        _log(f"get_selected_line_endpoints: found endpoints from direct noumenon: {endpoints[0]} -> {endpoints[1]}")
                        return endpoints
                except Exception as e:
                    _log(f"get_selected_line_endpoints direct noumenon error: {e}")

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
                    params = get_noumKV_from_instancekey(matched)
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
            if dk is not None and get_noumKV_from_instancekey is not None:
                try:
                    params = get_noumKV_from_instancekey(dk)
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

    _log("get_selected_line_endpoints: failed to read line endpoints from all methods")
    return None
