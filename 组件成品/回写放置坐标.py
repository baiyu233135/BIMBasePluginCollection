# -*- coding: utf-8 -*-
"""
回写放置坐标（按钮脚本）

用途：组件用原生布置工具（place / TwoPointPlace）放完后，选中组件点击本按钮，
脚本读取实例的放置变换（transformation），把基准点三轴坐标写入组件的
X坐标 / Y坐标 / Z坐标 参数（参数需在组件类中已定义，如 铁路封闭网）。

说明：自定义 interact 工具在鼠标移动时逐事件回调 Python，对重组件卡顿明显，
故采用"原生布置（顺滑）+ 事后回写"的两步方案。
坐标提取逻辑移植自 桥隧病害识别/disease_dialog.py 的 _extract_xyz_robust（已实测）。
"""

import os
import sys
from datetime import datetime

import pyp3d


def _p3d(name):
    """宽容式取 pyp3d API：某个 API 不存在时返回 None 而不是 ImportError
    （直接 from pyp3d import 不存在的名字会让整个脚本在导入期就崩溃）"""
    return getattr(pyp3d, name, None)


get_selections = _p3d('get_selections')
get_entityid_from_boxselection = _p3d('get_entityid_from_boxselection')
get_current_entityId = _p3d('get_current_entityId')
get_datakey_from_entity = _p3d('get_datakey_from_entity')
get_noumKV_from_instancekey = _p3d('get_noumKV_from_instancekey')
get_noumenon_from_datakey = _p3d('get_noumenon_from_datakey')
get_all_instancekey = _p3d('get_all_instancekey')
get_allbinding_entity_from_data = _p3d('get_allbinding_entity_from_data')
entityid_isvaid = _p3d('entityid_isvaid') or _p3d('entityid_isvalid')

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _log(msg):
    try:
        with open(os.path.join(_SCRIPT_DIR, '回写放置坐标_debug.log'), 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _is_entity_valid(eid):
    if eid is None:
        return False
    if entityid_isvaid is not None:
        try:
            return bool(entityid_isvaid(eid))
        except Exception:
            pass
    return True


def _obj_id_tuple(obj):
    """提取 id/key 对象的 (ModelId, ElementId) 用于比较与去重
    （P3DEntityId/P3DInstanceKey 不可 str()，会触发 _data AttributeError）"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float)):
        return ('plain', obj)
    mid = eid = None
    for attr in ('_ModelId', '_PClassId', 'ModelId', 'model_id'):
        try:
            mid = getattr(obj, attr, None)
            if mid is not None:
                break
        except Exception:
            continue
    for attr in ('_ElementId', 'ElementId', 'element_id',
                 '_P3DInstanceId', 'P3DInstanceId', 'p3d_instance_id'):
        try:
            eid = getattr(obj, attr, None)
            if eid is not None:
                break
        except Exception:
            continue
    return (mid, eid)


def get_selected_entity_ids():
    """获取当前选中的 entity id 列表（各 API 宽容调用）"""
    entity_ids = []
    if get_selections is not None:
        try:
            sel = get_selections()
            if sel:
                entity_ids = list(sel)
        except Exception as e:
            _log(f"get_selections error: {e}")
    if not entity_ids and get_entityid_from_boxselection is not None:
        try:
            entity_ids = get_entityid_from_boxselection() or []
        except Exception as e:
            _log(f"get_entityid_from_boxselection error: {e}")
    if not entity_ids and get_current_entityId is not None:
        try:
            cur = get_current_entityId()
            if cur:
                entity_ids = [cur]
        except Exception as e:
            _log(f"get_current_entityId error: {e}")
    return [eid for eid in entity_ids if _is_entity_valid(eid)]


def get_selected_instance_keys():
    """选中实体 → datakey 直取"""
    keys = []
    if get_datakey_from_entity is None:
        return keys
    for eid in get_selected_entity_ids():
        try:
            dk = get_datakey_from_entity(eid)
        except Exception as e:
            _log(f"get_datakey_from_entity error: {e}")
            dk = None
        if dk is not None:
            keys.append(dk)
    return keys


def get_target_instance_keys():
    """目标实例 keys：选中实体直取 + 全场景扫描按绑定实体匹配（代理实体兜底）。
    选中的参数化组件往往是“代理”实体，其 datakey 的 noumKV 可能缺少放置变换；
    通过 get_all_instancekey 全扫 + get_allbinding_entity_from_data 反查绑定实体，
    可拿到携带完整变换信息的真实实例。"""
    keys = []
    seen = set()

    def _add(ik):
        t = _obj_id_tuple(ik)
        if t is not None and t not in seen:
            seen.add(t)
            keys.append(ik)

    for ik in get_selected_instance_keys():
        _add(ik)

    sel = get_selected_entity_ids()
    if sel and get_all_instancekey is not None and get_allbinding_entity_from_data is not None:
        sel_tuples = {_obj_id_tuple(e) for e in sel}
        try:
            all_keys = get_all_instancekey() or []
        except Exception as e:
            _log(f"get_all_instancekey error: {e}")
            all_keys = []
        _log(f"全场景扫描: {len(all_keys)} 个实例，选中实体 {len(sel)} 个")
        for ik in all_keys:
            try:
                ents = get_allbinding_entity_from_data(ik) or []
            except Exception:
                continue
            if any(_obj_id_tuple(e) in sel_tuples for e in ents):
                _add(ik)
    return keys


def _extract_xyz(obj, _depth=0):
    """从 GeTransform/Placement/矩阵/字典/对象中提取平移分量
    （移植自 桥隧病害识别/disease_dialog.py::_extract_xyz_robust，已实测）"""
    if obj is None or _depth > 3:
        return None
    try:
        # GeTransform._mat：3x4 行主序矩阵，平移在 [i][3]
        if hasattr(obj, '_mat'):
            mat = obj._mat
            if isinstance(mat, (list, tuple)) and len(mat) == 3:
                return float(mat[0][3]), float(mat[1][3]), float(mat[2][3])
        # pyp3d 官方 helper
        try:
            from pyp3d import get_matrixs_position
            pos = get_matrixs_position(obj)
            if pos is not None:
                r = _extract_xyz(pos, _depth + 1)
                if r is not None:
                    return r
        except Exception:
            pass
        # 字典形式
        if isinstance(obj, dict):
            for kx in ('x', 'X', 'origin_x', 'translation_x', 'OriginX', 'TranslationX'):
                if kx in obj:
                    return (float(obj[kx]),
                            float(obj.get('y', obj.get('Y', 0))),
                            float(obj.get('z', obj.get('Z', 0))))
            for kk in ('translation', 'origin'):
                if kk in obj:
                    r = _extract_xyz(obj[kk], _depth + 1)
                    if r is not None:
                        return r
            return None
        # 对象属性 x/y/z
        if hasattr(obj, 'x') and hasattr(obj, 'y'):
            return (float(obj.x), float(obj.y),
                    float(obj.z) if hasattr(obj, 'z') else 0.0)
        # 列表/元组（16 元素列主序矩阵，或 Vec3）
        if isinstance(obj, (list, tuple)):
            if len(obj) >= 16:
                return float(obj[12]), float(obj[13]), float(obj[14])
            if len(obj) >= 3:
                try:
                    return float(obj[0]), float(obj[1]), float(obj[2])
                except Exception:
                    pass
        # 方法形式
        for m in ('get_translation', 'translation', 'get_origin', 'origin',
                  'get_position', 'position'):
            if hasattr(obj, m):
                try:
                    r = _extract_xyz(getattr(obj, m)(), _depth + 1)
                    if r is not None:
                        return r
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _get_instance_xyz(ik):
    """从实例的 noumKV 中读放置变换并提取平移。
    遍历全部候选键（含 ParaCmptProperty 子字典），优先采用非零结果；
    全部为零时扫描所有值中的矩阵对象兜底。键结构写入调试日志。"""
    try:
        kv = get_noumKV_from_instancekey(ik)
    except Exception as e:
        _log(f"get_noumKV_from_instancekey error: {e}")
        return None
    if not isinstance(kv, dict):
        _log(f"noumKV 不是字典: {type(kv).__name__}")
        return None

    # 诊断：记录键结构（键名 + 值类型），便于定位变换实际存放位置
    try:
        _log("noumKV keys: " + ", ".join(
            f"{repr(k)}:{type(v).__name__}" for k, v in kv.items()))
    except Exception:
        pass

    dicts = [kv]
    prop = kv.get('ParaCmptProperty')
    if isinstance(prop, dict):
        dicts.append(prop)
    elif prop is not None and hasattr(prop, 'keys'):
        try:
            dicts.append({k: prop[k] for k in prop.keys()})
        except Exception:
            pass

    TRANSFORM_KEYS = ('\a_transformation', '\aGraphicElement::m_transform',
                      'Placement', 'BaseTransform')
    candidates = []
    for d in dicts:
        for key in TRANSFORM_KEYS:
            if key in d:
                xyz = _extract_xyz(d.get(key))
                _log(f"候选 {repr(key)} -> {xyz}")
                if xyz is not None:
                    candidates.append((key, xyz))
        # 兜底：扫描所有值中的矩阵对象（_mat 3x4）
        for k, v in d.items():
            if k in TRANSFORM_KEYS:
                continue
            if hasattr(v, '_mat'):
                xyz = _extract_xyz(v)
                _log(f"矩阵对象 {repr(k)} -> {xyz}")
                if xyz is not None:
                    candidates.append((k, xyz))

    # 优先非零结果（单位矩阵的 (0,0,0) 往往是错误键）
    for key, xyz in candidates:
        if abs(xyz[0]) > 1e-9 or abs(xyz[1]) > 1e-9 or abs(xyz[2]) > 1e-9:
            return xyz
    if candidates:
        _log("警告：所有候选键提取结果均为 (0,0,0)")
        return candidates[0][1]
    return None


def _notify(title, text):
    try:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(None, title, text)
    except Exception:
        print(f"{title}: {text}")


def main():
    keys = get_target_instance_keys()
    _log(f"目标实例 keys: {len(keys)}")
    if not keys:
        _notify("回写放置坐标", "未检测到选中的组件。\n请先在 BIMBase 视图中选中要回写坐标的组件。")
        return

    done, no_xyz, no_param, failed = 0, 0, 0, 0
    zero_written = 0
    for ik in keys:
        xyz = _get_instance_xyz(ik)
        if xyz is None:
            no_xyz += 1
            _log("skip: 未读到放置变换")
            continue
        try:
            noum = get_noumenon_from_datakey(ik)
        except Exception as e:
            _log(f"get_noumenon_from_datakey error: {e}")
            noum = None
        if noum is None:
            failed += 1
            continue
        # 组件类需已定义坐标参数（如 铁路封闭网），否则跳过
        if hasattr(noum, '__contains__') and 'X坐标' not in noum:
            no_param += 1
            _log("skip: 组件没有 X/Y/Z坐标 参数")
            continue
        try:
            noum['X坐标'] = float(xyz[0])
            noum['Y坐标'] = float(xyz[1])
            noum['Z坐标'] = float(xyz[2])
            if hasattr(noum, 'replace'):
                noum.replace()
            done += 1
            if abs(xyz[0]) < 1e-9 and abs(xyz[1]) < 1e-9 and abs(xyz[2]) < 1e-9:
                zero_written += 1
            _log(f"written: ({xyz[0]:.1f}, {xyz[1]:.1f}, {xyz[2]:.1f})")
        except Exception as e:
            failed += 1
            _log(f"write error: {e}")

    msg = f"已回写 {done} 个组件的放置坐标。"
    if no_param:
        msg += f"\n跳过 {no_param} 个（组件没有 X/Y/Z坐标 参数，请重新布置后再试）。"
    if no_xyz:
        msg += f"\n跳过 {no_xyz} 个（未读到放置变换）。"
    if failed:
        msg += f"\n失败 {failed} 个。"
    if zero_written:
        msg += (f"\n\n注意：{zero_written} 个组件读到的是 (0,0,0)，可能不是实际位置。"
                f"\n请把 组件成品/回写放置坐标_debug.log 发给开发者排查。")
    elif done:
        msg += "\n\n请点击其他位置再选中组件，在属性面板查看 X/Y/Z坐标。"
    if no_xyz or failed:
        msg += "\n（详见 组件成品/回写放置坐标_debug.log）"
    _notify("回写放置坐标", msg)


if __name__ == "__main__":
    main()
