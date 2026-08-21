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
get_noumenon_on_entityid = None
get_noumenon_from_datakey = None
get_datakey_from_entity = None
get_entityid_from_boxselection = None
get_current_entityId = None
entityid_isvaid = None
entityid_isvalid = None
get_selections = None
get_element_from_boxselect = None
get_allbinding_entity_from_data = None
replace_noumenon = None
get_entity_property = None
get_entity_bounds = None
delete_one_entity = None
delete_data_bydatakey = None

# 逐个从 pyp3d 导入，避免某个 API 不存在导致全部失败
try:
    import pyp3d
    _pyp3d_ok = True
    _api_names = [
        'get_all_instancekey',
        'get_noumKV_from_instancekey',
        'get_noumenon_on_entityid',
        'get_noumenon_from_datakey',
        'get_datakey_from_entity',
        'get_entityid_from_boxselection',
        'get_current_entityId',
        'entityid_isvaid',
        'entityid_isvalid',
        'get_selections',
        'get_element_from_boxselect',
        'get_allbinding_entity_from_data',
        'replace_noumenon',
        'get_entity_property',
        'get_entity_bounds',
        'delete_one_entity',
        'delete_data_bydatakey',
        'get_matrixs_position',
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

from ai_modeling.component_factory import create_component, COMPONENT_CLASSES, _count_entities


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
    # 复杂组件（引桥桥墩 / 索缆锚锭）
    if '盖梁总长' in keys or '墩柱间距' in keys or '系梁根数' in keys:
        return 'pier'
    if '锚块总长' in keys or '底柱半径' in keys or '承台长度' in keys:
        return 'anchor'
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
                # 回退：从注册表记录推断组件类型（AI 放置的组件有记录）
                try:
                    from ai_modeling.component_registry import ComponentRegistry
                    record = ComponentRegistry().get(instance_key)
                    if record:
                        comp_type = record.get('component_type')
                        _log(f"modify_instance_by_key: type from registry = {comp_type}")
                except Exception as e2:
                    _log(f"modify_instance_by_key: registry fallback failed: {e2}")
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

    # 方式2：get_noumenon_from_datakey + 修改 + replace()
    if get_noumenon_from_datakey is not None:
        try:
            noum = get_noumenon_from_datakey(instance_key)
            if noum is None:
                return False, "无法获取组件本体"

            modified = False
            for k, v in changes.items():
                try:
                    # 跳过不属于该组件的伪参数（如解析器从"墩高2000"套出的 height）
                    if hasattr(noum, '__contains__') and k not in noum:
                        _log(f"  skip {k}: not a component key")
                        continue
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


def delete_selected_components():
    """
    删除当前在 BIMBase 中选中的组件（实体删除优先，实例删除兜底）。
    删除后用实体计数校验确实生效（不轻信 API 无异常返回），
    生效后同步从 AI 注册表注销对应记录。
    返回: (success: bool, message: str, deleted: int)
    """
    if not _pyp3d_ok:
        return False, "pyp3d 未加载", 0

    entity_ids = get_selected_entity_ids()
    instance_keys = get_selected_instance_keys()
    if not entity_ids and not instance_keys:
        return False, "未在 BIMBase 中选中任何组件，请先选中要删除的组件", 0

    before = _count_entities()
    deleted = 0
    errors = []

    # 方式1：按实体删除（delete_one_entity）
    if entity_ids and delete_one_entity is not None:
        for eid in entity_ids:
            try:
                delete_one_entity(eid)
                deleted += 1
            except Exception as e:
                _log(f"delete_one_entity error: {e}")
                errors.append(str(e))

    # 方式2：按实例删除（delete_data_bydatakey），实体删除全部失败时兜底
    if deleted == 0 and instance_keys and delete_data_bydatakey is not None:
        for ik in instance_keys:
            try:
                delete_data_bydatakey(ik)
                deleted += 1
            except Exception as e:
                _log(f"delete_data_bydatakey error: {e}")
                errors.append(str(e))

    if deleted == 0:
        if delete_one_entity is None and delete_data_bydatakey is None:
            return False, "没有可用的删除 API", 0
        return False, f"删除失败: {errors[0] if errors else '未知错误'}", 0

    # 校验删除确实生效：实体计数减少，或已删实体失效
    after = _count_entities()
    _log(f"delete_selected_components: before={before}, after={after}, api_deleted={deleted}")
    verified = True
    if before >= 0 and after >= 0:
        verified = after < before
        if not verified and entity_ids:
            verified = any(not _is_entity_valid(eid) for eid in entity_ids)
    if not verified:
        return False, "删除指令已执行，但场景实体数未减少，可能未生效，请检查 BIMBase 视图", 0

    # 从注册表注销（instance_key / entity_id 两种键都尝试）
    try:
        from ai_modeling.component_registry import get_registry
        registry = get_registry()
        for ik in instance_keys:
            registry.unregister(ik)
        eid_strs = set()
        for eid in entity_ids:
            s = registry._key_str(eid)
            if s:
                eid_strs.add(s)
        for key, record in list(registry.all_records().items()):
            if record.get('entity_id') and record['entity_id'] in eid_strs:
                registry.unregister(key)
    except Exception as e:
        _log(f"delete_selected_components unregister error: {e}")

    return True, f"已删除 {deleted} 个组件", deleted


def get_selected_entity_ids():
    """
    获取 BIMBase 当前选中的 entity id 列表
    返回: list of entity_id 或 []
    """
    entity_ids = []
    if not _pyp3d_ok:
        return entity_ids

    if get_selections is not None:
        try:
            sel = get_selections()
            if sel:
                entity_ids = list(sel) if not isinstance(sel, (list, tuple)) else list(sel)
        except Exception as e:
            _log(f"get_selected_entity_ids get_selections error: {e}")

    if not entity_ids and get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
        except Exception as e:
            _log(f"get_selected_entity_ids boxselection error: {e}")

    if not entity_ids and get_current_entityId is not None:
        try:
            cur_id = get_current_entityId()
            if cur_id and _is_entity_valid(cur_id):
                entity_ids = [cur_id]
        except Exception as e:
            _log(f"get_selected_entity_ids current_entityId error: {e}")

    return [eid for eid in entity_ids if _is_entity_valid(eid)]


def _bounds_center(bounds):
    """从 bounding box 计算中心点，支持多种返回格式"""
    if bounds is None:
        return None
    try:
        _log(f"_bounds_center: raw bounds type={type(bounds).__name__}, value={bounds}")
        # 格式1: (xmin, ymin, zmin, xmax, ymax, zmax)
        if hasattr(bounds, '__len__') and len(bounds) == 6:
            return (
                (float(bounds[0]) + float(bounds[3])) / 2.0,
                (float(bounds[1]) + float(bounds[4])) / 2.0,
                (float(bounds[2]) + float(bounds[5])) / 2.0,
            )
        # 格式2: ((xmin,ymin,zmin), (xmax,ymax,zmax))
        if hasattr(bounds, '__len__') and len(bounds) == 2:
            mn = bounds[0]
            mx = bounds[1]
            return (
                (float(mn[0]) + float(mx[0])) / 2.0,
                (float(mn[1]) + float(mx[1])) / 2.0,
                (float(mn[2]) + float(mx[2])) / 2.0,
            )
        # 格式3: [Vec3(min), Vec3(max)]
        if hasattr(bounds, 'min') and hasattr(bounds, 'max'):
            mn = bounds.min
            mx = bounds.max
            return (
                (float(mn[0]) + float(mx[0])) / 2.0,
                (float(mn[1]) + float(mx[1])) / 2.0,
                (float(mn[2]) + float(mx[2])) / 2.0,
            )
        # 格式4: 本身就是包含 min/max 属性的对象
        if hasattr(bounds, 'xmin') and hasattr(bounds, 'xmax'):
            return (
                (float(bounds.xmin) + float(bounds.xmax)) / 2.0,
                (float(bounds.ymin) + float(bounds.ymax)) / 2.0,
                (float(bounds.zmin) + float(bounds.zmax)) / 2.0,
            )
    except Exception as e:
        _log(f"_bounds_center error: {e}, bounds={bounds}")
    return None


def _position_from_params(params):
    """从组件参数字典推断位置，用于 bounds 不可用时的回退"""
    if not params:
        return None
    try:
        # 优先读取显式位置字段（z 优先从 Placement 写入的 z/z_bottom）
        x = params.get('cx', params.get('x', params.get('x1', params.get('偏移X', 0))))
        y = params.get('cy', params.get('y', params.get('y1', params.get('偏移Y', 0))))
        z = params.get('z_bottom', params.get('z', params.get('z_top', params.get('z_start', params.get('偏移Z', 0)))))
        return (float(_parse_number(x)), float(_parse_number(y)), float(_parse_number(z)))
    except Exception as e:
        _log(f"_position_from_params error: {e}")
    return None


def get_selected_component_position(prefer_bounds=True):
    """
    获取当前选中组件的世界坐标位置
    优先使用 bounding box 中心；不可用时回退到参数字典推断
    返回: (x, y, z) 或 None
    """
    if not _pyp3d_ok:
        _log("get_selected_component_position: pyp3d not ok")
        return None

    entity_ids = get_selected_entity_ids()
    _log(f"get_selected_component_position: entity_ids count={len(entity_ids)}")
    if not entity_ids:
        # 没有 entity id 时，尝试从 instance key 读参数推断
        infos = get_selected_component_info()
        _log(f"get_selected_component_position: no entity id, infos count={len(infos)}")
        if infos:
            pos = _position_from_params(infos[0].get('params'))
            if pos:
                _log(f"get_selected_component_position: fallback from params (no entity id): {pos}")
            return pos
        return None

    eid = entity_ids[0]
    _log(f"get_selected_component_position: using first entity id, type={type(eid).__name__}")

    # 优先读取 bounding box
    if prefer_bounds and get_entity_bounds is not None:
        _log("get_selected_component_position: trying get_entity_bounds")
        # 先尝试用 entity id
        bounds = None
        try:
            bounds = get_entity_bounds(eid)
        except Exception as e:
            _log(f"get_entity_bounds(entity_id) failed: {e}")

        # 再尝试用 datakey
        if bounds is None and get_datakey_from_entity is not None:
            try:
                dk = get_datakey_from_entity(eid)
                _log(f"get_datakey_from_entity returned type={type(dk).__name__ if dk is not None else None}")
                if dk is not None:
                    bounds = get_entity_bounds(dk)
            except Exception as e:
                _log(f"get_entity_bounds(datakey) failed: {e}")

        center = _bounds_center(bounds)
        if center:
            _log(f"get_selected_component_position: from bounds: {center}")
            return center
        _log("get_selected_component_position: bounds not available or invalid")

    # 回退：从 entity / instance 读参数推断
    try:
        params = _read_params_from_entity(eid)
        _log(f"get_selected_component_position: read params from entity, type={type(params).__name__ if params else None}")

        # 再回退：扫描所有 instance key，通过“绑定实体”关系找到选中实体对应的参数化组件实例
        if not params and get_all_instancekey is not None and get_allbinding_entity_from_data is not None:
            try:
                target_tuples = [_entity_id_tuple(e) for e in entity_ids]
                target_tuples = [t for t in target_tuples if t is not None]
                _log(f"get_selected_component_position: binding scan target_tuples={target_tuples}")
                scanned = 0
                for ik in get_all_instancekey():
                    scanned += 1
                    try:
                        bound_entities = get_allbinding_entity_from_data(ik)
                        if not bound_entities:
                            continue
                        for eid_tmp in entity_ids:
                            if _entity_id_in_list(eid_tmp, bound_entities):
                                params = _read_params_from_instancekey(ik)
                                _log(f"get_selected_component_position: found binding instance for selected entity, params type={type(params).__name__ if params else None}")
                                if params:
                                    break
                        if params:
                            break
                    except Exception as e:
                        _log(f"get_selected_component_position binding scan item error: {e}")
                    if scanned >= 300:
                        _log("get_selected_component_position: binding scan reached limit 300")
                        break
            except Exception as e:
                _log(f"get_selected_component_position binding scan error: {e}")

        # 再回退：扫描所有 instance key，按 ID 匹配选中实体
        if not params and get_all_instancekey is not None:
            target_ids = []
            target_element_ids = []
            for eid_tmp in entity_ids:
                mid, eid_val = _safe_entity_id(eid_tmp, log=False)
                if mid is not None and eid_val is not None:
                    target_ids.append((mid, eid_val))
                if eid_val is not None:
                    target_element_ids.append(eid_val)
            _log(f"get_selected_component_position: id scan target_ids={target_ids}, element_ids={target_element_ids}")
            if target_ids or target_element_ids:
                try:
                    scanned = 0
                    for ik in get_all_instancekey():
                        scanned += 1
                        if scanned > 300:
                            _log("get_selected_component_position: id scan reached limit 300")
                            break
                        mid, eid_val = _safe_instance_id(ik, log=False)
                        # 完全匹配（model + element）或仅 element id 匹配
                        if (mid is not None and eid_val is not None and (mid, eid_val) in target_ids) or \
                           (eid_val is not None and eid_val in target_element_ids):
                            params = _read_params_from_instancekey(ik)
                            _log(f"get_selected_component_position: matched instance key by id, params type={type(params).__name__ if params else None}")
                            if params:
                                break
                except Exception as e:
                    _log(f"get_selected_component_position id scan error: {e}")

        # 最后回退：get_selected_instance_keys() 通常能把 entity id 转成 datakey
        if not params:
            keys = get_selected_instance_keys()
            _log(f"get_selected_component_position: fallback instance keys count={len(keys)}")
            if keys:
                params = _read_params_from_instancekey(keys[0])
                _log(f"get_selected_component_position: read params from selected instance key, type={type(params).__name__ if params else None}")

        # 兜底：如果场景中只有一个 AI 可识别的组件，直接使用它
        if not params and get_all_instancekey is not None and len(entity_ids) == 1:
            try:
                ai_candidates = []
                for ik in get_all_instancekey():
                    p = _read_params_from_instancekey(ik)
                    if p and infer_component_type_from_params(p):
                        ai_candidates.append(ik)
                if len(ai_candidates) == 1:
                    params = _read_params_from_instancekey(ai_candidates[0])
                    _log(f"get_selected_component_position: fallback using the only AI component in scene")
            except Exception as e:
                _log(f"get_selected_component_position only-one fallback error: {e}")

        pos = _position_from_params(params)
        if pos:
            _log(f"get_selected_component_position: from params: {pos}")
        return pos
    except Exception as e:
        _log(f"get_selected_component_position fallback error: {e}")

    return None


def _find_id_attr(obj, kind):
    """安全地从对象中读取 ID 属性（kind='model' 或 'element'）。
    对 P3DInstanceKey 使用 _PClassId/_P3DInstanceId 作为 model/element 候选。"""
    if obj is None:
        return None
    if kind == 'model':
        candidates = ['ModelId', '_ModelId', '_PClassId', 'model_id', '_model_id', 'modelid', 'pclassid']
    else:
        candidates = ['ElementId', '_ElementId', '_P3DInstanceId', 'element_id', '_element_id', 'elementid', 'p3dinstanceid']
    for name in candidates:
        try:
            val = getattr(obj, name, None)
            if val is not None:
                return val
        except Exception:
            continue
    return None


def _is_instance_key(obj):
    """判断对象是否为 P3DInstanceKey 类型"""
    tname = type(obj).__name__
    if 'P3DInstanceKey' in tname:
        return True
    if hasattr(obj, '_P3DInstanceId') or hasattr(obj, '_PClassId'):
        return True
    return False


def _safe_entity_id(eid, log=True):
    """安全读取 entity id 的 ModelId/ElementId，避免访问异常"""
    try:
        mid = _find_id_attr(eid, 'model')
        eid_val = _find_id_attr(eid, 'element')
        if log:
            _log(f"_safe_entity_id: type={type(eid).__name__}, ModelId={mid}, ElementId={eid_val}")
        return mid, eid_val
    except Exception as e:
        if log:
            _log(f"_safe_entity_id error: {e}")
        return None, None


def _entity_id_tuple(eid):
    """把 entity id 转成 (ModelId, ElementId) 元组，用于比较"""
    mid, eid_val = _safe_entity_id(eid, log=False)
    if mid is not None and eid_val is not None:
        return (mid, eid_val)
    return None


def _entity_id_in_list(eid, eid_list):
    """判断 entity id 是否在一个 entity id 列表中（按 ModelId+ElementId 比较）"""
    target = _entity_id_tuple(eid)
    if target is None:
        return False
    for item in eid_list:
        if target == _entity_id_tuple(item):
            return True
    return False


def _safe_instance_id(ik, log=True):
    """安全读取 instance key 的 ID（Model/Class 与 Element/Instance）"""
    try:
        mid = _find_id_attr(ik, 'model')
        eid_val = _find_id_attr(ik, 'element')
        if log:
            _log(f"_safe_instance_id: type={type(ik).__name__}, ClassId={mid}, InstanceId={eid_val}")
        return mid, eid_val
    except Exception as e:
        if log:
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


def _extract_xyz_from_placement(placement):
    """从 Placement 对象/字典/矩阵中提取 x,y,z 平移分量（参考 CADBoard 实现）"""
    try:
        # dict-like
        if isinstance(placement, dict):
            for kx in ('x', 'X', 'origin_x', 'translation_x', 'OriginX', 'TranslationX'):
                if kx in placement:
                    x = float(placement[kx])
                    y = float(placement.get('y', placement.get('Y', 0)))
                    z = float(placement.get('z', placement.get('Z', 0)))
                    return x, y, z
            if 'origin' in placement:
                return _extract_xyz_from_placement(placement['origin'])
            if 'translation' in placement:
                return _extract_xyz_from_placement(placement['translation'])
            return None
        # 对象属性
        if hasattr(placement, 'x') and hasattr(placement, 'y'):
            x = float(placement.x)
            y = float(placement.y)
            z = float(placement.z) if hasattr(placement, 'z') else 0.0
            return x, y, z
        # 列表/元组（Vec3 或矩阵）
        if isinstance(placement, (list, tuple)):
            if len(placement) >= 3:
                try:
                    return float(placement[0]), float(placement[1]), float(placement[2])
                except Exception:
                    pass
            if len(placement) >= 16:
                return float(placement[12]), float(placement[13]), float(placement[14])
        # 方法
        for method_name in ('get_translation', 'translation', 'get_origin', 'origin', 'get_position', 'position'):
            if hasattr(placement, method_name):
                try:
                    result = getattr(placement, method_name)()
                    if result is not None:
                        extracted = _extract_xyz_from_placement(result)
                        if extracted:
                            return extracted
                except Exception:
                    pass
    except Exception as e:
        _log(f"_extract_xyz_from_placement error: {e}")
    return None


def _extract_xyz_from_transform(transform):
    """从 GeTransform / 矩阵列表 / 字典中提取 x,y,z 平移分量"""
    if transform is None:
        return None
    try:
        # 优先使用 pyp3d 官方 helper
        if get_matrixs_position is not None:
            try:
                pos = get_matrixs_position(transform)
                if pos is not None:
                    if hasattr(pos, 'x') and hasattr(pos, 'y'):
                        return float(pos.x), float(pos.y), float(pos.z) if hasattr(pos, 'z') else 0.0
                    if isinstance(pos, (list, tuple)) and len(pos) >= 3:
                        return float(pos[0]), float(pos[1]), float(pos[2])
            except Exception:
                pass
        # GeTransform._mat 是 3x4 行主序矩阵，平移在 [i][3]
        if hasattr(transform, '_mat'):
            mat = transform._mat
            if isinstance(mat, (list, tuple)) and len(mat) == 3:
                return float(mat[0][3]), float(mat[1][3]), float(mat[2][3])
        # 16 元素列表/元组（列主序 OpenGL 风格）
        if isinstance(transform, (list, tuple)) and len(transform) >= 16:
            return float(transform[12]), float(transform[13]), float(transform[14])
        # dict 形式
        if isinstance(transform, dict):
            for kx in ('x', 'X', 'origin_x', 'translation_x'):
                if kx in transform:
                    x = float(transform[kx])
                    y = float(transform.get('y', transform.get('Y', 0)))
                    z = float(transform.get('z', transform.get('Z', 0)))
                    return x, y, z
            if 'translation' in transform:
                return _extract_xyz_from_transform(transform['translation'])
            if 'origin' in transform:
                return _extract_xyz_from_transform(transform['origin'])
        # 对象属性
        if hasattr(transform, 'x') and hasattr(transform, 'y'):
            return float(transform.x), float(transform.y), float(transform.z) if hasattr(transform, 'z') else 0.0
    except Exception as e:
        _log(f"_extract_xyz_from_transform error: {e}")
    return None


def _merge_para_cmpt_property(params):
    """展开 ParaCmptProperty 子字典"""
    if not isinstance(params, dict) or 'ParaCmptProperty' not in params:
        return params
    prop = params.get('ParaCmptProperty')
    if prop is None:
        return params
    extracted = {}
    try:
        if hasattr(prop, 'keys'):
            for key in prop:
                try:
                    extracted[key] = prop[key]
                except Exception:
                    pass
        elif isinstance(prop, dict):
            extracted = dict(prop)
    except Exception as e:
        _log(f"_merge_para_cmpt_property error: {e}")
    if extracted:
        return {**params, **extracted}
    return params


def _read_params_from_instancekey(datakey):
    """
    从 P3DInstanceKey 读取参数字典。
    优先 get_noumKV_from_instancekey，若为空则回退到 get_noumenon_from_datakey。
    参考 CADBoard，会展开 ParaCmptProperty 并从 Placement/\a_transformation 提取世界坐标。
    """
    if datakey is None:
        return None
    if not _is_instance_key(datakey):
        _log(f"_read_params_from_instancekey: reject non-instance-key type={type(datakey).__name__}")
        return None
    params = None
    if get_noumKV_from_instancekey is not None:
        try:
            params = get_noumKV_from_instancekey(datakey)
        except Exception as e:
            _log(f"_read_params_from_instancekey noumKV error: {e}")

    if params is not None and isinstance(params, dict):
        _log(f"_read_params_from_instancekey: noumKV keys={_safe_keys(params)}, len={len(params)}")
        # 展开 ParaCmptProperty
        params = _merge_para_cmpt_property(params)
        # 从 Placement 提取世界坐标
        if 'Placement' in params:
            placement = params.get('Placement')
            xyz = _extract_xyz_from_placement(placement)
            if xyz is not None:
                x, y, z = xyz
                params['x'] = x
                params['y'] = y
                params['z'] = z
                params['z_bottom'] = z
                _log(f"_read_params_from_instancekey: extracted placement xyz=({x:.2f}, {y:.2f}, {z:.2f})")
        # 从 transformation 矩阵提取世界坐标
        trans_key = '\a_transformation'
        if trans_key in params:
            xyz = _extract_xyz_from_transform(params[trans_key])
            if xyz is not None:
                x, y, z = xyz
                params['x'] = x
                params['y'] = y
                params['z'] = z
                params['z_bottom'] = z
                _log(f"_read_params_from_instancekey: extracted transform xyz=({x:.2f}, {y:.2f}, {z:.2f})")
        if len(params) > 0:
            return params

    # 回退：读取完整 Noumenon 对象
    if get_noumenon_from_datakey is None:
        return None
    try:
        noum = get_noumenon_from_datakey(datakey)
        params = _read_params_from_noumenon(noum)
        if params:
            _log(f"_read_params_from_instancekey: got params from noumenon, keys={_safe_keys(params)}")
            return params
    except Exception as e:
        _log(f"_read_params_from_instancekey noumenon error: {e}")
    return None


def _read_params_from_noumenon(noum):
    """从 Noumenon 对象中读取参数化组件的参数字典，包含世界坐标。"""
    if noum is None:
        return None
    d = None
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
    except Exception:
        pass
    # 回退：直接遍历 noumenon
    if not d:
        try:
            d = {}
            for key in noum:
                d[key] = noum[key]
        except Exception:
            pass
    if not d:
        try:
            d = {}
            for key, val in noum.items():
                d[key] = val
        except Exception:
            pass
    if d:
        d = _merge_para_cmpt_property(d)
        if 'Placement' in d:
            placement = d.get('Placement')
            xyz = _extract_xyz_from_placement(placement)
            if xyz is not None:
                x, y, z = xyz
                d['x'] = x
                d['y'] = y
                d['z'] = z
        trans_key = '\a_transformation'
        if trans_key in d:
            xyz = _extract_xyz_from_transform(d[trans_key])
            if xyz is not None:
                x, y, z = xyz
                d['x'] = x
                d['y'] = y
                d['z'] = z
                d['z_bottom'] = z
        if d:
            return d
    # 最后尝试：即使没有任何参数，也读 transformation 矩阵的平移作为位置
    try:
        trans_key = '\a_transformation'
        if trans_key in noum:
            xyz = _extract_xyz_from_transform(noum[trans_key])
            if xyz is not None:
                x, y, z = xyz
                return {'x': x, 'y': y, 'z': z, 'z_bottom': z, trans_key: noum[trans_key]}
    except Exception:
        pass
    return None


def _read_params_from_entity(eid):
    """从选中的几何实体 entity id 直接读取参数（优先用 get_noumenon_on_entityid）。"""
    if eid is None:
        return None
    _log(f"_read_params_from_entity: start, type={type(eid).__name__}")
    # 方式1：get_noumenon_on_entityid 直接返回实体对应的 noumenon
    if get_noumenon_on_entityid is not None:
        try:
            noum = get_noumenon_on_entityid(eid)
            _log(f"_read_params_from_entity: get_noumenon_on_entityid returned type={type(noum).__name__ if noum is not None else None}")
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
            _log(f"_read_params_from_entity: get_datakey_from_entity returned type={type(dk).__name__ if dk is not None else None}")
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
    _log("_read_params_from_entity: all methods failed")
    return None


def _extract_arc_params_from_params(params):
    """从参数字典/Noumenon中提取圆弧参数（适配中文参数命名）。"""
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

    # 方式3：尝试 get_noumenon_from_datakey（如果有 datakey）
    for eid in entity_ids:
        try:
            dk = get_datakey_from_entity(eid) if get_datakey_from_entity is not None else None
            if dk is not None and get_noumenon_from_datakey is not None:
                try:
                    noum = get_noumenon_from_datakey(dk)
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
